"""SQLite persistence for engine-grounded AI advisor interactions."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "riskengine.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            mode TEXT NOT NULL,
            model TEXT,
            context_used TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def save_insight(result: Dict) -> Dict:
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO ai_insights
                (question, answer, mode, model, context_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                result.get("question", ""),
                result.get("answer", ""),
                result.get("mode", "deterministic"),
                result.get("model"),
                json.dumps(result.get("context_used", [])),
                created_at,
            ),
        )
        insight_id = cursor.lastrowid
    return {**result, "id": insight_id, "created_at": created_at}


def list_insights(limit: int = 25) -> List[Dict]:
    limit = max(1, min(limit, 100))
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, question, answer, mode, model, context_used, created_at
            FROM ai_insights
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "question": row["question"],
            "answer": row["answer"],
            "mode": row["mode"],
            "model": row["model"],
            "context_used": json.loads(row["context_used"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]