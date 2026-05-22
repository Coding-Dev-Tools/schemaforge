"""SchemaForge CLI — bidirectional ORM schema converter."""
from __future__ import annotations

import click
import sys
from pathlib import Path

from . import __version__
from .check import check_directory, detect_format
from .convert import convert_schema
from .diff import diff_schemas
from .mcp_server import mcp_command
from .type_config import TypeConfig

# All supported format names (used for CLI choices and detection)
_FORMATS = [
    "sql", "prisma", "drizzle", "typeorm", "django",
    "sqlalchemy", "alembic", "json_schema", "graphql", "ef", "scala",
]


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """SchemaForge — bidirectional ORM schema converter.

    Convert between SQL DDL, Prisma, Drizzle, TypeORM, Django, SQLAlchemy models,
    Alembic migrations, JSON Schema, and GraphQL SDL with zero-loss roundtripping.
    """



@main.command()
@click.option("--from", "from_fmt", required=True,
              type=click.Choice(_FORMATS),
              help="Source format")
@click.option("--to", "to_fmt", required=True,
              type=click.Choice(_FORMATS),
              help="Target format")
@click.option("--input", "-i", "input_path", required=True,
              type=click.Path(exists=True, readable=True),
              help="Input file path")
@click.option("--output", "-o", "output_path",
              type=click.Path(writable=True),
              help="Output file path (default: stdout)")
@click.option("--type-map", "type_map_path",
              type=click.Path(exists=True, readable=True),
              help="Custom type mapping config file (.yaml or .json)")
def convert(from_fmt: str, to_fmt: str, input_path: str,
            output_path: str | None, type_map_path: str | None) -> None:
    """Convert schema between formats."""
    # Load custom type mapping if specified
    type_config: TypeConfig | None = None
    if type_map_path:
        try:
            type_config = TypeConfig.from_file(type_map_path)
        except (FileNotFoundError, ValueError, ImportError) as e:
            click.echo(f"Error loading type map: {e}", err=True)
            sys.exit(1)

    input_text = Path(input_path).read_text(encoding="utf-8")
    try:
        result = convert_schema(input_text, from_fmt, to_fmt, type_config=type_config)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if output_path:
        Path(output_path).write_text(result, encoding="utf-8")
        click.echo(f"Written to {output_path}")
    else:
        click.echo(result)


@main.command()
@click.argument("file_a", type=click.Path(exists=True, readable=True))
@click.argument("file_b", type=click.Path(exists=True, readable=True))
@click.option("--format", "fmt", default="auto",
              type=click.Choice(["auto"] + _FORMATS),
              help="Schema format (auto = detect from extension)")
def diff(file_a: str, file_b: str, fmt: str) -> None:
    """Show differences between two schema files."""
    text_a = Path(file_a).read_text(encoding="utf-8")
    text_b = Path(file_b).read_text(encoding="utf-8")

    if fmt == "auto":
        fmt = _detect_format(file_a)

    try:
        result = diff_schemas(text_a, text_b, fmt)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(result)


@main.command()
@click.option("--dir", "directory", required=True,
              type=click.Path(exists=True, file_okay=False, readable=True),
              help="Directory containing schema files to check")
@click.option("--canonical", default="sql",
              type=click.Choice([f for f in _FORMATS if f != "alembic"]),
              help="Canonical format for comparison (default: sql)")
@click.option("--type-map", "type_map_path",
              type=click.Path(exists=True, readable=True),
              help="Custom type mapping config file (.yaml or .json)")
def check(directory: str, canonical: str, type_map_path: str | None) -> None:
    """Verify all schema files in a directory produce equivalent schemas.

    Converts every schema file to the canonical format and compares
    them pairwise. Useful for CI/CD pipelines to ensure schema
    consistency across format representations.
    """
    try:
        result = check_directory(directory, canonical=canonical,
                                 type_map_path=type_map_path)
        click.echo(result)
        if "FAIL" in result and "PASS" not in result:
            sys.exit(1)
    except (NotADirectoryError, ValueError, FileNotFoundError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Register the MCP server subcommand
main.add_command(mcp_command)


def _detect_format(path: str) -> str:
    """Detect schema format from file extension, falling back to sql."""
    return detect_format(path) or "sql"

