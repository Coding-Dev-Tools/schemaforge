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


_registry: dict[str, tuple[type, type]] = {
    "sql": (SQLParser, SQLGenerator),
    "prisma": (PrismaParser, PrismaGenerator),
    "drizzle": (DrizzleParser, DrizzleGenerator),
    "typeorm": (TypeORMParser, TypeORMGenerator),
    "django": (DjangoParser, DjangoGenerator),
}
