"""DuckDB database: local stand-in for Amazon Athena.

Athena queries S3/Glue tables serverlessly; locally DuckDB gives the
same "SQL over tabular data" shape with zero infrastructure. The DB
file is generated (git-ignored) by ``generate_data.py``.
"""
from __future__ import annotations

import pathlib

import duckdb

DEFAULT_DB = pathlib.Path(__file__).resolve().parents[2] / "data" / "claims.duckdb"


def connect(db_path: str | pathlib.Path = DEFAULT_DB, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=read_only)


def ensure_db(db_path: str | pathlib.Path = DEFAULT_DB) -> pathlib.Path:
    p = pathlib.Path(db_path)
    if not p.exists():
        from .generate_data import build_database
        build_database(p)
    return p
