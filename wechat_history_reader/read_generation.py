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

    def load(self) -> int:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            generation = value.get("generation", 0) if isinstance(value, dict) else 0
            return max(0, int(generation))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return 0

    def bump(self) -> int:
        generation = self.load() + 1
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + f".{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps({"generation": generation}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return generation
