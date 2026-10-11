"""Append-only audit trail: output/audit_trail.json (a JSON array of AuditEntry).

Never wipes the file. If the existing file can't be parsed, it is moved aside
(audit_trail.corrupt-<ts>.json) rather than overwritten, and a new array starts.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from models import AuditEntry


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class AuditTrail:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return []
        try:
            data = json.loads(self.path.read_text())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self.path.rename(self.path.with_name(f"audit_trail.corrupt-{stamp}.json"))
        return []

    def append(self, entry: AuditEntry) -> None:
        with self._lock:
            entries = self._load()
            entries.append(entry.model_dump(mode="json"))
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(entries, indent=2, default=str) + "\n")
            tmp.replace(self.path)  # atomic: a crash mid-write never truncates the trail
