from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import threading
import unicodedata
from collections import OrderedDict
from contextlib import contextmanager, nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any

from .contracts import make_cursor, parse_cursor, resolve_candidate, validate_limit
from .doctor import HistoryDoctor
from .initializer import HistoryInitializer
from .read_generation import ReadGenerationStore
from .snapshot_store import ConversationSnapshotStore


class HistoryService:
    _RECORD_COLUMNS = ["message_id", "timestamp", "sender_name", "type", "text"]
    _NON_TEXT_MARKERS = {
        "image": "[图片]",
        "voice": "[语音]",
        "video": "[视频]",
        "sticker": "[表情]",
        "contact_card": "[名片]",
        "location": "[位置]",
        "app_or_file": "[文件]",
        "call": "[通话]",
        "system": "[系统消息]",
        "recalled": "[撤回]",
    }

    def __init__(self, backend: Any, exporter: Any, *, state_root: Any = None):
        self.backend = backend
        self.exporter = exporter
        self.state_root = state_root
        self._lock = threading.RLock()
        self._result_cache: OrderedDict[tuple[str, str, str], dict[str, Any]] = OrderedDict()
        self._result_cache_limit = 64
        generation_root = state_root
        if generation_root is None:
            backend_paths = getattr(self.backend, "paths", None)
            generation_root = getattr(backend_paths, "root", None)
        if generation_root is None:
            generation_root = Path(tempfile.mkdtemp(prefix="wechat-history-reader-state-"))
        self._read_generation = ReadGenerationStore(generation_root)
        self._read_epoch = self._read_generation.load()
        self.snapshot_store = ConversationSnapshotStore(self._snapshot_root(state_root))

    def _sync_read_epoch(self) -> None:
        self._read_epoch = self._read_generation.load()

    def _bump_read_epoch(self) -> int:
        self._read_epoch = self._read_generation.bump()
        return self._read_epoch

    def _snapshot_root(self, state_root: Any) -> Path:
        if state_root is not None:
            return Path(state_root) / "snapshots"
        backend_paths = getattr(self.backend, "paths", None)
        backend_root = getattr(backend_paths, "root", None)
        if backend_root is not None:
            return Path(backend_root) / "snapshots"
        return Path(tempfile.gettempdir()) / "WeChatHistoryReader" / "snapshots"

    def configure_history(self, db_dir: str = "", *, discover: bool = False) -> dict[str, Any]:
        with self._lock:
            result = HistoryInitializer(self.backend, self.state_root).initialize(
                db_dir=db_dir,
                discover=discover,
            )
            self._result_cache.clear()
            self._bump_read_epoch()
            return result

    def check_history(self, *, process_probe: Any = None) -> dict[str, Any]:
        with self._lock:
            kwargs = {}
            if process_probe is not None:
                kwargs["process_probe"] = process_probe
            return HistoryDoctor(self.backend, self.state_root, **kwargs).check()

    def _prepare(self, **kwargs: Any) -> dict[str, Any]:
        snapshot = self.backend.prepare(**kwargs)
        if snapshot.get("cache_status") == "refreshed":
            self._result_cache.clear()
            source_signature = str(snapshot.get("source_signature") or "")
            if source_signature:
                self._read_generation.observe_source(source_signature)
                self._sync_read_epoch()
        return snapshot

    @staticmethod
    def _cache_key(
        scope: str,
        params: dict[str, Any],
        snapshot: dict[str, Any],
        epoch: int,
    ) -> tuple[str, str, str]:
        source = str(snapshot.get("source_signature") or snapshot.get("snapshot_at") or "")
        source = f"{source}:{epoch}"
        encoded = json.dumps(
            params,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        return scope, source, encoded

    def _cached(
        self,
        key: tuple[str, str, str],
        callback: Any,
    ) -> dict[str, Any]:
        cached = self._result_cache.get(key)
        if cached is not None:
            self._result_cache.move_to_end(key)
            return copy.deepcopy(cached)
        result = callback()
        self._result_cache[key] = copy.deepcopy(result)
        self._result_cache.move_to_end(key)
        while len(self._result_cache) > self._result_cache_limit:
            self._result_cache.popitem(last=False)
        return result

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        value = str(mode or "compact").strip().casefold()
        if value not in {"compact", "records"}:
            raise ValueError("mode must be compact or records")
        return value

    @staticmethod
    def _chat_kind(chat: dict[str, Any]) -> str:
        if bool(chat.get("is_group")) or "@chatroom" in str(chat.get("id", "")):
            return "group"
        return "direct"

    @classmethod
    def _chat_descriptor(cls, chat: dict[str, Any]) -> dict[str, Any]:
        descriptor = {
            "chat_id": str(chat.get("id", "")),
            "display_name": str(
                chat.get("display_name") or chat.get("id") or ""
            ),
            "kind": cls._chat_kind(chat),
        }
        if chat.get("member_count") is not None:
            descriptor["member_count"] = chat["member_count"]
        return descriptor

    @staticmethod
    def _format_time(message: dict[str, Any]) -> str:
        value = message.get("timestamp")
        if isinstance(value, str) and value.strip():
            try:
                normalized = value.strip()
                if normalized.endswith(("Z", "z")):
                    normalized = normalized[:-1] + "+00:00"
                parsed = datetime.fromisoformat(normalized)
                return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        timestamp_unix = message.get("timestamp_unix")
        try:
            return datetime.fromtimestamp(int(timestamp_unix)).astimezone().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except (TypeError, ValueError, OSError):
            return str(value or "")

    @classmethod
    def _compact_text(cls, message: dict[str, Any]) -> str:
        message_type = str(message.get("type") or "").casefold()
        if message_type in cls._NON_TEXT_MARKERS:
            return cls._NON_TEXT_MARKERS[message_type]
        text = message.get("text")
        if text is None:
            return ""
        return str(text)

    @staticmethod
    def _direct_role(message: dict[str, Any]) -> str:
        values = {
            str(message.get("sender_name") or "").strip().casefold(),
            str(message.get("sender_id") or "").strip().casefold(),
        }
        return "me" if values & {"me", "self", "我", "自己"} else "other"

    @classmethod
    def _compact_row(
        cls,
        message: dict[str, Any],
        *,
        kind: str,
        across_chats: bool = False,
    ) -> list[str]:
        timestamp = cls._format_time(message)
        text = cls._compact_text(message)
        is_group = kind == "group" or bool(message.get("is_group"))
        sender = str(
            message.get("sender_name")
            or message.get("sender_id")
            or ""
        )
        if across_chats:
            chat = str(message.get("chat_name") or message.get("chat_id") or "")
            speaker = sender if is_group else cls._direct_role(message)
            return [timestamp, chat, speaker, text]
        if kind == "group":
            return [timestamp, sender, text]
        return [timestamp, cls._direct_role(message), text]

    @classmethod
    def _record_message(
        cls,
        message: dict[str, Any],
        *,
        include_raw_content: bool,
        include_chat: bool = False,
    ) -> dict[str, Any]:
        record = {
            field: message.get(field, "")
            for field in cls._RECORD_COLUMNS
        }
        if include_chat:
            record["chat"] = str(
                message.get("chat_name") or message.get("chat_id") or ""
            )
        if include_raw_content:
            record["raw_content"] = message.get("raw_content", "")
        return record

    @staticmethod
    def _columns(
        *,
        mode: str,
        kind: str,
        include_raw_content: bool,
        across_chats: bool = False,
    ) -> list[str]:
        if mode == "compact":
            if across_chats:
                return ["time", "chat", "speaker", "text"]
            if kind == "group":
                return ["time", "sender", "text"]
            return ["time", "role", "text"]
        columns = list(HistoryService._RECORD_COLUMNS)
        if across_chats:
            columns.insert(0, "chat")
        if include_raw_content:
            columns.append("raw_content")
        return columns

    @staticmethod
    def _cursor_binding(scope: str, values: dict[str, Any]) -> str:
        encoded = json.dumps(
            {"scope": scope, **values},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _validate_live_cursor(
        self,
        cursor: dict[str, Any] | None,
        *,
        snapshot: dict[str, Any],
        scope: str,
        binding: str,
    ) -> None:
        if cursor is None:
            return
        context = cursor.get("context")
        if not isinstance(context, dict):
            raise ValueError("cursor is not compatible with this 2.0 read")
        expected_source = str(
            snapshot.get("source_signature") or snapshot.get("snapshot_at") or ""
        )
        if (
            context.get("scope") != scope
            or context.get("binding") != binding
            or context.get("source_signature") != expected_source
            or context.get("epoch") != self._read_epoch
        ):
            raise ValueError("cursor is stale or belongs to another read")

    def _ensure_cursor_source_current(
        self,
        cursor: dict[str, Any] | None,
        snapshot: dict[str, Any],
    ) -> None:
        if cursor is None:
            return
        checker = getattr(self.backend, "snapshot_is_current", None)
        if not callable(checker):
            return
        try:
            current = bool(checker(snapshot))
        except Exception as exc:
            self._result_cache.clear()
            self._bump_read_epoch()
            raise ValueError(
                "could not verify the source; refresh_history and start a new read"
            ) from exc
        if not current:
            self._result_cache.clear()
            self._bump_read_epoch()
            raise ValueError(
                "source changed during pagination; refresh_history and start a new read"
            )

    def _next_cursor(
        self,
        messages: list[dict[str, Any]],
        has_more: bool,
        *,
        snapshot: dict[str, Any],
        scope: str,
        binding: str,
    ) -> str:
        if not has_more or not messages:
            return ""
        oldest = messages[0]
        source_db = oldest.get("source_db")
        if not source_db:
            source_db = str(oldest["message_id"]).rsplit(":", 1)[0]
        source_signature = str(
            snapshot.get("source_signature") or snapshot.get("snapshot_at") or ""
        )
        return make_cursor(
            {
                "timestamp_unix": oldest["timestamp_unix"],
                "source_db": source_db,
                "local_id": oldest["local_id"],
            },
            context={
                "binding": binding,
                "epoch": self._read_epoch,
                "scope": scope,
                "source_signature": source_signature,
            },
        )

    def _resolve_chat(
        self,
        query: str,
        *,
        member_count: int | None,
        min_member_count: int | None,
    ) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]]]:
        if not query or not query.strip():
            raise ValueError("chat must not be empty")
        candidates = list(
            self.backend.find_chat_candidates(
                query.strip(),
                chat_kind="any",
                member_count=member_count,
                min_member_count=min_member_count,
            )
        )
        query_key = self._identity_key(query)
        exact = [
            candidate
            for candidate in candidates
            if query_key
            and any(
                query_key == self._identity_key(candidate.get(field, ""))
                for field in ("id", "display_name", "nick_name", "remark")
            )
        ]
        if exact:
            candidates = exact
        return resolve_candidate(
            candidates,
            member_count=member_count,
            min_member_count=min_member_count,
        )

    @staticmethod
    def _identity_key(value: Any) -> str:
        normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
        return "".join(
            character
            for character in normalized
            if not character.isspace()
            and not unicodedata.category(character).startswith(("P", "S"))
        )

    @staticmethod
    def _resolution_error(
        status: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result = {
            "status": status,
            "count": 0,
            "has_more": False,
            "next_cursor": "",
            "error": (
                "Multiple conversations match; use find_conversations to choose a chat_id."
                if status == "ambiguous"
                else "No matching conversation was found."
            ),
        }
        if candidates:
            result["conversations"] = [
                HistoryService._chat_descriptor(candidate)
                for candidate in candidates
            ]
        return result

    def find_conversations(
        self,
        query: str,
        *,
        limit: int = 20,
        chat_kind: str = "any",
        member_count: int | None = None,
        min_member_count: int | None = None,
    ) -> dict[str, Any]:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        page_size = validate_limit(limit)
        if chat_kind not in {"any", "direct", "group"}:
            raise ValueError("chat_kind must be any, direct, or group")
        with self._lock:
            self._prepare()
            candidates = self.backend.find_chat_candidates(
                query.strip(),
                chat_kind=chat_kind,
                member_count=member_count,
                min_member_count=min_member_count,
            )[:page_size]
            conversations = [
                self._chat_descriptor(candidate) for candidate in candidates
            ]
            return {
                "status": "ok",
                "query": query.strip(),
                "chat_kind": chat_kind,
                "conversations": conversations,
                "count": len(conversations),
            }

    def refresh_history(self) -> dict[str, Any]:
        with self._lock:
            snapshot = self._prepare(force=True)
            self._result_cache.clear()
            self._bump_read_epoch()
            return {
                "status": "ok",
                "refreshed_at": snapshot.get("snapshot_at", ""),
            }

    @contextmanager
    def _fixed_read(self, *, refresh: bool):
        snapshot = self._prepare(force=True) if refresh else self._prepare(reuse=True)
        freeze = getattr(self.backend, "frozen_read", None)
        with freeze(refresh=refresh) if callable(freeze) else nullcontext():
            yield snapshot

    def _snapshot_rows(
        self,
        chat_id: str,
        *,
        start_time: str,
        end_time: str,
        keyword: str,
        kind: str,
    ):
        records = self.backend.iter_chat_records(
            chat_id,
            start_time=start_time,
            end_time=end_time,
            keyword=keyword,
            include_raw_content=False,
        )
        for record in records:
            yield self._compact_row(record, kind=kind)

    def _read_snapshot(
        self,
        snapshot_id: str,
        *,
        cursor: str,
        limit: int,
        mode: str,
        include_raw_content: bool,
        chat: str | None,
        create_snapshot: bool,
        keyword: str,
        start_time: str,
        end_time: str,
    ) -> dict[str, Any]:
        if chat and chat.strip():
            raise ValueError("chat and snapshot_id cannot be used together")
        if create_snapshot:
            raise ValueError("create_snapshot is only valid on the first chat read")
        if keyword or start_time or end_time:
            raise ValueError("snapshot reads cannot change filters")
        if mode != "compact" or include_raw_content:
            raise ValueError("machine snapshots only support compact mode")

        metadata, rows, has_more, next_cursor = self.snapshot_store.read_page(
            snapshot_id,
            cursor=cursor,
            limit=limit,
        )
        kind = str(metadata.get("kind") or "direct")
        columns = list(metadata.get("columns") or [])
        first_page = not bool(cursor)
        result: dict[str, Any] = {
            "status": "ok",
            "rows": rows,
            "count": len(rows),
            "has_more": has_more,
            "next_cursor": next_cursor,
        }
        if first_page:
            result.update(
                {
                    "mode": "compact",
                    "kind": kind,
                    "columns": columns,
                    "chat": metadata.get("chat"),
                    "snapshot_id": snapshot_id,
                }
            )
        return result

    def _create_snapshot(
        self,
        chat: str,
        *,
        refresh: bool,
        limit: int,
        start_time: str,
        end_time: str,
        keyword: str,
        member_count: int | None,
        min_member_count: int | None,
    ) -> dict[str, Any]:
        with self._fixed_read(refresh=refresh) as snapshot:
            status, selected, candidates = self._resolve_chat(
                chat,
                member_count=member_count,
                min_member_count=min_member_count,
            )
            if status != "ok":
                return self._resolution_error(status, candidates)
            assert selected is not None
            kind = self._chat_kind(selected)
            metadata = {
                "chat": self._chat_descriptor(selected),
                "columns": self._columns(
                    mode="compact", kind=kind, include_raw_content=False
                ),
                "filters": {
                    "end_time": end_time,
                    "keyword": keyword,
                    "start_time": start_time,
                },
                "kind": kind,
                "mode": "compact",
                "source_signature": str(snapshot.get("source_signature") or ""),
            }
            created_id, _ = self.snapshot_store.create(
                metadata=metadata,
                rows=self._snapshot_rows(
                    str(selected["id"]),
                    start_time=start_time,
                    end_time=end_time,
                    keyword=keyword,
                    kind=kind,
                ),
            )
        return self._read_snapshot(
            created_id,
            cursor="",
            limit=limit,
            mode="compact",
            include_raw_content=False,
            chat=None,
            create_snapshot=False,
            keyword="",
            start_time="",
            end_time="",
        )

    def read_conversation(
        self,
        chat: str | None = None,
        *,
        snapshot_id: str = "",
        limit: int = 100,
        cursor: str = "",
        keyword: str = "",
        start_time: str = "",
        end_time: str = "",
        mode: str = "compact",
        include_raw_content: bool = False,
        create_snapshot: bool = False,
        member_count: int | None = None,
        min_member_count: int | None = None,
        refresh: bool = True,
    ) -> dict[str, Any]:
        page_size = validate_limit(limit)
        mode = self._normalize_mode(mode)
        snapshot_key = str(snapshot_id or "").strip()
        chat_value = str(chat or "").strip()
        if mode == "compact" and include_raw_content:
            raise ValueError("include_raw_content=true requires mode=records")
        if snapshot_key:
            return self._read_snapshot(
                snapshot_key,
                cursor=cursor,
                limit=page_size,
                mode=mode,
                include_raw_content=include_raw_content,
                chat=chat_value,
                create_snapshot=create_snapshot,
                keyword=keyword,
                start_time=start_time,
                end_time=end_time,
            )
        if not chat_value:
            raise ValueError("chat or snapshot_id is required")
        if create_snapshot and cursor:
            raise ValueError("create_snapshot cannot be combined with cursor")
        if create_snapshot and mode != "compact":
            raise ValueError("create_snapshot only supports mode=compact")

        parsed_cursor = parse_cursor(cursor)
        with self._lock:
            self._sync_read_epoch()
            if create_snapshot:
                return self._create_snapshot(
                    chat_value,
                    refresh=refresh,
                    limit=page_size,
                    start_time=start_time,
                    end_time=end_time,
                    keyword=keyword,
                    member_count=member_count,
                    min_member_count=min_member_count,
                )
            snapshot = self._prepare()
            status, selected, candidates = self._resolve_chat(
                chat_value,
                member_count=member_count,
                min_member_count=min_member_count,
            )
            if status != "ok":
                return self._resolution_error(status, candidates)
            assert selected is not None
            kind = self._chat_kind(selected)
            binding = self._cursor_binding(
                "conversation",
                {
                    "chat_id": selected.get("id", ""),
                    "end_time": end_time,
                    "include_raw_content": include_raw_content,
                    "keyword": keyword,
                    "mode": mode,
                    "start_time": start_time,
                },
            )
            self._validate_live_cursor(
                parsed_cursor,
                snapshot=snapshot,
                scope="conversation",
                binding=binding,
            )
            self._ensure_cursor_source_current(parsed_cursor, snapshot)

            params = {
                "chat_id": selected.get("id", ""),
                "chat_value": chat_value,
                "cursor": cursor,
                "end_time": end_time,
                "include_raw_content": include_raw_content,
                "keyword": keyword,
                "limit": page_size,
                "member_count": member_count,
                "min_member_count": min_member_count,
                "mode": mode,
                "start_time": start_time,
            }
            key = self._cache_key("conversation", params, snapshot, self._read_epoch)

            def build() -> dict[str, Any]:
                messages, has_more = self.backend.read_chat_records(
                    str(selected["id"]),
                    limit=page_size,
                    before=parsed_cursor,
                    keyword=keyword,
                    start_time=start_time,
                    end_time=end_time,
                    include_raw_content=mode == "records" and include_raw_content,
                )
                continuation = bool(cursor)
                result: dict[str, Any] = {
                    "status": "ok",
                    "count": len(messages),
                    "has_more": has_more,
                    "next_cursor": self._next_cursor(
                        messages,
                        has_more,
                        snapshot=snapshot,
                        scope="conversation",
                        binding=binding,
                    ),
                }
                if mode == "compact":
                    result["rows"] = [
                        self._compact_row(message, kind=kind) for message in messages
                    ]
                else:
                    result["messages"] = [
                        self._record_message(
                            message,
                            include_raw_content=include_raw_content,
                        )
                        for message in messages
                    ]
                if not continuation:
                    result.update(
                        {
                            "mode": mode,
                            "kind": kind,
                            "columns": self._columns(
                                mode=mode,
                                kind=kind,
                                include_raw_content=include_raw_content,
                            ),
                            "chat": self._chat_descriptor(selected),
                        }
                    )
                return result

            return self._cached(key, build)

    def read_recent_across_chats(
        self,
        *,
        limit: int = 100,
        cursor: str = "",
        keyword: str = "",
        start_time: str = "",
        end_time: str = "",
        mode: str = "compact",
        include_raw_content: bool = False,
    ) -> dict[str, Any]:
        page_size = validate_limit(limit)
        mode = self._normalize_mode(mode)
        if mode == "compact" and include_raw_content:
            raise ValueError("include_raw_content=true requires mode=records")
        parsed_cursor = parse_cursor(cursor)
        with self._lock:
            self._sync_read_epoch()
            snapshot = self._prepare()
            binding = self._cursor_binding(
                "recent",
                {
                    "end_time": end_time,
                    "include_raw_content": include_raw_content,
                    "keyword": keyword,
                    "mode": mode,
                    "start_time": start_time,
                },
            )
            self._validate_live_cursor(
                parsed_cursor,
                snapshot=snapshot,
                scope="recent",
                binding=binding,
            )
            self._ensure_cursor_source_current(parsed_cursor, snapshot)
            params = {
                "cursor": cursor,
                "end_time": end_time,
                "include_raw_content": include_raw_content,
                "keyword": keyword,
                "limit": page_size,
                "mode": mode,
                "start_time": start_time,
            }
            key = self._cache_key("recent", params, snapshot, self._read_epoch)

            def build() -> dict[str, Any]:
                messages, has_more = self.backend.read_recent_records(
                    limit=page_size,
                    before=parsed_cursor,
                    keyword=keyword,
                    start_time=start_time,
                    end_time=end_time,
                    include_raw_content=mode == "records" and include_raw_content,
                )
                continuation = bool(cursor)
                result: dict[str, Any] = {
                    "status": "ok",
                    "count": len(messages),
                    "has_more": has_more,
                    "next_cursor": self._next_cursor(
                        messages,
                        has_more,
                        snapshot=snapshot,
                        scope="recent",
                        binding=binding,
                    ),
                }
                if mode == "compact":
                    result["rows"] = [
                        self._compact_row(
                            message,
                            kind="group"
                            if bool(message.get("is_group"))
                            or "@chatroom" in str(message.get("chat_id", ""))
                            else "direct",
                            across_chats=True,
                        )
                        for message in messages
                    ]
                else:
                    result["messages"] = [
                        self._record_message(
                            message,
                            include_raw_content=include_raw_content,
                            include_chat=True,
                        )
                        for message in messages
                    ]
                if not continuation:
                    result.update(
                        {
                            "mode": mode,
                            "kind": "recent",
                            "columns": self._columns(
                                mode=mode,
                                kind="recent",
                                include_raw_content=include_raw_content,
                                across_chats=True,
                            ),
                        }
                    )
                return result

            return self._cached(key, build)

    def export_conversation(
        self,
        chat: str,
        *,
        member_count: int | None = None,
        min_member_count: int | None = None,
        start_time: str = "",
        end_time: str = "",
        output_dir: str | None = None,
        refresh: bool = True,
    ) -> dict[str, Any]:
        with self._lock, self._fixed_read(refresh=refresh) as snapshot:
            status, selected, candidates = self._resolve_chat(
                chat,
                member_count=member_count,
                min_member_count=min_member_count,
            )
            if status != "ok":
                return self._resolution_error(status, candidates)
            if self.exporter is None:
                raise RuntimeError("exporter is unavailable")
            assert selected is not None
            return self.exporter.export(
                self.backend,
                selected,
                start_time=start_time,
                end_time=end_time,
                output_dir=output_dir,
                snapshot=snapshot,
            )

    def decode_conversation_image(
        self,
        chat: str,
        message_id: str,
        *,
        member_count: int | None = None,
        min_member_count: int | None = None,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._prepare()
            status, selected, candidates = self._resolve_chat(
                chat,
                member_count=member_count,
                min_member_count=min_member_count,
            )
            if status != "ok":
                return self._resolution_error(status, candidates)
            assert selected is not None
            result = self.backend.decode_image(
                selected["id"],
                message_id,
                output_dir=output_dir,
            )
            result.setdefault("chat", self._chat_descriptor(selected))
            return result
