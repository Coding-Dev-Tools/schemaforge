"""Tests for SchemaForge MCP server (mcp_server.py)."""

from __future__ import annotations

import pytest
import sys
from click.testing import CliRunner
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

pytest.importorskip("mcp", reason="mcp is an optional dependency")

from schemaforge import mcp_server
from schemaforge.cli import main
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


@pytest.mark.parametrize(
    ("args", "transport", "host", "port"),
    [
        (["--sse"], "sse", "127.0.0.1", 8000),
        (["--sse", "--host", "localhost", "--port", "8765"], "sse", "localhost", 8765),
        ([], "stdio", "127.0.0.1", 8000),
        (["--host", "localhost", "--port", "8765"], "stdio", "127.0.0.1", 8000),
    ],
    ids=["default-sse", "custom-sse", "default-stdio", "stdio-ignores-sse-options"],
)
def test_mcp_command_transports(args, transport, host, port):
    """Enforce the installed SDK run signature without starting either transport."""
    with patch.object(mcp_server.FastMCP, "run", autospec=True) as run_mock:
        result = CliRunner().invoke(mcp_server.mcp_command, args)

    assert result.exit_code == 0, repr(result.exception)
    run_mock.assert_called_once()
    server = run_mock.call_args.args[0]
    assert run_mock.call_args.kwargs == {"transport": transport}
    assert server.settings.host == host
    assert server.settings.port == port
    assert len(server._tool_manager._tools) == 5
    if transport == "sse":
        assert f"Starting SchemaForge MCP server on http://{host}:{port}" in result.output


def test_create_server_custom_address():
    """Configure the address through the installed SDK constructor."""
    server = create_server(host="localhost", port=8765)
    assert server.settings.host == "localhost"
    assert server.settings.port == 8765


def test_create_server_without_optional_mcp(monkeypatch):
    """Missing MCP keeps the same installation error for both factory calls."""
    monkeypatch.setattr(mcp_server, "FastMCP", None)
    with pytest.raises(ImportError, match="The 'mcp' package is required"):
        create_server()
    with pytest.raises(ImportError, match="The 'mcp' package is required"):
        create_server(host="localhost", port=8765)


def _link_directory(link, target):
    if sys.platform == "win32":
        # Junctions exercise canonical link resolution without symlink privileges.
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


@pytest.fixture(params=["environment", "cwd"])
def mcp_file_paths(tmp_path, monkeypatch, request):
    root = tmp_path / "allowed"
    maps = root / "maps"
    maps.mkdir(parents=True)
    schemas = root / "schemas"
    schemas.mkdir()
    schema = "CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL);"
    for name in ("a.sql", "b.sql"):
        (schemas / name).write_text(schema, encoding="utf-8")
    map_path = maps / "types.json"
    config = '{"overrides": {"prisma": {"STRING": "String @db.Text"}}}'
    map_path.write_text(config, encoding="utf-8")
    outside = tmp_path / "allowed-neighbor"
    outside.mkdir()
    outside_map = outside / "types.json"
    outside_map.write_text(config, encoding="utf-8")
    _link_directory(root / "linked-outside", outside)
    _link_directory(root / "linked-maps", maps)
    if request.param == "environment":
        monkeypatch.setenv("SCHEMAFORGE_MCP_ROOT", str(root))
        monkeypatch.chdir(tmp_path)
    else:
        monkeypatch.delenv("SCHEMAFORGE_MCP_ROOT", raising=False)
        monkeypatch.chdir(root)
    return root, map_path, outside_map, schemas


def _invoke_type_map_tool(tool_name, directory, **kwargs):
    tool = create_server()._tool_manager._tools[tool_name]
    if tool_name == "convert":
        return tool.fn("CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL);", **kwargs)
    return tool.fn(str(directory), **kwargs)


@pytest.mark.parametrize("tool_name", ["convert", "check"])
@pytest.mark.parametrize("path_kind", ["absolute", "traversal", "symlink"])
def test_mcp_type_map_rejects_outside_root(mcp_file_paths, tool_name, path_kind):
    """Reject outside-root paths before the loader can read any file."""
    root, _, outside_map, schemas = mcp_file_paths
    if path_kind == "absolute":
        path = outside_map
    elif path_kind == "traversal":
        path = root.relative_to(Path.cwd()) / ".." / outside_map.parent.name / outside_map.name
    else:
        path = root / "linked-outside" / outside_map.name
    with patch.object(mcp_server.TypeConfig, "from_file", return_value=mcp_server.TypeConfig()) as load:
        result = _invoke_type_map_tool(tool_name, schemas, type_map_path=str(path))
    load.assert_not_called()
    assert "outside the allowed root" in result


@pytest.mark.parametrize("tool_name", ["convert", "check"])
@pytest.mark.parametrize("path_kind", ["absolute", "relative", "symlink"])
def test_mcp_type_map_allows_in_root(mcp_file_paths, tool_name, path_kind):
    """Load valid synthetic maps through their validated canonical paths."""
    root, map_path, _, schemas = mcp_file_paths
    if path_kind == "absolute":
        path = map_path
    elif path_kind == "relative":
        path = map_path.relative_to(Path.cwd())
    else:
        path = root / "linked-maps" / map_path.name
    with patch.object(mcp_server.TypeConfig, "from_file", wraps=mcp_server.TypeConfig.from_file) as load:
        result = _invoke_type_map_tool(tool_name, schemas, type_map_path=str(path))
    load.assert_called_once()
    assert Path(load.call_args.args[0]) == map_path.resolve()
    if tool_name == "convert":
        assert "String @db.Text" in result
    else:
        assert "PASS: All schema files are equivalent" in result


@pytest.mark.parametrize("tool_name", ["convert", "check"])
def test_mcp_type_map_omitted(mcp_file_paths, tool_name):
    """Omitting the map keeps normal conversion and checking without a load."""
    _, _, _, schemas = mcp_file_paths
    with patch.object(mcp_server.TypeConfig, "from_file") as load:
        result = _invoke_type_map_tool(tool_name, schemas)
    load.assert_not_called()
    if tool_name == "convert":
        assert "model users" in result
    else:
        assert "PASS: All schema files are equivalent" in result


def test_mcp_check_directory_rejects_outside_root(mcp_file_paths):
    """The existing check-directory guard still prevents map loading."""
    _, map_path, outside_map, _ = mcp_file_paths
    with patch.object(mcp_server.TypeConfig, "from_file") as load:
        result = _invoke_type_map_tool("check", outside_map.parent, type_map_path=str(map_path))
    load.assert_not_called()
    assert "Directory" in result and "outside the allowed root" in result


@pytest.mark.parametrize("tool_name", ["convert", "check"])
def test_standalone_cli_type_map_unrestricted(mcp_file_paths, tool_name):
    """The standalone CLI can still load a user-selected synthetic outside map."""
    _, _, outside_map, schemas = mcp_file_paths
    if tool_name == "convert":
        args = ["convert", str(schemas / "a.sql"), "--from", "sql", "--to", "prisma"]
    else:
        args = ["check", "--dir", str(schemas), "--canonical", "prisma"]
    with patch.object(mcp_server.TypeConfig, "from_file", wraps=mcp_server.TypeConfig.from_file) as load:
        result = CliRunner().invoke(main, [*args, "--type-map", str(outside_map)])
    assert result.exit_code == 0, repr(result.exception)
    load.assert_called_once_with(str(outside_map))
    if tool_name == "convert":
        assert "String @db.Text" in result.output
    else:
        assert "PASS: All schema files are equivalent" in result.output
