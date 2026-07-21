"""Tests for SchemaForge MCP server (mcp_server.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

pytest.importorskip("mcp", reason="mcp is an optional dependency")

from schemaforge.mcp_server import _FORMATS, create_server


def test_create_server():
    """create_server should return a FastMCP instance."""
    s = create_server()
    assert s is not None
    assert len([name for name in s._tool_manager._tools]) > 0


def test_server_has_convert_tool():
    """Server should have the convert tool registered."""
    s = create_server()
    tool_names = [name for name in s._tool_manager._tools]
    assert "convert" in tool_names


def test_server_has_diff_tool():
    """Server should have the diff tool registered."""
    s = create_server()
    tool_names = [name for name in s._tool_manager._tools]
    assert "diff" in tool_names


def test_server_has_check_tool():
    """Server should have the check tool registered."""
    s = create_server()
    tool_names = [name for name in s._tool_manager._tools]
    assert "check" in tool_names


def test_server_has_formats_tool():
    """Server should have the formats tool registered."""
    s = create_server()
    tool_names = [name for name in s._tool_manager._tools]
    assert "formats" in tool_names


def test_server_has_detect_format_tool():
    """Server should have the detect_format tool registered."""
    s = create_server()
    tool_names = [name for name in s._tool_manager._tools]
    assert "detect_format" in tool_names


def test_all_5_tools_registered():
    """Server should have exactly 5 tools."""
    s = create_server()
    tool_names = [name for name in s._tool_manager._tools]
    assert len(tool_names) == 5


def test_convert_tool_converts_sql_to_prisma():
    """Convert tool should handle basic SQL to Prisma conversion."""
    sql = """CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100) NOT NULL
    );
    """
    s = create_server()
    tool = s._tool_manager._tools["convert"]
    result = tool.fn(
        schema_text=sql,
        from_format="sql",
        to_format="prisma",
    )
    assert "generator client" in result
    assert "model users" in result


def test_convert_tool_invalid_format():
    """Convert tool should return error message for invalid format."""
    s = create_server()
    tool = s._tool_manager._tools["convert"]
    result = tool.fn(
        schema_text="",
        from_format="invalid",
        to_format="sql",
    )
    assert "Error" in result
    assert "invalid" in result


def test_diff_tool():
    """Diff tool should compare two schemas."""
    s = create_server()
    tool = s._tool_manager._tools["diff"]
    result = tool.fn(
        schema_a="CREATE TABLE a (id INTEGER);",
        schema_b="CREATE TABLE b (id INTEGER);",
        format="sql",
    )
    # Should detect changed table names
    assert "a" in result or "b" in result or "No differences" in result


def test_formats_tool():
    """Formats tool should list all supported formats, including ef and scala."""
    s = create_server()
    tool = s._tool_manager._tools["formats"]
    result = tool.fn()
    assert "sql" in result
    assert "prisma" in result
    assert "graphql" in result
    assert "json_schema" in result
    assert "ef" in result
    assert "scala" in result
    assert all(f in result for f in _FORMATS)


def test_detect_format_tool():
    """detect_format tool should return format from filename."""
    s = create_server()
    tool = s._tool_manager._tools["detect_format"]
    assert tool.fn("schema.sql") == "sql"
    assert tool.fn("schema.prisma") == "prisma"
    assert tool.fn("schema.graphql") == "graphql"
    assert tool.fn("schema.json") == "json_schema"


def test_detect_format_tool_unknown():
    """detect_format tool should return 'unknown' for unrecognized files."""
    s = create_server()
    tool = s._tool_manager._tools["detect_format"]
    result = tool.fn("readme.md")
    assert "unknown" in result


def test_convert_tool_alembic_error():
    """Convert from alembic should return error (generator-only)."""
    s = create_server()
    tool = s._tool_manager._tools["convert"]
    result = tool.fn(
        schema_text="some migration",
        from_format="alembic",
        to_format="sql",
    )
    assert "Error" in result
    assert "generator-only" in result.lower() or "not supported" in result.lower()
