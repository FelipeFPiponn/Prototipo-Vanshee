"""Motor de Memoria Vectorial Local para Código (Codebase RAG) en V.ANSHEE.

Indexa el código fuente del proyecto en SQLite usando embeddings vectoriales densos con NumPy
(combinando hashing semántico de n-gramas + símbolos AST/regex 100% local en 0ms y síntesis con Gemini/Ollama)
para responder preguntas sobre la arquitectura, funciones, clases y archivos del proyecto.
"""

import os
import re
import json
import math
import sqlite3
import hashlib
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
from config.settings import settings, BASE_DIR
from src.integrations.git_manager import git_manager


CODE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".md", ".json"}
IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    "dist", "build", "data", ".gemini", ".vscode", ".idea", "chat_webview_cache", "wallpaper_webview_cache"
}
EMBED_DIM = 384


def _compute_local_code_embedding(text: str) -> np.ndarray:
    """
    Genera un vector denso normalizado de 384 dimensiones usando Feature Hashing
    sobre tokens de código, camelCase/snake_case y bigramas (100% local, instantáneo, sin servidor externo).
    """
    vec = np.zeros(EMBED_DIM, dtype=np.float32)
    if not text:
        return vec

    # Separar camelCase y snake_case para capturar semántica de identificadores de código
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{1,35}", expanded.lower())
    if not tokens:
        return vec

    for i, tok in enumerate(tokens):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % EMBED_DIM
        sign = 1.0 if (h & (1 << 16)) else -1.0
        # Dar mayor peso a definiciones de clases/funciones e identificadores
        weight = 2.2 if tok in ("class", "def", "function", "async", "interface") else 1.0
        vec[idx] += sign * weight

        if i + 1 < len(tokens):
            bigram = f"{tok}_{tokens[i + 1]}"
            hb = int(hashlib.md5(bigram.encode("utf-8")).hexdigest()[:8], 16)
            vec[hb % EMBED_DIM] += (1.0 if (hb & (1 << 16)) else -1.0) * 0.65

    norm = float(np.linalg.norm(vec))
    if norm > 1e-6:
        vec /= norm
    return vec


class CodebaseRAG:
    """Indexador vectorial local y motor de consulta RAG sobre el repositorio de código."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (BASE_DIR / "data" / "vanshee_code_rag.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS code_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    workspace TEXT,
                    rel_path TEXT,
                    start_line INTEGER,
                    end_line INTEGER,
                    symbols TEXT,
                    content TEXT,
                    file_mtime REAL,
                    embedding BLOB
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_code_ws ON code_chunks(workspace)")
            conn.commit()

    def get_active_workspace(self) -> Path:
        ws = git_manager._resolve_workspace_path()
        if ws and os.path.isdir(ws):
            return Path(ws)
        return BASE_DIR

    def _extract_symbols(self, chunk_text: str) -> List[str]:
        syms = []
        for m in re.finditer(r"^\s*(?:async\s+)?(?:def|class|function|interface|const)\s+([A-Za-z_][A-Za-z0-9_]*)", chunk_text, re.MULTILINE):
            syms.append(m.group(1))
        return syms[:15]

    def index_workspace(self, workspace_dir: Optional[Path] = None, force: bool = False) -> Tuple[bool, str, int]:
        """Escanea e indexa incrementalmente los archivos de código del proyecto."""
        root = workspace_dir or self.get_active_workspace()
        ws_key = str(root.resolve())
        chunks_indexed = 0
        files_scanned = 0

        with sqlite3.connect(self.db_path) as conn:
            existing_mtimes = {}
            if not force:
                rows = conn.execute(
                    "SELECT rel_path, MAX(file_mtime) FROM code_chunks WHERE workspace = ? GROUP BY rel_path",
                    (ws_key,)
                ).fetchall()
                existing_mtimes = {r[0]: float(r[1] or 0.0) for r in rows}

            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
                for fname in filenames:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in CODE_EXTENSIONS:
                        continue
                    fpath = Path(dirpath) / fname
                    try:
                        stat = fpath.stat()
                        if stat.st_size > 350_000:  # Omitir archivos gigantes/minificados
                            continue
                        rel_path = str(fpath.relative_to(root)).replace("\\", "/")
                        mtime = stat.st_mtime
                        if not force and rel_path in existing_mtimes and abs(mtime - existing_mtimes[rel_path]) < 0.5:
                            files_scanned += 1
                            continue

                        text = fpath.read_text(encoding="utf-8", errors="ignore")
                        lines = text.splitlines()
                        if not lines:
                            continue

                        conn.execute("DELETE FROM code_chunks WHERE workspace = ? AND rel_path = ?", (ws_key, rel_path))

                        # Dividir en bloques de ~75 líneas con solapamiento de 15 líneas
                        step = 60
                        window = 75
                        for start in range(0, len(lines), step):
                            end = min(len(lines), start + window)
                            chunk_lines = lines[start:end]
                            chunk_str = "\n".join(chunk_lines)
                            symbols = self._extract_symbols(chunk_str)
                            header = f"File: {rel_path} (Lines {start + 1}-{end}) Symbols: {' '.join(symbols)}\n"
                            full_text = header + chunk_str
                            vec = _compute_local_code_embedding(full_text)
                            chunk_id = f"{ws_key}::{rel_path}::{start + 1}"

                            conn.execute(
                                """
                                INSERT OR REPLACE INTO code_chunks
                                (chunk_id, workspace, rel_path, start_line, end_line, symbols, content, file_mtime, embedding)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    chunk_id,
                                    ws_key,
                                    rel_path,
                                    start + 1,
                                    end,
                                    json.dumps(symbols),
                                    chunk_str[:2400],
                                    mtime,
                                    vec.tobytes()
                                )
                            )
                            chunks_indexed += 1
                        files_scanned += 1
                    except Exception:
                        continue
            conn.commit()

            total_chunks = conn.execute(
                "SELECT COUNT(*) FROM code_chunks WHERE workspace = ?", (ws_key,)
            ).fetchone()[0]

        msg = f"Índice vectorial actualizado para '{root.name}': {files_scanned} archivos escaneados y {total_chunks} bloques de código disponibles en memoria."
        return True, msg, total_chunks

    def search_codebase(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Busca los fragmentos de código más relevantes combinando similitud coseno vectorial y coincidencia de símbolos."""
        root = self.get_active_workspace()
        ws_key = str(root.resolve())

        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM code_chunks WHERE workspace = ?", (ws_key,)).fetchone()[0]
            if count == 0:
                self.index_workspace(root)

            rows = conn.execute(
                "SELECT rel_path, start_line, end_line, symbols, content, embedding FROM code_chunks WHERE workspace = ?",
                (ws_key,)
            ).fetchall()

        if not rows:
            return []

        q_vec = _compute_local_code_embedding(query)
        q_lower = query.lower()
        q_tokens = [t for t in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", q_lower) if t not in {
            "donde", "esta", "como", "funciona", "archivo", "clase", "funcion", "metodo",
            "codigo", "proyecto", "definida", "definido", "para", "sirve", "que", "cual", "del", "las", "los"
        }]

        scored = []
        for rel_path, start_line, end_line, sym_json, content, emb_bytes in rows:
            vec = np.frombuffer(emb_bytes, dtype=np.float32)
            score = float(np.dot(q_vec, vec)) if len(vec) == EMBED_DIM else 0.0

            # Impulso léxico exacto para nombres de clases, funciones o rutas mencionadas
            syms = [s.lower() for s in json.loads(sym_json or "[]")]
            path_lower = rel_path.lower()
            content_lower = content.lower()

            for qt in q_tokens:
                if qt in syms:
                    score += 0.55
                if qt in path_lower:
                    score += 0.40
                if qt in content_lower:
                    score += 0.18

            scored.append({
                "rel_path": rel_path,
                "start_line": start_line,
                "end_line": end_line,
                "symbols": json.loads(sym_json or "[]"),
                "content": content,
                "score": round(score, 4)
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def ask_codebase(self, question: str) -> Tuple[bool, str]:
        """Busca en el índice vectorial del código y sintetiza una respuesta precisa citando archivos y líneas."""
        # Asegurar actualización incremental rápida antes de buscar
        self.index_workspace()
        matches = self.search_codebase(question, top_k=4)
        if not matches:
            return False, "No encontré fragmentos de código en el proyecto actual para responder esa consulta."

        context_blocks = []
        for m in matches:
            syms_str = ", ".join(m["symbols"]) if m["symbols"] else "N/A"
            context_blocks.append(
                f"--- Archivo: {m['rel_path']} (Líneas {m['start_line']}-{m['end_line']}) | Símbolos: {syms_str} ---\n{m['content'][:900]}"
            )
        joined_context = "\n\n".join(context_blocks)

        api_key = (getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")).strip()
        if api_key and getattr(settings, "LLM_PROVIDER", "gemini") != "ollama":
            try:
                primary_model = getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite") or "gemini-3.1-flash-lite"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{primary_model}:generateContent?key={api_key}"
                prompt = (
                    "Eres V.ANSHEE, asistente experta en la arquitectura del proyecto del usuario. "
                    "Responde la pregunta sobre el código en español de forma clara y hablada (2 a 3 oraciones), "
                    "mencionando explícitamente el nombre del archivo y las líneas donde se encuentra.\n\n"
                    f"Pregunta: {question}\n\n"
                    f"Fragmentos recuperados del índice vectorial (RAG):\n{joined_context}"
                )
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 280}
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    candidates = body.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts") or []
                        if parts and parts[0].get("text"):
                            return True, parts[0]["text"].strip()
            except Exception as e:
                print(f"[CodebaseRAG Gemini Warning]: {e}")

        # Respuesta directa determinista si está offline
        top = matches[0]
        syms = ", ".join(top["symbols"][:4]) if top["symbols"] else "el bloque principal"
        return (
            True,
            f"Encontré la coincidencia principal en el archivo {top['rel_path']} "
            f"(entre las líneas {top['start_line']} y {top['end_line']}), donde se define {syms}."
        )


codebase_rag = CodebaseRAG()
