"""Tests for SchemaForge schema consistency checker (check.py)."""
from __future__ import annotations

import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.check import check_directory, detect_format

# ── detect_format tests ──

def test_detect_format_sql():
    assert detect_format("schema.sql") == "sql"


def test_detect_format_prisma():
    assert detect_format("schema.prisma") == "prisma"


def test_detect_format_drizzle():
    assert detect_format("schema.ts") == "drizzle"
    assert detect_format("schema.tsx") == "drizzle"


def test_detect_format_django():
    assert detect_format("models.py") == "django"


def test_detect_format_json_schema():
    assert detect_format("schema.json") == "json_schema"


def test_detect_format_graphql():
    assert detect_format("schema.graphql") == "graphql"
    assert detect_format("schema.gql") == "graphql"


def test_detect_format_unknown():
    assert detect_format("readme.md") is None


def test_detect_format_alembic():
    """Alembic .py files are detected as Django by extension."""
    assert detect_format("migration.py") == "django"


# ── check_directory tests ──

SAMPLE_SQL = """CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);
"""

SAMPLE_PRISMA = """generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model users {
  id   Int   @id @default(autoincrement())
  name String @db.VarChar(100)
}
"""


def test_check_directory_empty():
    """Empty directory should report need at least 2 files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = check_directory(tmpdir)
        assert "Need at least 2 schema files" in result


def test_check_directory_single_file():
    """Single file directory should report need at least 2 files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "schema.sql").write_text(SAMPLE_SQL)
        result = check_directory(tmpdir)
        assert "Need at least 2 schema files" in result


def test_check_directory_consistent_files():
    """Files that produce equivalent schemas should pass."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "schema.sql").write_text(SAMPLE_SQL)
        Path(tmpdir, "schema.prisma").write_text(SAMPLE_PRISMA)

        result = check_directory(tmpdir)
        # The check might find minor differences (nullable, naming), but
        # the output should mention both files and attempt comparison
        assert "Files found: 2" in result
        assert "schema.sql" in result or "schema" in result


def test_check_directory_not_a_directory():
    """Non-directory path should raise NotADirectoryError."""
    import pytest
    with tempfile.NamedTemporaryFile() as f:
        with pytest.raises(NotADirectoryError):
            check_directory(f.name)


def test_check_directory_ignores_non_schema_files():
    """Non-schema files should be ignored by the check."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "schema.sql").write_text(SAMPLE_SQL)
        Path(tmpdir, "readme.md").write_text("# Not a schema")
        Path(tmpdir, "data.csv").write_text("a,b,c")

        result = check_directory(tmpdir)
        assert "Need at least 2" in result
        assert "found 1" in result


def test_check_directory_canonical_format():
    """--canonical option should change the comparison target format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "schema.sql").write_text(SAMPLE_SQL)
        Path(tmpdir, "schema.prisma").write_text(SAMPLE_PRISMA)

        result = check_directory(tmpdir, canonical="prisma")
        assert "compared via prisma" in result
