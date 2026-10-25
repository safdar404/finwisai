"""LLM response caching: in-memory and SQLite.

How it works
------------
`set_llm_cache(cache)` registers ONE global cache. Before every model call,
LangChain builds a key from (prompt, model settings) and looks it up:
* hit  -> the stored answer is returned instantly; no API call, no cost;
* miss -> the model is called and the answer is stored for next time.

InMemoryCache lives in RAM (fastest, gone when the app restarts).
SQLiteCache lives in a .db file on disk (survives restarts, slightly slower).

Cache objects are kept at module level so they survive Streamlit reruns.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.caches import InMemoryCache
from langchain_core.globals import get_llm_cache, set_llm_cache

from .config import CACHE_MEMORY, CACHE_NONE, CACHE_SQLITE, SQLITE_CACHE_PATH

_memory_cache: InMemoryCache | None = None
_sqlite_cache = None
_sqlite_path: Path | None = None


def _get_memory_cache() -> InMemoryCache:
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = InMemoryCache()
    return _memory_cache


def _get_sqlite_cache(path: Path):
    global _sqlite_cache, _sqlite_path
    if _sqlite_cache is None or _sqlite_path != Path(path):
        from langchain_community.cache import SQLiteCache   # imported lazily (heavier package)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _sqlite_cache = SQLiteCache(database_path=str(path))
        _sqlite_path = Path(path)
    return _sqlite_cache


def configure_cache(mode: str, sqlite_path: Path = SQLITE_CACHE_PATH) -> str:
    """Activate the chosen cache globally and return the active mode."""
    if mode == CACHE_MEMORY:
        set_llm_cache(_get_memory_cache())
    elif mode == CACHE_SQLITE:
        set_llm_cache(_get_sqlite_cache(sqlite_path))
    else:
        set_llm_cache(None)
        mode = CACHE_NONE
    return mode


def cache_entry_count(mode: str, sqlite_path: Path = SQLITE_CACHE_PATH) -> int:
    """Number of cached responses for the given mode (0 if unavailable)."""
    if mode == CACHE_MEMORY:
        return len(getattr(_get_memory_cache(), "_cache", {}))
    if mode == CACHE_SQLITE:
        if not Path(sqlite_path).exists():
            return 0
        try:
            with sqlite3.connect(sqlite_path) as conn:
                return conn.execute("SELECT COUNT(*) FROM full_llm_cache").fetchone()[0]
        except sqlite3.Error:
            return 0
    return 0


def cache_file_size_kb(sqlite_path: Path = SQLITE_CACHE_PATH) -> float:
    path = Path(sqlite_path)
    return round(path.stat().st_size / 1024, 1) if path.exists() else 0.0


def clear_cache(mode: str, sqlite_path: Path = SQLITE_CACHE_PATH) -> None:
    if mode == CACHE_MEMORY:
        _get_memory_cache().clear()
    elif mode == CACHE_SQLITE:
        _get_sqlite_cache(sqlite_path).clear()


def active_cache_name() -> str:
    cache = get_llm_cache()
    return type(cache).__name__ if cache is not None else "None"


CACHE_COMPARISON = [
    {"": "Stored in", "InMemoryCache": "RAM (memory)", "SQLiteCache": "A file on disk (.db)"},
    {"": "Speed", "InMemoryCache": "Fastest", "SQLiteCache": "Fast, slightly slower"},
    {"": "Survives restart?", "InMemoryCache": "No", "SQLiteCache": "Yes"},
    {"": "Best for", "InMemoryCache": "One session", "SQLiteCache": "Reusing across sessions"},
]
