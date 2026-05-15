"""MCP server for SchemaForge — exposes schema operations as AI-usable tools.

Run with:
    schemaforge mcp          # stdio transport (default for AI clients)
    schemaforge mcp --sse    # SSE transport (HTTP server)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click

from .convert import convert_schema
from .diff import diff_schemas
from .check import check_directory, detect_format
from .type_config import TypeConfig

# Try to import mcp — soft dependency
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore


# All supported formats
_FORMATS = ["sql", "prisma", "drizzle", "typeorm", "django", "sqlalchemy", "alembic", "json_schema", "graphql"]
_FORMAT_DESCRIPTIONS = {
    "sql": "SQL DDL (Data Definition Language)",
    "prisma": "Prisma schema",
    "drizzle": "Drizzle ORM schema (TypeScript)",
    "typeorm": "TypeORM entity decorators (TypeScript)",
    "django": "Django models (Python)",
    "sqlalchemy": "SQLAlchemy declarative models (Python)",
    "alembic": "Alembic migration scripts (Python, generator-only)",
    "json_schema": "JSON Schema (draft 2020-12)",
    "graphql": "GraphQL SDL (Schema Definition Language)",
}


def create_server() -> Any:
    """Create and configure the MCP server with all SchemaForge tools."""
    if FastMCP is None:
        raise ImportError(
            "The 'mcp' package is required to run the MCP server.\n"
            "Install it with: pip install mcp"
        )

    server = FastMCP("SchemaForge", log_level="WARNING")

    @server.tool(
        name="convert",
        description="Convert a schema from one format to another. "
                    "All 9 formats support conversion to and from every other format. "
                    "Returns the converted schema as text.",
    )
    def convert_tool(
        schema_text: str,
        from_format: str = "sql",
        to_format: str = "prisma",
        type_map_path: str | None = None,
    ) -> str:
        """Convert a schema between formats.

        Args:
            schema_text: The schema text to convert.
            from_format: Source format (sql, prisma, drizzle, typeorm, django,
                        sqlalchemy, alembic, json_schema, graphql).
            to_format: Target format (same options as from_format).
            type_map_path: Optional path to a YAML/JSON type mapping config file.
        """
        if from_format not in _FORMATS:
            return f"Error: Unsupported source format '{from_format}'. Supported: {', '.join(_FORMATS)}"
        if to_format not in _FORMATS:
            return f"Error: Unsupported target format '{to_format}'. Supported: {', '.join(_FORMATS)}"

        type_config: TypeConfig | None = None
        if type_map_path:
            try:
                type_config = TypeConfig.from_file(type_map_path)
            except (FileNotFoundError, ValueError) as e:
                return f"Error loading type map: {e}"

        try:
            result = convert_schema(schema_text, from_format, to_format, type_config=type_config)
            return result
        except ValueError as e:
            return f"Error: {e}"
        except NotImplementedError:
            return f"Error: {from_format} → {to_format} conversion is not supported (Alembic is generator-only)."
        except Exception as e:
            return f"Error: {e}"

    @server.tool(
        name="diff",
        description="Compare two schemas in the same format and return differences. "
                    "Detects added, removed, and modified tables, columns, indexes, and constraints.",
    )
    def diff_tool(
        schema_a: str,
        schema_b: str,
        format: str = "sql",
    ) -> str:
        """Compare two schemas and show differences.

        Args:
            schema_a: First schema text.
            schema_b: Second schema text to compare against.
            format: Schema format (sql, prisma, drizzle, typeorm, django,
                   sqlalchemy, json_schema, graphql). Default: sql.
        """
        if format not in _FORMATS:
            return f"Error: Unsupported format '{format}'. Supported: {', '.join(_FORMATS)}"

        try:
            result = diff_schemas(schema_a, schema_b, format)
            return result if result.strip() else "No differences found — schemas are equivalent."
        except Exception as e:
            return f"Error: {e}"

    @server.tool(
        name="check",
        description="Verify all schema files in a directory produce equivalent schemas. "
                    "Useful for CI/CD to ensure consistency across format representations.",
    )
    def check_tool(
        directory: str,
        canonical: str = "sql",
        type_map_path: str | None = None,
    ) -> str:
        """Check schema consistency in a directory.

        Args:
            directory: Path to directory containing schema files.
            canonical: Canonical format for comparison (default: sql).
            type_map_path: Optional path to a YAML/JSON type mapping config file.
        """
        try:
            result = check_directory(directory, canonical=canonical, type_map_path=type_map_path)
            return result
        except NotADirectoryError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error: {e}"

    @server.tool(
        name="formats",
        description="List all supported schema formats with their descriptions. "
                    "Returns the list of format identifiers and what they represent.",
    )
    def formats_tool() -> str:
        """List all supported schema formats."""
        lines = ["Supported SchemaForge formats:", ""]
        for fmt in _FORMATS:
            desc = _FORMAT_DESCRIPTIONS.get(fmt, "")
            bidirectional = "✓" if fmt != "alembic" else "— (generator only)"
            lines.append(f"  {fmt:15s} {desc}")
            lines.append(f"  {'':15s} Bidirectional: {bidirectional}")
            lines.append("")
        return "\n".join(lines)

    @server.tool(
        name="detect_format",
        description="Detect the schema format from a filename or file extension. "
                    "Returns the format identifier or 'unknown' if not recognized.",
    )
    def detect_format_tool(filename: str) -> str:
        """Detect schema format from filename.

        Args:
            filename: Name or path of the schema file.
        """
        fmt = detect_format(filename)
        if fmt:
            return fmt
        # Also try by extension
        ext = Path(filename).suffix.lower()
        ext_map = {
            ".sql": "sql",
            ".prisma": "prisma",
            ".ts": "drizzle",
            ".tsx": "drizzle",
            ".py": "django",
            ".json": "json_schema",
            ".graphql": "graphql",
            ".gql": "graphql",
        }
        fmt = ext_map.get(ext)
        return fmt if fmt else f"unknown (extension: {ext})"

    return server


@click.command(name="mcp")
@click.option("--sse", is_flag=True, help="Run as SSE HTTP server instead of stdio")
@click.option("--host", default="127.0.0.1", help="SSE host (default: 127.0.0.1)")
@click.option("--port", default=8000, type=int, help="SSE port (default: 8000)")
def mcp_command(sse: bool, host: str, port: int) -> None:
    """Run SchemaForge as an MCP (Model Context Protocol) server.

    By default runs in stdio mode for AI clients (Claude Desktop, Cursor, etc.).
    Use --sse for HTTP transport.
    """
    server = create_server()

    if sse:
        click.echo(f"Starting SchemaForge MCP server on http://{host}:{port}", err=True)
        server.run(transport="sse", host=host, port=port)
    else:
        server.run(transport="stdio")
