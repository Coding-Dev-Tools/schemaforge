"""Tests for SchemaForge schema diffing (diff.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.diff import _diff_tables, diff_schemas
from schemaforge.ir import Column, ColumnType, Index, Table

# ── Unit tests for _diff_tables ──


def _col(name: str, col_type: ColumnType = ColumnType.STRING, **kwargs) -> Column:
    return Column(name=name, type=col_type, **kwargs)


def _table(
    name: str, columns: list[Column] | None = None, indexes: list[Index] | None = None
) -> Table:
    return Table(name=name, columns=columns or [], indexes=indexes or [])


class TestDiffTables:
    """Unit tests for _diff_tables comparing two Table IR objects."""

    def test_identical_tables(self):
        ta = _table("users", [_col("id", ColumnType.INTEGER, primary_key=True)])
        tb = _table("users", [_col("id", ColumnType.INTEGER, primary_key=True)])
        assert _diff_tables(ta, tb) == []

    def test_added_column(self):
        ta = _table("users", [_col("id", ColumnType.INTEGER, primary_key=True)])
        tb = _table(
            "users",
            [
                _col("id", ColumnType.INTEGER, primary_key=True),
                _col("email", ColumnType.STRING),
            ],
        )
        diffs = _diff_tables(ta, tb)
        assert any('+ column "email"' in d for d in diffs)

    def test_removed_column(self):
        ta = _table(
            "users",
            [
                _col("id", ColumnType.INTEGER, primary_key=True),
                _col("email", ColumnType.STRING),
            ],
        )
        tb = _table("users", [_col("id", ColumnType.INTEGER, primary_key=True)])
        diffs = _diff_tables(ta, tb)
        assert any('- column "email"' in d for d in diffs)

    def test_type_change(self):
        ta = _table("users", [_col("age", ColumnType.INTEGER)])
        tb = _table("users", [_col("age", ColumnType.STRING)])
        diffs = _diff_tables(ta, tb)
        assert any("integer" in d and "string" in d for d in diffs)

    def test_nullable_change(self):
        ta = _table("users", [_col("name", ColumnType.STRING, nullable=True)])
        tb = _table("users", [_col("name", ColumnType.STRING, nullable=False)])
        diffs = _diff_tables(ta, tb)
        assert any("nullable" in d for d in diffs)

    def test_primary_key_change(self):
        ta = _table("users", [_col("id", ColumnType.INTEGER, primary_key=False)])
        tb = _table("users", [_col("id", ColumnType.INTEGER, primary_key=True)])
        diffs = _diff_tables(ta, tb)
        assert any("PK" in d for d in diffs)

    def test_default_change(self):
        ta = _table("users", [_col("status", ColumnType.STRING, default="active")])
        tb = _table("users", [_col("status", ColumnType.STRING, default="inactive")])
        diffs = _diff_tables(ta, tb)
        assert any("default" in d for d in diffs)

    def test_unique_change(self):
        """Unique constraint changes should appear in diff output."""
        ta = _table("users", [_col("email", ColumnType.STRING, unique=True)])
        tb = _table("users", [_col("email", ColumnType.STRING, unique=False)])
        diffs = _diff_tables(ta, tb)
        assert any("unique" in d for d in diffs)
        assert "True" in diffs[0]
        assert "False" in diffs[0]

    def test_comment_change(self):
        """Comment changes should appear in diff output."""
        ta = _table("users", [_col("id", ColumnType.INTEGER, comment="old comment")])
        tb = _table("users", [_col("id", ColumnType.INTEGER, comment="new comment")])
        diffs = _diff_tables(ta, tb)
        assert any("comment" in d for d in diffs)

    def test_added_index(self):
        """Added index should appear in diff output."""
        ta = _table("users", [_col("email", ColumnType.STRING)], indexes=[])
        tb = _table(
            "users",
            [_col("email", ColumnType.STRING)],
            indexes=[
                Index(name="idx_email", columns=["email"]),
            ],
        )
        diffs = _diff_tables(ta, tb)
        assert any('+ index "idx_email"' in d for d in diffs)

    def test_removed_index(self):
        """Removed index should appear in diff output."""
        ta = _table(
            "users",
            [_col("email", ColumnType.STRING)],
            indexes=[
                Index(name="idx_email", columns=["email"]),
            ],
        )
        tb = _table("users", [_col("email", ColumnType.STRING)], indexes=[])
        diffs = _diff_tables(ta, tb)
        assert any('- index "idx_email"' in d for d in diffs)

    def test_no_index_diff_for_unnamed(self):
        """Indexes with empty names should not produce spurious diffs."""
        ta = _table(
            "users",
            [_col("email", ColumnType.STRING)],
            indexes=[
                Index(name="", columns=["email"]),
            ],
        )
        tb = _table(
            "users",
            [_col("email", ColumnType.STRING)],
            indexes=[
                Index(name="", columns=["email"]),
            ],
        )
        diffs = _diff_tables(ta, tb)
        assert not any("index" in d for d in diffs)


# ── Integration tests for diff_schemas ──

SQL_UNIQUE_A = """CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) UNIQUE
);
"""

SQL_UNIQUE_B = """CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255)
);
"""

SQL_TABLE_ADDED = """CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    title VARCHAR(200)
);
"""

SQL_TABLE_REMOVED = """CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);
"""

SQL_ENUM_ADDED = """CREATE TYPE status AS ENUM ('active', 'inactive', 'pending');

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);
"""

SQL_ENUM_REMOVED = """CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);
"""

SQL_ENUM_CHANGED = """CREATE TYPE status AS ENUM ('active', 'inactive', 'pending');

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);
"""

SQL_ENUM_ORIGINAL = """CREATE TYPE status AS ENUM ('active', 'inactive');

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);
"""

SQL_IDENTICAL = """CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);
"""


class TestDiffSchemas:
    """Integration tests for diff_schemas using SQL text."""

    def test_identical_schemas(self):
        result = diff_schemas(SQL_IDENTICAL, SQL_IDENTICAL, "sql")
        assert "No differences found" in result

    def test_unique_change_detected(self):
        """Column going from UNIQUE to non-UNIQUE should be reported."""
        result = diff_schemas(SQL_UNIQUE_A, SQL_UNIQUE_B, "sql")
        assert "unique" in result
        assert "No differences found" not in result

    def test_added_table(self):
        result = diff_schemas(SQL_TABLE_REMOVED, SQL_TABLE_ADDED, "sql")
        assert "Added tables" in result
        assert "posts" in result

    def test_removed_table(self):
        result = diff_schemas(SQL_TABLE_ADDED, SQL_TABLE_REMOVED, "sql")
        assert "Removed tables" in result
        assert "posts" in result

    def test_added_enum(self):
        """Added enum type should be reported."""
        result = diff_schemas(SQL_ENUM_REMOVED, SQL_ENUM_ADDED, "sql")
        assert "Added enums" in result
        assert "status" in result

    def test_removed_enum(self):
        """Removed enum type should be reported."""
        result = diff_schemas(SQL_ENUM_ADDED, SQL_ENUM_REMOVED, "sql")
        assert "Removed enums" in result
        assert "status" in result

    def test_enum_value_change(self):
        """Changed enum values should be reported."""
        result = diff_schemas(SQL_ENUM_ORIGINAL, SQL_ENUM_CHANGED, "sql")
        # The enum 'status' has values changed from ['active','inactive'] to ['active','inactive','pending']
        assert "status" in result
        assert "pending" in result or "values" in result

    def test_unsupported_format(self):
        result = diff_schemas("x", "y", "badformat")
        assert "Unsupported" in result


class TestIndexAndCommentDrift:
    """Regression: same-named indexes with changed columns/unique and table
    comment changes previously produced NO diff (silent schema drift)."""

    def test_index_columns_change(self):
        ta = _table("users", indexes=[Index(name="idx_email", columns=["email"])])
        tb = _table(
            "users", indexes=[Index(name="idx_email", columns=["email", "tenant_id"])]
        )
        diffs = _diff_tables(ta, tb)
        assert any('~ index "idx_email": columns=' in d for d in diffs)

    def test_index_unique_change(self):
        ta = _table("users", indexes=[Index(name="idx_email", columns=["email"])])
        tb = _table(
            "users",
            indexes=[Index(name="idx_email", columns=["email"], unique=True)],
        )
        diffs = _diff_tables(ta, tb)
        assert any('~ index "idx_email": unique=False -> True' in d for d in diffs)

    def test_identical_indexes_still_clean(self):
        idx = Index(name="idx_email", columns=["email"], unique=True)
        ta = _table("users", indexes=[idx])
        tb = _table("users", indexes=[Index(name="idx_email", columns=["email"], unique=True)])
        assert _diff_tables(ta, tb) == []

    def test_table_comment_change(self):
        ta = Table(name="users", columns=[], comment="old")
        tb = Table(name="users", columns=[], comment="new")
        diffs = _diff_tables(ta, tb)
        assert any('~ table comment: "old" -> "new"' in d for d in diffs)

    def test_standalone_create_index_unique_drift_end_to_end(self):
        """Regression: standalone CREATE [UNIQUE] INDEX statements were silently
        dropped by the SQL parser, so unique-flag drift compared as equivalent."""
        from schemaforge.diff import diff_schemas

        a = (
            "CREATE TABLE users ("
            "id INTEGER PRIMARY KEY, email VARCHAR(255));"
            "CREATE INDEX idx_email ON users (email);"
        )
        b = (
            "CREATE TABLE users ("
            "id INTEGER PRIMARY KEY, email VARCHAR(255));"
            "CREATE UNIQUE INDEX idx_email ON users (email);"
        )
        out = diff_schemas(a, b, "sql")
        assert '~ index "idx_email": unique=False -> True' in out

    def test_standalone_create_index_columns_drift_end_to_end(self):
        from schemaforge.diff import diff_schemas

        a = (
            "CREATE TABLE users (id INTEGER PRIMARY KEY);\n"
            "CREATE INDEX idx_t ON users (tenant_id);"
        )
        b = (
            "CREATE TABLE users (id INTEGER PRIMARY KEY);\n"
            "CREATE INDEX idx_t ON users (tenant_id, region);"
        )
        out = diff_schemas(a, b, "sql")
        assert '~ index "idx_t": columns=' in out
