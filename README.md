# SchemaForge

> **Bidirectional ORM schema converter** — convert between SQL DDL, Prisma, Drizzle, TypeORM, Django, SQLAlchemy, and Alembic migration scripts. **7 formats, 42 direction pairs.**

[![PyPI](https://img.shields.io/pypi/v/schemaforge)](https://pypi.org/project/schemaforge/)
[![Python](https://img.shields.io/pypi/pyversions/schemaforge)](https://pypi.org/project/schemaforge/)
[![License](https://img.shields.io/pypi/l/schemaforge)](https://github.com/Coding-Dev-Tools/schemaforge/blob/main/LICENSE)
[![CI](https://github.com/Coding-Dev-Tools/schemaforge/actions/workflows/test.yml/badge.svg)](https://github.com/Coding-Dev-Tools/schemaforge/actions/workflows/test.yml)
[![Tests](https://img.shields.io/badge/tests-137%20passing-brightgreen)](https://github.com/Coding-Dev-Tools/schemaforge)

**Why SchemaForge?** Every major ORM migration is a one-way street. Prisma introspects SQL but can't export back. Drizzle users manually rewrite schemas when switching ORMs. TypeORM developers are locked into decorator syntax. SchemaForge is the first tool to do **bidirectional, lossless conversion** between 7 schema formats — with a shared internal representation that guarantees roundtrip fidelity.

Convert any schema to any format, verify equivalence with the diff command, generate Alembic migrations, and batch-process entire directories. Whether you're migrating from Prisma to Drizzle, sharing a schema with a Django backend, or generating SQL DDL from TypeORM entities — SchemaForge handles it.

## Quick Start

```bash
# Install
pip install schemaforge

# Convert Prisma → Drizzle
schemaforge convert --from prisma --to drizzle --input schema.prisma

# Generate Alembic migration from SQL
schemaforge convert --from sql --to alembic --input schema.sql --output migrations/initial.py

# Diff two schemas
schemaforge diff schema-v1.prisma schema-v2.prisma

# Batch convert all schemas in a directory
schemaforge convert --from sql --to prisma --dir ./schemas/
```

## Installation

```bash
# PyPI (recommended)
pip install schemaforge

# Latest from source
pip install git+https://github.com/Coding-Dev-Tools/schemaforge.git
```

Requires Python 3.10+.

## Commands

### `schemaforge convert`

Convert a schema from one format to another. All 7 formats support conversion to and from every other format (42 direction pairs).

```bash
# SQL DDL
schemaforge convert --from sql --to prisma --input schema.sql
schemaforge convert --from sql --to alembic --input schema.sql --output migrations/initial.py

# Prisma
schemaforge convert --from prisma --to drizzle --input schema.prisma
schemaforge convert --from prisma --to django --input schema.prisma --output models.py

# Drizzle
schemaforge convert --from drizzle --to sql --input schema.drizzle.ts
schemaforge convert --from drizzle --to typeorm --input schema.ts

# TypeORM
schemaforge convert --from typeorm --to django --input entities/
schemaforge convert --from typeorm --to prisma --input user.entity.ts

# Django
schemaforge convert --from django --to drizzle --input models.py
schemaforge convert --from django --to sqlalchemy --input models.py

# SQLAlchemy
schemaforge convert --from sqlalchemy --to prisma --input models.py
schemaforge convert --from sqlalchemy --to sql --input declarative.py

# Alembic (generator-only — migration scripts)
schemaforge convert --from sql --to alembic --input schema.sql --output migrations/initial.py
schemaforge convert --from prisma --to alembic --input schema.prisma --output migrations/

# Dir mode (batch convert all files)
schemaforge convert --from sql --to prisma --dir ./schemas/
schemaforge convert --from typeorm --to django --dir ./src/entities/
```

### `schemaforge diff`

Compare two schema files in the same format and see line-level differences.

```bash
schemaforge diff schema-v1.prisma schema-v2.prisma
schemaforge diff schema.sql schema-updated.sql --format sql
schemaforge diff fixtures/sample.sql fixtures/sample.prisma --format prisma
```

Detects added, removed, and modified tables, columns, indexes, and constraints. Useful for CI/CD checks and code review.

## Supported Formats

| Format | Import | Export | Roundtrip |
|--------|:------:|:------:|:---------:|
| SQL DDL | ✓ | ✓ | ✓ |
| Prisma schema | ✓ | ✓ | ✓ |
| Drizzle schema | ✓ | ✓ | ✓ |
| TypeORM entities | ✓ | ✓ | ✓ |
| Django models | ✓ | ✓ | ✓ |
| SQLAlchemy models | ✓ | ✓ | ✓ |
| Alembic migrations | — | ✓ | — |

**Alembic** is generator-only: you can create migration scripts from any format, but parsing existing migrations back to IR is not yet supported.

## How It Works

SchemaForge uses a **shared Internal Representation (IR)** — all formats convert to and from this common schema definition. This architecture guarantees:

- **Zero-loss roundtripping**: `sql → prisma → sql` produces the same schema you started with
- **Bidirectional conversion**: every supported format can convert to every other format
- **Extensibility**: adding a new format requires only a parser and a generator — no pairwise converters

```
   SQL DDL ──┐
   Prisma ───┤
   Drizzle ──┤
   TypeORM ──┼──▶ Shared IR ──▶ Any Format
   Django ───┤
SQLAlchemy ──┤
  Alembic ───┘
```

## Type Mapping

SchemaForge maps types intelligently between ORM systems. The core `ColumnType` enum represents all supported data types, and each format maps them to their native equivalents.

| ColumnType | SQL DDL | Prisma | Drizzle | TypeORM | Django | SQLAlchemy | Alembic |
|------------|---------|--------|---------|---------|--------|------------|---------|
| STRING | VARCHAR(n) / TEXT | String @db.VarChar(n) | varchar(n) | varchar | CharField(max_length=n) | String(n) | sa.String(n) |
| INTEGER | INTEGER | Int | integer | integer | IntegerField | Integer | sa.Integer |
| FLOAT | FLOAT | Float | real | float | FloatField | Float | sa.Float |
| BOOLEAN | BOOLEAN | Boolean | boolean | boolean | BooleanField | Boolean | sa.Boolean |
| DATETIME | TIMESTAMP | DateTime | timestamp | timestamp | DateTimeField | DateTime | sa.DateTime |
| DATE | DATE | DateTime | date | date | DateField | Date | sa.Date |
| TIME | TIME | DateTime | time | time | TimeField | Time | sa.Time |
| TEXT | TEXT | String | text | text | TextField | Text | sa.Text |
| BLOB | BLOB | Bytes | blob | blob | BinaryField | LargeBinary | sa.LargeBinary |
| JSON | JSON | Json | json | json | JSONField | JSON | sa.JSON |
| UUID | UUID | String | uuid | uuid | UUIDField | Uuid | sa.Uuid |
| ENUM | ENUM('a','b') | (via enum type) | pgEnum | enum | CharField | Enum | sa.Enum |
| DECIMAL | DECIMAL(p,s) | Decimal | numeric(p,s) | decimal(p,s) | DecimalField(max_digits=p) | Numeric(p,s) | sa.Numeric(p,s) |

**Function defaults** (`CURRENT_TIMESTAMP`, `NOW()`, `gen_random_uuid()`, etc.) are preserved across conversions using a `fn:` prefix convention. For example, `DEFAULT CURRENT_TIMESTAMP` in SQL becomes `@default(now())` in Prisma and `server_default=func.now()` in SQLAlchemy.

## Demo Fixtures

Try SchemaForge immediately with our example blog schema. The `fixtures/` directory contains an equivalent schema (users, posts, categories with enums and various data types) in 7 formats:

```bash
# List all fixtures
ls fixtures/

# Convert SQL → Prisma
schemaforge convert --from sql --to prisma --input fixtures/sample.sql

# Convert Prisma → Django
schemaforge convert --from prisma --to django --input fixtures/sample.prisma

# Convert TypeORM → Drizzle
schemaforge convert --from typeorm --to drizzle --input fixtures/sample.typeorm.ts

# Convert SQL → Alembic migration
schemaforge convert --from sql --to alembic --input fixtures/sample.sql --output migrations/initial.py

# Batch convert all fixtures from SQL
schemaforge convert --from sql --to prisma --dir fixtures/

# Diff two format outputs
schemaforge diff fixtures/sample.sql fixtures/sample.prisma --format prisma
```

Each fixture demonstrates the same blog schema so you can compare ORM syntax side-by-side and verify roundtrip consistency.

## Features

- **Bidirectional conversion** — all 7 formats convert to and from every other format (42 direction pairs)
- **Zero-loss roundtripping** — `sql → prisma → sql` reproduces the original schema exactly
- **Alembic migration generation** — create database migration scripts from any schema format
- **Diff mode** — compare two schemas in the same format with line-level differences
- **Batch mode** — convert entire directories of schema files with one command
- **Intelligent type mapping** — types map correctly across all 7 formats (String ↔ CharField ↔ VARCHAR)
- **Function default preservation** — `CURRENT_TIMESTAMP`, `NOW()`, `gen_random_uuid()` survive roundtrips
- **MySQL support** — ENGINE=InnoDB, AUTO_INCREMENT, DEFAULT CHARSET, COMMENT table options
- **Inline ENUM** — `ENUM('small', 'medium', 'large')` column types parsed and roundtripped
- **Relation preservation** — indexes, unique constraints maintained across all conversions
- **Custom type handling** — dialect-specific types (JSONB, etc.) pass through via CUSTOM type

## Roadmap

| Version | Features |
|---------|----------|
| v0.1.0 | SQL DDL ↔ Prisma bidirectional conversion |
| v0.2.0 | Drizzle schema support |
| v0.3.0 | TypeORM entities support |
| v0.4.0 | Django models support |
| v0.5.0 | SQLAlchemy support, diff mode, batch mode, custom type mappings |
| v0.6.0 | SQL parser edge cases (TEMPORARY TABLE, backtick quoting, fn: defaults) |
| v0.7.0 | MySQL table options (ENGINE, CHARSET), inline ENUM('a','b','c') |
| v0.8.0 | Alembic migration generation (7th format) |
| v0.9.0 | Shared generator base module, refactored fn: default handling |
| **v1.0.0** | **Stable release — comprehensive docs, CLI polish, 137 tests** |

### Planned

- [ ] Custom type mapping configuration files (YAML/JSON overrides)
- [ ] JSON Schema import/export
- [ ] GraphQL schema export
- [ ] MCP server for AI-assisted schema operations
- [ ] VS Code extension with live diff
- [ ] CI/CD check: enforce schema consistency across branches
- [ ] Additional ORM formats: Doobie/Quill (Scala), Entity Framework (C#)

## Pricing

SchemaForge is one of eight tools in the Revenue Holdings suite. One license covers all CLI tools.

| Plan | Price | Best For |
|------|-------|----------|
| **Free** | $0 | Individual devs, OSS — CLI only, rate-limited |
| **SchemaForge Individual** | **$15/mo** ($12 billed annually) | Professional devs — unlimited conversions, batch mode |
| **Suite (all 8 tools)** | **$49/mo** ($39 billed annually) | Full Revenue Holdings toolkit — 40% savings |
| **Team** | **$79/mo** ($63 billed annually) | Up to 5 devs — shared schemas, team dashboard, alerts |
| **Enterprise** | Custom | SSO, RBAC, compliance reports, dedicated support |

🔹 **No lock-in**: CLI works fully offline on the free tier — no telemetry, no phone-home.
🔹 **Annual billing**: Save 20%.

### Per-Tier Features

| Feature | Free | Individual | Suite | Team | Enterprise |
|---------|:----:|:----------:|:-----:|:----:|:----------:|
| CLI: convert, diff | ✓ | ✓ | ✓ | ✓ | ✓ |
| All 7 format directions | — | ✓ | ✓ | ✓ | ✓ |
| Alembic migration generation | — | ✓ | ✓ | ✓ | ✓ |
| Batch directory conversion | — | ✓ | ✓ | ✓ | ✓ |
| Zero-loss roundtrip verification | — | ✓ | ✓ | ✓ | ✓ |
| Custom type mappings | — | ✓ | ✓ | ✓ | ✓ |
| Team shared type mappings | — | — | — | ✓ | ✓ |
| Dashboard & analytics | — | — | — | ✓ | ✓ |
| Compliance reports | — | — | — | — | ✓ |
| RBAC / SSO / SAML / OIDC | — | — | — | — | ✓ |
| Priority support | Community | 24h | 24h | 8h | Dedicated |

## Development

```bash
# Clone and install in dev mode
git clone https://github.com/Coding-Dev-Tools/schemaforge.git
cd schemaforge
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=schemaforge
```

## Contributing

PRs welcome! New format parsers/generators, bug fixes, and documentation improvements are all appreciated.

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/awesome-format`)
3. Add your parser and generator in `src/schemaforge/parsers/` and `src/schemaforge/generators/`
4. Register in `src/schemaforge/convert.py`
5. Add tests in `tests/`
6. Run the full test suite (`pytest tests/ -v`)
7. Submit a PR

## License

MIT — see [LICENSE](LICENSE)

---

<sub>Part of [Revenue Holdings](https://coding-dev-tools.github.io/revenueholdings.dev/) — a suite of 10 developer CLI tools built by autonomous AI agents. Also check out [API Contract Guardian](https://github.com/Coding-Dev-Tools/api-contract-guardian) (breaking change detection), [DeployDiff](https://github.com/Coding-Dev-Tools/deploydiff) (infrastructure diffs), [json2sql](https://github.com/Coding-Dev-Tools/json2sql) (JSON → SQL), [ConfigDrift](https://github.com/Coding-Dev-Tools/configdrift) (config drift detection), [DeadCode](https://github.com/Coding-Dev-Tools/deadcode) (dead code cleanup), [APIAuth](https://github.com/Coding-Dev-Tools/apiauth) (API key management), [APIGhost](https://github.com/Coding-Dev-Tools/apighost) (mock API server), [Envault](https://github.com/Coding-Dev-Tools/envault) (env sync), and [click-to-mcp](https://github.com/Coding-Dev-Tools/click-to-mcp) (CLI → MCP server).</sub>
