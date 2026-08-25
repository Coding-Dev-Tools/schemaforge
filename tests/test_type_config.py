"""Tests for SchemaForge custom type mapping configuration (type_config.py)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from schemaforge.convert import convert_schema
from schemaforge.ir import Column, ColumnType
from schemaforge.type_config import EMPTY_CONFIG, TypeConfig

# ── Basic TypeConfig Tests ──


def test_empty_config_returns_none():
    """Empty TypeConfig returns None for all lookups."""
    col = Column(name="id", type=ColumnType.INTEGER)
    result = EMPTY_CONFIG.get_override(col, "sql")
    assert result is None


def test_config_simple_override():
    """TypeConfig returns overridden type for matching column/format."""
    config = TypeConfig({"sql": {"INTEGER": "BIGINT"}})
    col = Column(name="id", type=ColumnType.INTEGER)
    result = config.get_override(col, "sql")
    assert result == "BIGINT"


def test_config_wrong_format():
    """TypeConfig returns None for non-matching format."""
    config = TypeConfig({"sql": {"INTEGER": "BIGINT"}})
    col = Column(name="id", type=ColumnType.INTEGER)
    result = config.get_override(col, "prisma")
    assert result is None


def test_config_wrong_column_type():
    """TypeConfig returns None for non-matching column type."""
    config = TypeConfig({"sql": {"STRING": "TEXT"}})
    col = Column(name="id", type=ColumnType.INTEGER)
    result = config.get_override(col, "sql")
    assert result is None


def test_config_with_length_placeholder():
    """TypeConfig replaces {length} placeholder."""
    config = TypeConfig({"sql": {"STRING": "VARCHAR({length})"}})
    col = Column(name="name", type=ColumnType.STRING, type_args={"length": 100})
    result = config.get_override(col, "sql")
    assert result == "VARCHAR(100)"


def test_config_with_precision_scale():
    """TypeConfig replaces {precision} and {scale} placeholders."""
    config = TypeConfig({"sql": {"DECIMAL": "DECIMAL({precision},{scale})"}})
    col = Column(
        name="price", type=ColumnType.DECIMAL, type_args={"precision": 12, "scale": 4}
    )
    result = config.get_override(col, "sql")
    assert result == "DECIMAL(12,4)"


def test_config_with_enum_values():
    """TypeConfig replaces {values} placeholder."""
    config = TypeConfig({"sql": {"ENUM": "ENUM({values})"}})
    col = Column(
        name="size", type=ColumnType.ENUM, type_args={"values": ["S", "M", "L"]}
    )
    result = config.get_override(col, "sql")
    assert result == "ENUM('S', 'M', 'L')"


def test_config_unresolved_placeholder_removed():
    """Unresolved placeholders are stripped from the result."""
    config = TypeConfig({"sql": {"INTEGER": "INTEGER DEFAULT {unknown}"}})
    col = Column(name="id", type=ColumnType.INTEGER)
    result = config.get_override(col, "sql")
    assert result == "INTEGER DEFAULT "


# ── File Loading Tests ──


def test_load_from_json():
    """TypeConfig can be loaded from a JSON file."""
    data = {"overrides": {"sql": {"INTEGER": "BIGINT"}}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        tmp_path = f.name
    try:
        config = TypeConfig.from_file(tmp_path)
        col = Column(name="id", type=ColumnType.INTEGER)
        assert config.get_override(col, "sql") == "BIGINT"
    finally:
        os.unlink(tmp_path)


def test_load_from_yaml():
    """TypeConfig can be loaded from a YAML file."""
    yaml_content = """
overrides:
  sql:
    INTEGER: BIGINT
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        tmp_path = f.name
    try:
        config = TypeConfig.from_file(tmp_path)
        col = Column(name="id", type=ColumnType.INTEGER)
        assert config.get_override(col, "sql") == "BIGINT"
    finally:
        os.unlink(tmp_path)


def test_load_from_yaml_without_pyyaml():
    """Loading YAML without PyYAML raises ImportError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("overrides:\n  sql:\n    INTEGER: BIGINT\n")
        tmp_path = f.name
    try:
        _orig_import = (
            __builtins__["__import__"]
            if isinstance(__builtins__, dict)
            else __builtins__.__import__
        )

        def _mock_import(name, *args, **kw):
            if name == "yaml":
                raise ImportError("No module named yaml")
            return _orig_import(name, *args, **kw)

        try:
            if isinstance(__builtins__, dict):
                __builtins__["__import__"] = _mock_import
            else:
                __builtins__.__import__ = _mock_import

            with pytest.raises(ImportError, match="PyYAML is required"):
                TypeConfig.from_file(tmp_path)
        finally:
            # Restore original import
            if isinstance(__builtins__, dict):
                __builtins__["__import__"] = _orig_import
            else:
                __builtins__.__import__ = _orig_import
    finally:
        os.unlink(tmp_path)


@pytest.mark.parametrize("ext", [".yml", ".yaml", ".json"])
def test_supported_extensions(ext):
    """All supported extensions load without error."""
    if ext == ".json":
        content = '{"overrides": {"sql": {"INTEGER": "BIGINT"}}}'
    else:
        content = "overrides:\n sql:\n INTEGER: BIGINT\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False) as f:
        f.write(content)
        tmp_path = f.name
    try:
        config = TypeConfig.from_file(tmp_path)
        assert isinstance(config, TypeConfig)
    finally:
        os.unlink(tmp_path)


def test_unsupported_extension():
    """Unsupported extensions raise ValueError."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("test = 1")
        tmp_path = f.name
    try:
        with pytest.raises(ValueError, match="Unsupported config format"):
            TypeConfig.from_file(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_file_not_found():
    """Missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Type config not found"):
        TypeConfig.from_file("/nonexistent/path/types.yaml")


# ── Merge Tests ──


def test_merge_two_configs():
    """Merging configs combines overrides (other takes precedence)."""
    base = TypeConfig({"sql": {"INTEGER": "INT", "STRING": "TEXT"}})
    override = TypeConfig({"sql": {"INTEGER": "BIGINT"}})
    merged = base.merge(override)

    col_int = Column(name="id", type=ColumnType.INTEGER)
    col_str = Column(name="name", type=ColumnType.STRING)

    assert merged.get_override(col_int, "sql") == "BIGINT"  # Overridden
    assert merged.get_override(col_str, "sql") == "TEXT"  # Preserved


def test_merge_different_formats():
    """Merging configs with different formats combines both."""
    a = TypeConfig({"sql": {"INTEGER": "INT"}})
    b = TypeConfig({"prisma": {"INTEGER": "Int"}})
    merged = a.merge(b)

    col = Column(name="id", type=ColumnType.INTEGER)
    assert merged.get_override(col, "sql") == "INT"
    assert merged.get_override(col, "prisma") == "Int"


# ── Integration Tests ──


def test_type_config_in_convert_sql_to_prisma():
    """TypeConfig overrides applied through convert_schema API."""
    sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);
"""
    # Without override: STRING → "String"
    normal = convert_schema(sql, "sql", "prisma")
    assert "String" in normal

    # With override: STRING → "String @db.VarChar({length})"
    config = TypeConfig({"prisma": {"STRING": "String @db.VarChar({length})"}})
    overridden = convert_schema(sql, "sql", "prisma", type_config=config)
    assert "String @db.VarChar(100)" in overridden


def test_type_config_in_convert_sql_to_sqlalchemy():
    """TypeConfig can change SQLAlchemy type mapping."""
    sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);
"""
    # With override: STRING → "Unicode({length})"
    config = TypeConfig({"sqlalchemy": {"STRING": "Unicode({length})"}})
    result = convert_schema(sql, "sql", "sqlalchemy", type_config=config)
    assert "Unicode(100)" in result


def test_type_config_in_convert_sql_to_django():
    """TypeConfig can change Django field type."""
    sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100)
);
"""
    config = TypeConfig({"django": {"STRING": "CharField(max_length={length})"}})
    result = convert_schema(sql, "sql", "django", type_config=config)
    assert "CharField(max_length=100)" in result


def test_type_config_does_not_affect_roundtrip():
    """TypeConfig only affects generation, not parsing — roundtrip fidelity preserved."""
    sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);
"""
    config = TypeConfig({"prisma": {"STRING": "CustomString"}})
    # SQL → Prisma should use override
    prisma = convert_schema(sql, "sql", "prisma", type_config=config)
    assert "CustomString" in prisma

    # Prisma → SQL should still produce valid SQL (no override for SQL)
    sql2 = convert_schema(prisma, "prisma", "sql")
    assert "CREATE TABLE users" in sql2
    assert "name" in sql2


def test_empty_config_passthrough():
    """Passing EMPTY_CONFIG should behave identically to no config."""
    sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY
);
"""
    without = convert_schema(sql, "sql", "prisma")
    with_empty = convert_schema(sql, "sql", "prisma", type_config=EMPTY_CONFIG)
    assert without == with_empty
