"""Schema conversion: all format pairs via the IR."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .ir import Schema
from .parsers.sql_parser import SQLParser
from .generators.sql_generator import SQLGenerator
from .parsers.prisma_parser import PrismaParser
from .generators.prisma_generator import PrismaGenerator
from .parsers.drizzle_parser import DrizzleParser
from .generators.drizzle_generator import DrizzleGenerator
from .parsers.typeorm_parser import TypeORMParser
from .generators.typeorm_generator import TypeORMGenerator
from .parsers.django_parser import DjangoParser
from .generators.django_generator import DjangoGenerator
from .parsers.sqlalchemy_parser import SQLAlchemyParser
from .generators.sqlalchemy_generator import SQLAlchemyGenerator
from .parsers.alembic_parser import AlembicParser
from .generators.alembic_generator import AlembicGenerator
from .parsers.json_schema_parser import JSONSchemaParser
from .generators.json_schema_generator import JSONSchemaGenerator
from .parsers.graphql_parser import GraphQLParser
from .generators.graphql_generator import GraphQLGenerator

if TYPE_CHECKING:
    from .type_config import TypeConfig


_registry: dict[str, tuple[type, type]] = {
    "sql": (SQLParser, SQLGenerator),
    "prisma": (PrismaParser, PrismaGenerator),
    "drizzle": (DrizzleParser, DrizzleGenerator),
    "typeorm": (TypeORMParser, TypeORMGenerator),
    "django": (DjangoParser, DjangoGenerator),
    "sqlalchemy": (SQLAlchemyParser, SQLAlchemyGenerator),
    "alembic": (AlembicParser, AlembicGenerator),
    "json_schema": (JSONSchemaParser, JSONSchemaGenerator),
    "graphql": (GraphQLParser, GraphQLGenerator),
}


def convert_schema(
    input_text: str,
    from_fmt: str,
    to_fmt: str,
    type_config: TypeConfig | None = None,
) -> str:
    """Convert schema text from one format to another via the IR.

    Args:
        input_text: Schema text in the source format.
        from_fmt: Source format name (e.g. 'sql', 'prisma').
        to_fmt: Target format name (e.g. 'django', 'alembic').
        type_config: Optional type mapping overrides.

    Returns:
        Schema text in the target format.

    Raises:
        ValueError: If either format is not supported.
    """
    if from_fmt == to_fmt:
        return input_text

    if from_fmt not in _registry:
        raise ValueError(f"Unsupported source format: {from_fmt}")
    if to_fmt not in _registry:
        raise ValueError(f"Unsupported target format: {to_fmt}")

    parser_cls, _ = _registry[from_fmt]
    _, generator_cls = _registry[to_fmt]

    parser = parser_cls()
    schema = parser.parse(input_text)

    generator = generator_cls(type_config=type_config)
    return generator.generate(schema)


def register_format(name: str, parser_cls: type, generator_cls: type) -> None:
    """Register a new format pair (for extensibility)."""
    _registry[name] = (parser_cls, generator_cls)
