import json
import sqlite3
from dataclasses import asdict, is_dataclass
from typing import Any

from config.settings import settings
from src.routines.db import init_db


class MemoryStore:
    """Memoria persistente del cerebro de V.ANSHEE."""

    def __init__(self):
        init_db()
        self.db_path = settings.DB_PATH

    def remember_fact(self, key: str, value: str, source: str = "brain", confidence: float = 1.0):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO brain_facts (fact_key, fact_value, source, confidence)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fact_key) DO UPDATE SET
                    fact_value = excluded.fact_value,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value, source, confidence),
            )

    def recall_fact(self, key: str, default: str = "") -> str:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT fact_value FROM brain_facts WHERE fact_key = ?",
                (key,),
            ).fetchone()
        return row[0] if row else default

    def recall_recent_interactions(self, limit: int = 5) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT user_text, app_name, window_title, plan_summary, response_text, success, confidence, created_at
                FROM brain_interactions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def recall_context_for_app(self, app_name: str, limit: int = 5) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT user_command, assistant_response, window_title, confidence, created_at
                FROM context_events
                WHERE app_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (app_name, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def log_interaction(
        self,
        user_text: str,
        app_name: str,
        window_title: str,
        plan_summary: str,
        response_text: str,
        success: bool,
        confidence: float = 0.0,
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO brain_interactions (
                    user_text, app_name, window_title, plan_summary, response_text, success, confidence
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_text,
                    app_name,
                    window_title,
                    plan_summary,
                    response_text,
                    1 if success else 0,
                    confidence,
                ),
            )

    def summarize_for_prompt(self, app_name: str = "") -> str:
        facts = self._all_facts()
        recent = self.recall_recent_interactions(limit=3)
        app_context = self.recall_context_for_app(app_name, limit=3) if app_name else []
        payload = {
            "facts": facts,
            "recent_interactions": recent,
            "recent_app_context": app_context,
        }
        return json.dumps(payload, ensure_ascii=False, default=self._json_default)

    def _all_facts(self) -> dict[str, str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT fact_key, fact_value FROM brain_facts").fetchall()
        return {key: value for key, value in rows}

    @staticmethod
    def _json_default(value: Any):
        if is_dataclass(value):
            return asdict(value)
        return str(value)
