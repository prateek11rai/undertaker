"""Certificates cached in SQLite under the data folder."""

import json
import sqlite3
from pathlib import Path

from undertaker.explain.certificate import Certificate


class CertCache:
    """Key: workflow id, run id, last event id, pending attempt (and model/source)."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS certs (key TEXT PRIMARY KEY, body TEXT)")

    def get(self, key: str) -> Certificate | None:
        """Look up a certificate."""
        row = self.db.execute("SELECT body FROM certs WHERE key = ?", (key,)).fetchone()
        return Certificate(**json.loads(row[0])) if row else None

    def put(self, key: str, cert: Certificate) -> None:
        """Store a certificate."""
        self.db.execute(
            "INSERT OR REPLACE INTO certs VALUES (?, ?)", (key, json.dumps(cert.to_dict()))
        )
        self.db.commit()
