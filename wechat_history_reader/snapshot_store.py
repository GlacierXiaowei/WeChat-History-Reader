from __future__ import annotations

import base64
import json
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable


_SNAPSHOT_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _encode_cursor(snapshot_id: str, row_index: int, byte_offset: int) -> str:
    payload = {
        "byte_offset": int(byte_offset),
        "row_index": int(row_index),
        "snapshot_id": snapshot_id,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str, snapshot_id: str) -> tuple[int, int]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(cursor + padding).decode("utf-8")
        )
        if (
            not isinstance(payload, dict)
            or set(payload) != {"byte_offset", "row_index", "snapshot_id"}
            or payload["snapshot_id"] != snapshot_id
            or isinstance(payload["byte_offset"], bool)
            or not isinstance(payload["byte_offset"], int)
            or payload["byte_offset"] < 0
            or isinstance(payload["row_index"], bool)
            or not isinstance(payload["row_index"], int)
            or payload["row_index"] < 0
        ):
            raise ValueError
        return payload["row_index"], payload["byte_offset"]
    except (TypeError, ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid snapshot cursor") from exc


class ConversationSnapshotStore:
    """Persist compact, replayable conversation rows outside the export tree."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    @staticmethod
    def _validate_snapshot_id(snapshot_id: str) -> str:
        value = str(snapshot_id or "").strip().casefold()
        if not _SNAPSHOT_ID_RE.fullmatch(value):
            raise ValueError("invalid snapshot_id")
        return value

    def _directory(self, snapshot_id: str) -> Path:
        return self.root / self._validate_snapshot_id(snapshot_id)

    def create(
        self,
        *,
        metadata: dict[str, Any],
        rows: Iterable[list[Any]],
        validate: Callable[[], bool] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        self.root.mkdir(parents=True, exist_ok=True)
        snapshot_id = uuid.uuid4().hex
        final_dir = self.root / snapshot_id
        temporary_dir = Path(
            tempfile.mkdtemp(prefix=f".{snapshot_id}-", dir=str(self.root))
        )
        row_count = 0
        try:
            rows_path = temporary_dir / "rows.jsonl"
            with rows_path.open("w", encoding="utf-8", newline="\n") as handle:
                for row in rows:
                    if not isinstance(row, list):
                        row = list(row)
                    handle.write(
                        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                    )
                    handle.write("\n")
                    row_count += 1

            saved_metadata = {
                "format_version": 1,
                **metadata,
                "row_count": row_count,
            }
            metadata_path = temporary_dir / "metadata.json"
            metadata_path.write_text(
                json.dumps(
                    saved_metadata,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            if validate is not None and not validate():
                raise RuntimeError("WeChat source changed during snapshot creation.")
            temporary_dir.replace(final_dir)
            return snapshot_id, saved_metadata
        except Exception:
            shutil.rmtree(temporary_dir, ignore_errors=True)
            raise

    def _load_metadata(self, snapshot_id: str) -> tuple[str, Path, dict[str, Any]]:
        snapshot_id = self._validate_snapshot_id(snapshot_id)
        directory = self._directory(snapshot_id)
        try:
            metadata = json.loads(
                (directory / "metadata.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("snapshot is unavailable") from exc
        if not isinstance(metadata, dict) or metadata.get("format_version") != 1:
            raise ValueError("snapshot format is unsupported")
        return snapshot_id, directory, metadata

    def read_page(
        self,
        snapshot_id: str,
        *,
        cursor: str = "",
        limit: int,
    ) -> tuple[dict[str, Any], list[list[Any]], bool, str]:
        snapshot_id, directory, metadata = self._load_metadata(snapshot_id)
        if cursor:
            row_index, byte_offset = _decode_cursor(cursor, snapshot_id)
        else:
            row_index, byte_offset = 0, 0

        row_count = int(metadata.get("row_count", 0))
        if row_index > row_count:
            raise ValueError("snapshot cursor is past the end")

        rows: list[list[Any]] = []
        next_offset = byte_offset
        rows_path = directory / "rows.jsonl"
        try:
            with rows_path.open("r", encoding="utf-8", newline="") as handle:
                handle.seek(byte_offset)
                while len(rows) < limit:
                    line = handle.readline()
                    if not line:
                        break
                    value = json.loads(line)
                    if not isinstance(value, list):
                        raise ValueError("snapshot row is invalid")
                    rows.append(value)
                    next_offset = handle.tell()
                extra = handle.readline()
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("snapshot rows are unavailable") from exc

        has_more = bool(extra)
        next_cursor = (
            _encode_cursor(snapshot_id, row_index + len(rows), next_offset)
            if has_more
            else ""
        )
        return metadata, rows, has_more, next_cursor
