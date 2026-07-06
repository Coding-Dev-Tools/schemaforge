# SchemaForge

## Purpose
Bidirectional ORM schema converter — convert between SQL DDL, Prisma, Drizzle, TypeORM, Django, SQLAlchemy, Alembic migrations, JSON Schema, GraphQL SDL, EF Core (C#), and Scala case classes. 11 formats, 110 direction pairs.

## Build & Test Commands
- Install: `pip install -e .` or `pip install git+https://github.com/Coding-Dev-Tools/schemaforge.git`
- Test: `pytest` (310 tests)
- Lint: `ruff check .`
- Build: `pip wheel . --wheel-dir dist/`

## Architecture
Key directories:
- `src/schemaforge/` — Main package (CLI, converters, formats, diff, type mapping)
- `tests/` — 310 passing tests
- `fixtures/` — Test fixtures for various schema formats
- `scripts/` — Build/release scripts
- `.github/workflows/` — CI/CD (4 workflows)

## Conventions
- Language: Python 3.10+
- Test framework: pytest (310 tests passing)
- CI: GitHub Actions (4 workflows)
- Formatting: ruff (line-length 120)
- Type checking: py.typed included
- Package: setuptools with src layout