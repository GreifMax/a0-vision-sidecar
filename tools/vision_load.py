from helpers.print_style import PrintStyle
from helpers.tool import Tool, Response
from helpers import runtime, files, plugins, ephemeral_images, images, chat_media
from mimetypes import guess_type
from helpers import history

TOKENS_ESTIMATE = 1500


class VisionLoad(Tool):
    async def execute(self, paths: list[str] | str = [], query: str = "", raw: bool = False, **kwargs) -> Response:
        # State for after_execution
        self.images_dict = {}
        self.loaded_paths: list[str] = []
        self.skipped_paths: list[str] = []
        self._arg_error: str | None = None
        self._is_delegated: bool = False
        self._delegated_capsule: str | None = None
        self._delegation_error: str | None = None
        self.query = str(query or "").strip()
        self._raw = bool(raw) if isinstance(raw, bool) else str(raw).lower() in ("true", "1", "yes")

        # --- Phase 0: normalize prompt-style aliases into `query` ---
        # Some models send a differently-named focus argument ("Prompt", "question",
        # "instruction", ...) despite the schema. Map any alias onto `query` so the
        # vision model always receives the intended focus text.
        _alias_map = {
            "prompt": "query",
            "prompt_text": "query",
            "question": "query",
            "instruction": "query",
            "instructions": "query",
            "focus": "query",
            "request": "query",
            "force_raw": "raw",
        }
        _canonical: dict = {}
        for _k in list(kwargs.keys()):
            _target = _alias_map.get(str(_k).strip().lower())
            if _target:
                _canonical.setdefault(_target, kwargs.pop(_k))
        if not self.query:
            _alias_q = _canonical.get("query")
            if isinstance(_alias_q, str) and _alias_q.strip():
                self.query = _alias_q.strip()
        if not self._raw:
            _alias_r = _canonical.get("raw")
            if isinstance(_alias_r, bool):
                self._raw = _alias_r
            elif isinstance(_alias_r, str) and _alias_r.strip().lower() in ("true", "1", "yes"):
                self._raw = True

        # --- Phase 1: tolerant coerce paths ---
        coerce = paths
        if isinstance(coerce, str):
            s = coerce.strip()
            if not s:
                coerce = []
            elif s.startswith("["):
                # handle LLM/harness mistakenly sending JSON-encoded array as string
                try:
                    import json as _json
                    parsed = _json.loads(s)
                    if isinstance(parsed, list):
                        coerce = parsed
                    else:
                        coerce = [s]
                except Exception:
                    # fallback: try single-quoted / python literal
                    try:
                        import ast as _ast
                        parsed = _ast.literal_eval(s)
                        if isinstance(parsed, list):
                            coerce = parsed
                        else:
                            coerce = [s]
                    except Exception:
                        coerce = [s]
            elif (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                # harness double-quoted a single path: "...png" -> strip outer quotes
                coerce = [s[1:-1].strip()]
            else:
                coerce = [s]
        elif isinstance(coerce, (list, tuple)):
            # keep as is, will stringify elements later
            coerce = list(coerce)
        elif coerce is None:
            coerce = []
        else:
            self._arg_error = (
                f"vision_load error: `paths` must be a list of strings, e.g. {{\"paths\": [\"/a.png\"]}} — got {type(paths).__name__}. "
                f"Use an array even for one image."
            )
            return Response(message="dummy", break_loop=False)

        # Normalize elements to strings
        try:
            # strip per-element surrounding quotes (defensive)
            def _strip_outer_q(v: str) -> str:
                v = v.strip()
                if len(v) >= 2 and ((v[0]=='"' and v[-1]=='"') or (v[0]=="\'" and v[-1]=="\'")):
                    return v[1:-1].strip()
                return v
            paths_list = [_strip_outer_q(str(p or "")) for p in coerce]
        except Exception as e:
            self._arg_error = f"vision_load error: invalid `paths` value: {e}"
            return Response(message="dummy", break_loop=False)

        max_embeds = self._get_max_embeds()
        requested = [
            (str(path or "").strip(), self._display_input_path(str(path or "").strip(), idx + 1))
            for idx, path in enumerate(paths_list)
        ]
        limited_paths = requested if max_embeds <= 0 else requested[-max_embeds:]
        self.skipped_paths = (
            [display for _, display in requested[:-max_embeds]]
            if max_embeds > 0 and len(requested) > max_embeds
            else []
        )

        for idx, (path, display_path) in enumerate(limited_paths):
            if not path:
                continue
            if ephemeral_images.is_ref(path):
                image = ephemeral_images.consume_image(path, context_id=self._context_id())
                if image is None:
                    continue
                display = image.display_name or display_path
                stored_ref = self._store_ephemeral_image(image)
                if stored_ref:
                    self.images_dict[display] = stored_ref
                    self.loaded_paths.append(display)
                continue
            if self._is_data_image_url(path):
                stored_ref = self._store_data_url(path, preferred_name=f"vision-load-{idx + 1}.png")
                if stored_ref:
                    self.images_dict[display_path] = stored_ref
                    self.loaded_paths.append(display_path)
                continue
            if not await runtime.call_development_function(files.exists, str(path)):
                continue
            if path not in self.images_dict:
                mime_type, _ = guess_type(str(path))
                if mime_type and mime_type.startswith("image/"):
                    try:
                        stored_ref = self._store_local_image(path, preferred_name=files.basename(path))
                        self.images_dict[display_path] = stored_ref
                        self.loaded_paths.append(display_path)
                    except (FileNotFoundError, OSError, ValueError):
                        continue

        # --- Phase 2: delegated vision model call (if configured and not raw) ---
        # We defer the actual LLM call to after_execution to keep execute fast,
        # but we can also do it here. Doing it in after_execution preserves
        # the original history injection pattern. So just mark intent here.
        # The actual call happens in after_execution when we know images_dict.
        return Response(message="dummy", break_loop=False)

    def _get_max_embeds(self) -> int:
        # Prefer the effective (preset-aware) chat config; fall back to raw plugin config.
        try:
            from plugins._model_config.helpers.model_config import get_chat_model_config
            chat_cfg = get_chat_model_config(self.agent) or {}
        except Exception:
            cfg = plugins.get_plugin_config("_model_config", agent=self.agent) or {}
            chat_cfg = cfg.get("chat_model", {}) or {}
        try:
            return int(chat_cfg.get("max_embeds", 10) or 0)
        except Exception:
            return 10

    def _main_has_vision(self) -> bool:
        # Whether the *main* chat model accepts image content. Injected image_url
        # blocks must never reach a text-only provider (400 "content.type invalid").
        try:
            from plugins._model_config.helpers.model_config import get_chat_model_config
            return bool(get_chat_model_config(self.agent).get("vision", False))
        except Exception:
            try:
                cfg = plugins.get_plugin_config("_model_config", agent=self.agent) or {}
                return bool((cfg.get("chat_model", {}) or {}).get("vision", False))
            except Exception:
                return False

    def _update_log(self, message: str) -> None:
        # Write the "Result" row (kvps) of the tool's log item — including inside
        # `parallel` workers. The parent's _update_parallel_child_log only writes
        # the plain body text (`content=`) of the same item; it never sets the
        # `result` row, so skipping this write would lose the Result row entirely.
        try:
            self.log.update(result=message)
        except Exception:
            pass

    def _context_id(self) -> str:
        return str(getattr(getattr(self.agent, "context", None), "id", "") or "").strip()

    def _store_ephemeral_image(self, image: ephemeral_images.EphemeralImage) -> str:
        context_id = self._context_id()
        if not context_id:
            return image.data_url
        source = chat_media.infer_source(image.ref, image.display_name)
        category = chat_media.category_for_source(source)
        saved = chat_media.save_image_base64(
            context_id=context_id,
            data=image.data,
            mime_type=image.mime,
            category=category,
            source=source,
            preferred_name=image.display_name,
        )
        return saved.a0_path

    def _store_data_url(self, data_url: str, *, preferred_name: str = "") -> str:
        context_id = self._context_id()
        if not context_id:
            return data_url
        source = chat_media.infer_source(data_url, preferred_name)
        category = chat_media.category_for_source(source)
        saved = chat_media.save_image_data_url(
            context_id=context_id,
            data_url=data_url,
            category=category,
            source=source,
            preferred_name=preferred_name,
        )
        return saved.a0_path

    def _store_local_image(self, path: str, *, preferred_name: str = "") -> str:
        context_id = self._context_id()
        if not context_id:
            return images.to_data_url(path)
        return chat_media.materialize_image_ref(
            context_id=context_id,
            url=path,
            source=chat_media.infer_source(path, preferred_name),
            preferred_name=preferred_name,
        )

    @staticmethod
    def _is_data_image_url(value: str) -> bool:
        normalized = str(value or "").strip().lower()
        return normalized.startswith("data:image/") and ";base64," in normalized

    @classmethod
    def _display_input_path(cls, value: str, index: int) -> str:
        if ephemeral_images.is_ref(value):
            return ephemeral_images.display_ref(value)
        if cls._is_data_image_url(value):
            prefix = value.split(",", 1)[0]
            return f"{prefix},<ephemeral-image-{index}>"
        return value

    async def before_execution(self, **kwargs):
        # Vision Sidecar: the focus argument is named `query`. Some models send a
        # differently-named key ("Prompt", "question", ...) despite the schema — fold
        # any alias into `query` in the logged args so the user sees exactly one row,
        # and always show the Query row in delegated mode even when it was omitted.
        try:
            if not isinstance(self.args, dict):
                self.args = dict(self.args or {})
            aliases = ("prompt", "prompt_text", "question", "instruction", "instructions", "focus", "request")
            alias_value = ""
            for key in list(self.args.keys()):
                if str(key).strip().lower() in aliases:
                    val = self.args.pop(key)
                    if isinstance(val, str) and val.strip() and not alias_value:
                        alias_value = val.strip()
            if not self.args.get("query"):
                from usr.plugins.vision_sidecar.helpers.vision_model import has_vision_model
                if has_vision_model(self.agent):
                    self.args["query"] = alias_value
            elif alias_value and not str(self.args.get("query") or "").strip():
                self.args["query"] = alias_value
        except Exception:
            pass
        await super().before_execution(**kwargs)

    async def after_execution(self, response: Response, **kwargs):
        # Handle arg error first: return as tool_result error (not raise)
        if getattr(self, "_arg_error", None):
            msg = self._arg_error
            lid = getattr(getattr(self, 'log', None), 'id', '') or ''
            self.agent.hist_add_tool_result(self.name, msg, id=lid)
            response.message = msg  # authoritative result: parallel workers return response.message
            PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: Response from tool '{self.name}'"
            )
            PrintStyle(font_color="#E74C3C").print(msg)
            self._update_log(msg)
            return

        content = []
        loaded_count = len(self.loaded_paths)
        skipped_count = len(self.skipped_paths)
        loaded_summary = "\n".join(self.loaded_paths) if self.loaded_paths else "none"
        skipped_summary = "\n".join(self.skipped_paths) if self.skipped_paths else "none"
        summary = (
            f"Loaded images ({loaded_count}):\n{loaded_summary}\n\n"
            f"Skipped images ({skipped_count}, max {self._get_max_embeds()} loaded at a time according to model configuration):\n{skipped_summary}"
        )

        # Determine delegation. `raw=true` is honored only when the main model can
        # actually receive images; on a text-only main raw injection is impossible,
        # so we delegate to the Vision Model instead of leaking image blocks.
        main_has_vision = self._main_has_vision()
        should_delegate = False
        if self.images_dict and (not getattr(self, "_raw", False) or not main_has_vision):
            try:
                from usr.plugins.vision_sidecar.helpers.vision_model import has_vision_model, call_vision_model, get_behaviour
                if has_vision_model(self.agent):
                    should_delegate = True
            except Exception:
                should_delegate = False

        if should_delegate:
            # Delegated path: query + images -> vision model -> text capsule
            # No RawMessage injection -> saves ~1500 tok/image on main context
            try:
                from usr.plugins.vision_sidecar.helpers.vision_model import call_vision_model, get_behaviour
                behaviour = get_behaviour(self.agent)
                # images_dict values are a0_path strings
                a0_paths = list(self.images_dict.values())
                capsule = await call_vision_model(
                    self.agent,
                    a0_paths,
                    getattr(self, "query", ""),
                    timeout=behaviour["timeout"],
                )
                self._delegated_capsule = (capsule or "").strip()
                self._is_delegated = True
            except Exception as e:
                self._delegation_error = str(e)[:2000]
                self._is_delegated = False

        if getattr(self, "_is_delegated", False) and self._delegated_capsule is not None:
            # Success delegated — stock-like one-liner: counts + Description
            flat = " ".join(self._delegated_capsule.split())
            message = (
                f"{loaded_count} images sent, {skipped_count} images skipped"
                f' - Description: "{flat}"'
            )
            lid = getattr(getattr(self, 'log', None), 'id', '') or ''
            self.agent.hist_add_tool_result(self.name, message, id=lid)
            response.message = message  # authoritative result: parallel workers return response.message
            # Inject RawMessage thumbnails for UI parity with native vision when the
            # main preset declares vision support. The flag is the user's declaration
            # and governs: if it mislabels a text-only provider, the resulting provider
            # error is a configuration issue the user owns — the capsule still carries
            # the answer in the meantime. (Deliberate design decision, restored 0.7.7.)
            if self.images_dict and main_has_vision:
                content = []
                for path, image_path in self.images_dict.items():
                    if image_path:
                        content.append({"type": "image_url", "image_url": {"url": image_path}})
                    else:
                        content.append({"type": "text", "text": "Error processing image " + path})
                msg = history.RawMessage(raw_content=content, preview="<Image attachments loaded by path>")
                self.agent.hist_add_message(False, content=msg, tokens=TOKENS_ESTIMATE * len(content))
            PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: Response from tool '{self.name}'"
            )
            PrintStyle(font_color="#85C1E9").print(message)
            self._update_log(message)
            return

        if getattr(self, "_delegation_error", None):
            # Delegation failed — surface error but do NOT inject images (main has no vision)
            combined = (
                summary
                + f"\n\n[Vision model error: {self._delegation_error}]\n"
                + "Tip: check Vision Sidecar Vision Model settings (provider/name/api_key) or retry with raw=true to inject images directly."
            )
            lid = getattr(getattr(self, 'log', None), 'id', '') or ''
            self.agent.hist_add_tool_result(self.name, combined, id=lid)
            message = f"Vision model error — {self._delegation_error[:200]}"
            response.message = message  # authoritative result: parallel workers return response.message
            PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(
                f"{self.agent.agent_name}: Response from tool '{self.name}'"
            )
            PrintStyle(font_color="#E74C3C").print(message)
            self._update_log(message)
            return

        # Legacy / raw / no vision_model path: inject images as RawMessage
        if self.images_dict and main_has_vision:
            lid = getattr(getattr(self, 'log', None), 'id', '') or ''
            self.agent.hist_add_tool_result(self.name, summary, id=lid)
            for path, image_path in self.images_dict.items():
                if image_path:
                    content.append({"type": "image_url", "image_url": {"url": image_path}})
                else:
                    content.append({"type": "text", "text": "Error processing image " + path})
            msg = history.RawMessage(raw_content=content, preview="<Image attachments loaded by path>")
            self.agent.hist_add_message(False, content=msg, tokens=TOKENS_ESTIMATE * len(content))
        elif self.images_dict:
            # No vision anywhere (no Vision Model, main has no vision): never inject
            # image blocks a text-only provider would reject.
            lid = getattr(getattr(self, 'log', None), 'id', '') or ''
            self.agent.hist_add_tool_result(
                self.name,
                summary
                + "\n\n[Images not injected: the main model has no vision and no Vision Model is configured for delegation.]",
                id=lid,
            )
        else:
            lid2 = getattr(getattr(self, 'log', None), 'id', '') or ''
            self.agent.hist_add_tool_result(
                self.name, summary if self.skipped_paths else "No images processed", id=lid2
            )

        message = (
            "No images processed"
            if not self.images_dict and not self.skipped_paths
            else f"{loaded_count} images loaded, {skipped_count} skipped"
        )
        response.message = message  # authoritative result: parallel workers return response.message
        PrintStyle(font_color="#1B4F72", background_color="white", padding=True, bold=True).print(
            f"{self.agent.agent_name}: Response from tool '{self.name}'"
        )
        PrintStyle(font_color="#85C1E9").print(message)
        self._update_log(message)
