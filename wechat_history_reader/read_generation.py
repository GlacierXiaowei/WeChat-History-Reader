from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class ReadGenerationStore:
    """Persist live-read invalidation generation across short-lived CLI runs."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.path = self.root / "read-generation.json"

    def _load_state(self) -> dict[str, object]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _write_state(self, state: dict[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + f".{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps(state, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def load(self) -> int:
        value = self._load_state()
        try:
            return max(0, int(value.get("generation", 0)))
        except (TypeError, ValueError):
            return 0

    def observe_source(self, source_signature: str) -> bool:
        """Record a source and bump only when an existing source changes."""
        source_signature = str(source_signature or "")
        if not source_signature:
            return False
        state = self._load_state()
        previous = str(state.get("source_signature", "") or "")
        if previous == source_signature:
            return False
        try:
            generation = max(0, int(state.get("generation", 0)))
        except (TypeError, ValueError):
            generation = 0
        changed = bool(previous)
        state["generation"] = generation + 1 if changed else generation
        state["source_signature"] = source_signature
        self._write_state(state)
        return changed

    def bump(self) -> int:
        generation = self.load() + 1
        state = self._load_state()
        state["generation"] = generation
        self._write_state(state)
        return generation
