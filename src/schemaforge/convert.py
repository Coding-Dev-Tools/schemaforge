"""Schema conversion: all format pairs via the IR."""
from __future__ import annotations

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


_registry: dict[str, tuple[type, type]] = {
    "sql": (SQLParser, SQLGenerator),
    "prisma": (PrismaParser, PrismaGenerator),
    "drizzle": (DrizzleParser, DrizzleGenerator),
    "typeorm": (TypeORMParser, TypeORMGenerator),
    "django": (DjangoParser, DjangoGenerator),
    "sqlalchemy": (SQLAlchemyParser, SQLAlchemyGenerator),
}


def convert_schema(input_text: str, from_fmt: str, to_fmt: str) -> str:
    """Convert schema text from one format to another via the IR."""
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

    generator = generator_cls()
    return generator.generate(schema)


def register_format(name: str, parser_cls: type, generator_cls: type) -> None:
    """Register a new format pair (for extensibility)."""
    _registry[name] = (parser_cls, generator_cls)
