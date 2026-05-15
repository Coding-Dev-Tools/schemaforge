"""SchemaForge CLI — bidirectional ORM schema converter."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from .convert import convert_schema
from .diff import diff_schemas
from .type_config import TypeConfig

# All supported format names (used for CLI choices and detection)
_FORMATS = ["sql", "prisma", "drizzle", "typeorm", "django", "sqlalchemy", "alembic", "json_schema", "graphql"]


@click.group()
@click.version_option()
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


def _detect_format(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".sql":
        return "sql"
    if ext == ".prisma":
        return "prisma"
    if ext in (".ts", ".tsx"):
        return "drizzle"
    if ext == ".py":
        return "django"
    if ext in (".json",):
        return "typeorm"
    return "sql"  # default
