import json
import math
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from config.settings import settings
from src.routines.db import init_db


SPANISH_STOPWORDS = {
    "a", "al", "algo", "como", "con", "de", "del", "el", "en", "es", "esta",
    "este", "la", "las", "lo", "los", "me", "mi", "para", "por", "que", "se",
    "si", "un", "una", "y", "ya",
}


@dataclass
class SemanticMemoryMatch:
    id: int
    text: str
    kind: str
    metadata: dict[str, Any]
    score: float
    importance: float
    success: bool


class SemanticMemory:
    """Memoria semántica liviana para recordar frases parecidas y acciones exitosas."""

    def __init__(self):
        init_db()
        self.db_path = settings.DB_PATH

    def remember(
        self,
        text: str,
        kind: str = "interaction",
        metadata: dict[str, Any] | None = None,
        importance: float = 0.5,
        success: bool = False,
    ) -> int:
        clean_text = text.strip()
        if not clean_text:
            return 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO semantic_memories (text, kind, metadata_json, importance, success)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    clean_text,
                    kind,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    max(0.0, min(1.0, importance)),
                    1 if success else 0,
                ),
            )
            return int(cursor.lastrowid)

    def search(self, query: str, limit: int = 5, min_score: float = 0.12) -> list[SemanticMemoryMatch]:
        query_tokens = self._tokens(query)
        if not query_tokens:
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, text, kind, metadata_json, importance, success
                FROM semantic_memories
                ORDER BY id DESC
                LIMIT 250
                """
            ).fetchall()

        matches: list[SemanticMemoryMatch] = []
        for row in rows:
            memory_tokens = self._tokens(row["text"])
            score = self._score(query_tokens, memory_tokens, float(row["importance"]), bool(row["success"]))
            if score >= min_score:
                matches.append(
                    SemanticMemoryMatch(
                        id=int(row["id"]),
                        text=row["text"],
                        kind=row["kind"],
                        metadata=json.loads(row["metadata_json"] or "{}"),
                        score=score,
                        importance=float(row["importance"]),
                        success=bool(row["success"]),
                    )
                )

        matches.sort(key=lambda item: item.score, reverse=True)
        selected = matches[:limit]
        self._touch([item.id for item in selected])
        return selected

    def summarize_matches(self, query: str, limit: int = 3) -> str:
        matches = self.search(query, limit=limit)
        if not matches:
            return "sin_recuerdos_semanticos"
        return " | ".join(
            f"{match.kind}:{match.text[:120]} (score={match.score:.2f})"
            for match in matches
        )

    def _touch(self, ids: list[int]):
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE semantic_memories SET last_used_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                ids,
            )

    @staticmethod
    def _tokens(text: str) -> dict[str, float]:
        words = re.findall(r"[a-záéíóúñü0-9_]+", text.lower())
        counts: dict[str, float] = {}
        for word in words:
            if len(word) <= 1 or word in SPANISH_STOPWORDS:
                continue
            counts[word] = counts.get(word, 0.0) + 1.0
        return counts

    @staticmethod
    def _score(query: dict[str, float], memory: dict[str, float], importance: float, success: bool) -> float:
        if not query or not memory:
            return 0.0
        common = set(query) & set(memory)
        dot = sum(query[token] * memory[token] for token in common)
        query_norm = math.sqrt(sum(value * value for value in query.values()))
        memory_norm = math.sqrt(sum(value * value for value in memory.values()))
        cosine = dot / (query_norm * memory_norm) if query_norm and memory_norm else 0.0
        overlap = len(common) / max(1, len(set(query)))
        success_boost = 0.08 if success else 0.0
        importance_boost = importance * 0.08
        return min(1.0, (cosine * 0.7) + (overlap * 0.22) + success_boost + importance_boost)
