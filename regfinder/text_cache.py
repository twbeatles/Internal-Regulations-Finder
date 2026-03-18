# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .app_types import DiscoveredFile, TextCacheSnapshot
from .runtime import logger


@dataclass(frozen=True)
class CachedChunk:
    doc_id: str
    file_key: str
    chunk_idx: int
    text: str
    source: str
    path: str
    mtime: float | None


@dataclass(frozen=True)
class TextCacheReplacement:
    file: DiscoveredFile
    status: str
    chunks: Sequence[CachedChunk]


class TextCacheStore:
    def __init__(self, sqlite_path: str, schema_version: int) -> None:
        self.sqlite_path = sqlite_path
        self.schema_version = int(schema_version)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        os.makedirs(os.path.dirname(self.sqlite_path) or ".", exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            current = self._read_meta(conn, "schema_version")
            if current and int(current) != self.schema_version:
                conn.execute("DROP TABLE IF EXISTS chunks")
                conn.execute("DROP TABLE IF EXISTS files")
                conn.execute("DELETE FROM meta")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    file_key TEXT PRIMARY KEY,
                    rel_path TEXT NOT NULL,
                    abs_path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    doc_id TEXT PRIMARY KEY,
                    file_key TEXT NOT NULL,
                    chunk_idx INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    path TEXT NOT NULL,
                    mtime REAL,
                    FOREIGN KEY(file_key) REFERENCES files(file_key) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_file_key ON files(file_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file_key ON chunks(file_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)")
            self._write_meta(conn, "schema_version", str(self.schema_version))
            if self._read_meta(conn, "revision") is None:
                self._write_meta(conn, "revision", "0")
            if self._read_meta(conn, "updated_at") is None:
                self._write_meta(conn, "updated_at", "")

    def _read_meta(self, conn: sqlite3.Connection, key: str) -> Optional[str]:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def _write_meta(self, conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO meta(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def get_revision(self) -> int:
        with self._connect() as conn:
            raw = self._read_meta(conn, "revision")
        return int(raw or 0)

    def _bump_revision(self, conn: sqlite3.Connection) -> int:
        revision = int(self._read_meta(conn, "revision") or 0) + 1
        now = datetime.now().isoformat(timespec="seconds")
        self._write_meta(conn, "revision", str(revision))
        self._write_meta(conn, "updated_at", now)
        return revision

    def get_files(self) -> Dict[str, Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT file_key, rel_path, abs_path, size, mtime, chunk_count, status, updated_at
                FROM files
                """
            ).fetchall()
        return {
            str(row["file_key"]): {
                "file_key": str(row["file_key"]),
                "rel_path": str(row["rel_path"]),
                "path": str(row["abs_path"]),
                "size": int(row["size"]),
                "mtime": float(row["mtime"]),
                "chunks": int(row["chunk_count"]),
                "status": str(row["status"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        }

    def load_chunks(self) -> List[CachedChunk]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT doc_id, file_key, chunk_idx, text, source, path, mtime
                FROM chunks
                ORDER BY file_key ASC, chunk_idx ASC
                """
            ).fetchall()
        return [
            CachedChunk(
                doc_id=str(row["doc_id"]),
                file_key=str(row["file_key"]),
                chunk_idx=int(row["chunk_idx"]),
                text=str(row["text"]),
                source=str(row["source"]),
                path=str(row["path"]),
                mtime=float(row["mtime"]) if row["mtime"] is not None else None,
            )
            for row in rows
        ]

    def delete_files(self, file_keys: Iterable[str]) -> int:
        keys = [str(key) for key in file_keys if key]
        if not keys:
            return self.get_revision()
        placeholders = ",".join("?" for _ in keys)
        with self._connect() as conn:
            with conn:
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute(f"DELETE FROM chunks WHERE file_key IN ({placeholders})", keys)
                conn.execute(f"DELETE FROM files WHERE file_key IN ({placeholders})", keys)
                return self._bump_revision(conn)

    def replace_files(self, replacements: Sequence[TextCacheReplacement]) -> int:
        if not replacements:
            return self.get_revision()
        with self._connect() as conn:
            with conn:
                conn.execute("PRAGMA foreign_keys=ON")
                now = datetime.now().isoformat(timespec="seconds")
                for replacement in replacements:
                    file = replacement.file
                    conn.execute("DELETE FROM chunks WHERE file_key = ?", (file.file_key,))
                    conn.execute("DELETE FROM files WHERE file_key = ?", (file.file_key,))
                    conn.execute(
                        """
                        INSERT INTO files(
                            file_key, rel_path, abs_path, size, mtime, chunk_count, status, updated_at
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            file.file_key,
                            file.rel_path,
                            file.path,
                            file.size,
                            file.mtime,
                            len(replacement.chunks),
                            replacement.status,
                            now,
                        ),
                    )
                    conn.executemany(
                        """
                        INSERT INTO chunks(doc_id, file_key, chunk_idx, text, source, path, mtime)
                        VALUES(?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                chunk.doc_id,
                                chunk.file_key,
                                chunk.chunk_idx,
                                chunk.text,
                                chunk.source,
                                chunk.path,
                                chunk.mtime,
                            )
                            for chunk in replacement.chunks
                        ],
                    )
                return self._bump_revision(conn)

    def clear(self) -> None:
        if os.path.exists(self.sqlite_path):
            try:
                os.remove(self.sqlite_path)
            except OSError as exc:
                logger.warning(f"텍스트 캐시 삭제 실패: {self.sqlite_path} - {exc}")

    def snapshot(self) -> TextCacheSnapshot:
        with self._connect() as conn:
            revision = int(self._read_meta(conn, "revision") or 0)
            updated_at = self._read_meta(conn, "updated_at")
            cached_files = int(conn.execute("SELECT COUNT(*) FROM files").fetchone()[0])
            cached_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        return TextCacheSnapshot(
            schema_version=self.schema_version,
            revision=revision,
            cached_files=cached_files,
            cached_chunks=cached_chunks,
            sqlite_path=self.sqlite_path,
            updated_at=updated_at or None,
        )
