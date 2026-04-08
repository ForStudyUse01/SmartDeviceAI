from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = PROJECT_ROOT / "database"
DB_PATH = DB_DIR / "smartdeviceai.db"


class SQLiteStore:
    def __init__(self) -> None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = DB_PATH
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS inference_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    image_name TEXT,
                    detections_json TEXT,
                    explanation TEXT,
                    model_path TEXT,
                    device TEXT
                )
                """
            )
            conn.commit()

    def log_result(
        self,
        endpoint: str,
        image_name: str,
        detections: list[dict[str, Any]],
        explanation: str | None,
        model_path: str,
        device: str,
    ) -> None:
        payload = json.dumps(detections, ensure_ascii=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO inference_logs
                (created_at, endpoint, image_name, detections_json, explanation, model_path, device)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    endpoint,
                    image_name,
                    payload,
                    explanation,
                    model_path,
                    device,
                ),
            )
            conn.commit()


_STORE: SQLiteStore | None = None


def get_store() -> SQLiteStore:
    global _STORE
    if _STORE is None:
        _STORE = SQLiteStore()
    return _STORE

