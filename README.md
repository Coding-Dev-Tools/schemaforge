# SchemaForge

> **Bidirectional ORM schema converter** — convert between SQL DDL, Prisma, Drizzle, TypeORM, Django, SQLAlchemy, Alembic migrations, JSON Schema, GraphQL SDL, EF Core (C#), and Scala case classes. **11 formats, 110 direction pairs.**

[![GitHub stars](https://img.shields.io/github/stars/Coding-Dev-Tools/schemaforge?style=social)](https://github.com/Coding-Dev-Tools/schemaforge/stargazers)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/Coding-Dev-Tools/schemaforge)
[![License](https://img.shields.io/github/license/Coding-Dev-Tools/schemaforge)](https://github.com/Coding-Dev-Tools/schemaforge/blob/main/LICENSE)
[![CI](https://github.com/Coding-Dev-Tools/schemaforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Coding-Dev-Tools/schemaforge/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-298%20passing-brightgreen)](https://github.com/Coding-Dev-Tools/schemaforge)
[![VS Code](https://img.shields.io/badge/VS%20Code-extension-blue)](https://marketplace.visualstudio.com/items?itemName=revenue-holdings.vscode-schemaforge)
[![Open Source Alternative](https://img.shields.io/badge/Open_Source_Alternative-%E2%87%92-blue?logo=opensourceinitiative)](https://www.opensourcealternative.to/project/schemaforge)

**Why SchemaForge?**

Convert any schema to any format, verify equivalence with the diff command, generate Alembic migrations, produce JSON Schema definitions, create GraphQL SDL types, convert Entity Framework (C#) entities, generate Scala case classes, and batch-process entire directories. Whether you're migrating from Prisma to Drizzle, sharing a schema with a Django backend, exposing your data model as GraphQL, translating C# entities to Scala, or working with the SchemaForge VS Code extension for live preview — SchemaForge handles it.

## Quick Start

```bash
# Install (package publishing pending — install from source)
pip install git+https://github.com/Coding-Dev-Tools/schemaforge.git

# Convert Prisma → Drizzle
schemaforge convert --from prisma --to drizzle --input schema.prisma

# Generate GraphQL from SQL
schemaforge convert --from sql --to graphql --input schema.sql --output schema.graphql

# Generate JSON Schema from Prisma
schemaforge convert --from prisma --to json_schema --input schema.prisma --output schema.json

# Generate Alembic migration from SQL
schemaforge convert --from sql --to alembic --input schema.sql --output migrations/initial.py

# Apply custom type mappings
schemaforge convert --from sql --to prisma --input schema.sql --type-map my-types.yaml

# Diff two schemas
schemaforge diff schema-v1.prisma schema-v2.prisma

# Check all schemas in a directory are consistent
schemaforge check --dir ./schemas/
```

## Installation

```bash
# Install from source (recommended — PyPI publishing pending)
pip install git+https://github.com/Coding-Dev-Tools/schemaforge.git
```

Requires Python 3.10+.

## Commands

### `schemaforge convert`

Convert a schema from one format to another. All 11 formats support conversion to and from every other format (110 direction pairs).

```bash
# Format-specific examples
schemaforge convert --from sql --to prisma --input schema.sql
schemaforge convert --from prisma --to drizzle --input schema.prisma
schemaforge convert --from drizzle --to sql --input schema.drizzle.ts
schemaforge convert --from typeorm --to django --input entities/
schemaforge convert --from django --to sqlalchemy --input models.py
schemaforge convert --from sqlalchemy --to prisma --input models.py

# Alembic migration generation
schemaforge convert --from sql --to alembic --input schema.sql --output migrations/initial.py
schemaforge convert --from prisma --to alembic --input schema.prisma --output migrations/

# JSON Schema
schemaforge convert --from sql --to json_schema --input schema.sql --output schema.json
schemaforge convert --from json_schema --to prisma --input schema.json

# GraphQL SDL
schemaforge convert --from sql --to graphql --input schema.sql --output schema.graphql
schemaforge convert --from graphql --to prisma --input schema.graphql

# Custom type mapping
schemaforge convert --from sql --to prisma --input schema.sql --type-map my-types.yaml

# Dir mode (check all files are consistent)
schemaforge check --dir ./schemas/ --canonical prisma
```

### `schemaforge diff`

Compare two schema files in the same format and see line-level differences.

```bash
schemaforge diff schema-v1.prisma schema-v2.prisma
schemaforge diff schema.sql schema-updated.sql --format sql
schemaforge diff fixtures/sample.sql fixtures/sample.prisma --format prisma
```

Detects added, removed, and modified tables, columns, indexes, and constraints.

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
| JSON Schema | ✓ | ✓ | ✓ |
| GraphQL SDL | ✓ | ✓ | ✓ |
| EF Core (C#) | ✓ | ✓ | ✓ |
| Scala case class | ✓ | ✓ | ✓ |

**Alembic** is generator-only: you can create migration scripts from any format, but parsing existing migrations back to IR is not yet supported.

### Format Identifiers for `--from` / `--to`

| CLI identifier | Format |
|----------------|--------|
| `sql` | SQL DDL |
| `prisma` | Prisma schema |
| `drizzle` | Drizzle ORM schema |
| `typeorm` | TypeORM entities |
| `django` | Django models |
| `sqlalchemy` | SQLAlchemy declarative models |
| `alembic` | Alembic migration scripts |
| `json_schema` | JSON Schema (draft 2020-12) |
| `graphql` | GraphQL SDL |
| `ef` | Entity Framework Core (C#) |
| `scala` | Scala case classes (Doobie/Quill/Slick) |

## How It Works

SchemaForge uses a **shared Internal Representation (IR)** — all formats convert to and from this common schema definition. This architecture guarantees:

- **Zero-loss roundtripping**: `sql → prisma → sql` produces the same schema you started with
- **Bidirectional conversion**: every supported format can convert to every other format
- **Extensibility**: adding a new format requires only a parser and a generator — no pairwise converters

```
|    SQL DDL ───┐
|    Prisma ────┤
|    Drizzle ───┤
|    TypeORM ───┤
|    Django ────┤
| SQLAlchemy ───┤
|   Alembic ────┤
| JSON Schema ──┤
|   GraphQL ────┤
|  EF Core ─────┤
|    Scala ─────┤
```

Each parser reads format-specific syntax and builds a schema IR. Each generator takes the same IR and produces format-native output. The `fn:` prefix convention preserves SQL function defaults (CURRENT_TIMESTAMP, NOW(), gen_random_uuid()) across format boundaries.

## Custom Type Mappings (v1.1.0+)

Override default type mappings with YAML or JSON configuration files.

```yaml
# type-overrides.yaml
overrides:
  prisma:
    STRING: "String @db.VarChar({length})"
    UUID: "String @db.Uuid"
  sql:
    STRING: "TEXT"
    DATETIME: "TIMESTAMP WITH TIME ZONE"
```

Template variables available: `{length}`, `{precision}`, `{scale}`, `{values}`.

```bash
# Apply overrides during conversion
schemaforge convert --from sql --to prisma --input schema.sql --type-map type-overrides.yaml
```

## Type Mapping

SchemaForge maps types intelligently between ORM systems. The core `ColumnType` enum represents all supported data types, and each format maps them to their native equivalents.

| ColumnType | SQL DDL | Prisma | Drizzle | TypeORM | Django | SQLAlchemy | Alembic | JSON Schema | GraphQL |
|------------|---------|--------|---------|---------|--------|------------|---------|-------------|---------|
| STRING | VARCHAR(n) / TEXT | String @db.VarChar(n) | varchar(n) | varchar | CharField(max_length=n) | String(n) | sa.String(n) | type: string | String |
| INTEGER | INTEGER | Int | integer | integer | IntegerField | Integer | sa.Integer | type: integer | Int |
| FLOAT | FLOAT | Float | real | float | FloatField | Float | sa.Float | type: number | Float |
| BOOLEAN | BOOLEAN | Boolean | boolean | boolean | BooleanField | Boolean | sa.Boolean | type: boolean | Boolean |
| DATETIME | TIMESTAMP | DateTime | timestamp | timestamp | DateTimeField | DateTime | sa.DateTime | format: date-time | DateTime |
| DATE | DATE | DateTime | date | date | DateField | Date | sa.Date | format: date | Date |
| TIME | TIME | DateTime | time | time | TimeField | Time | sa.Time | format: time | Time |
| TEXT | TEXT | String | text | text | TextField | Text | sa.Text | type: string | String |
| BLOB | BLOB | Bytes | blob | blob | BinaryField | LargeBinary | sa.LargeBinary | format: binary | String |
| JSON | JSON | Json | json | json | JSONField | JSON | sa.JSON | type: object | JSON |
| UUID | UUID | String | uuid | uuid | UUIDField | Uuid | sa.Uuid | format: uuid | ID |
| ENUM | ENUM('a','b') | (via enum) | pgEnum | enum | CharField | Enum | sa.Enum | (enum) | enum |
| DECIMAL | DECIMAL(p,s) | Decimal | numeric(p,s) | decimal(p,s) | DecimalField | Numeric(p,s) | sa.Numeric(p,s) | type: number | Float |
| CUSTOM | (passthrough) | (passthrough) | (passthrough) | (passthrough) | (passthrough) | (passthrough) | (passthrough) | (passthrough) | (passthrough) |

**Function defaults** (`CURRENT_TIMESTAMP`, `NOW()`, `gen_random_uuid()`, etc.) are preserved across conversions using a `fn:` prefix convention.

## Demo Fixtures

Try SchemaForge immediately with our example blog schema. The `fixtures/` directory contains an equivalent schema (users, posts, categories with enums and various data types) in all 11 formats:

```bash
# List all fixtures
ls fixtures/

# Convert SQL → Prisma
schemaforge convert --from sql --to prisma --input fixtures/sample.sql

# Convert Prisma → Django
schemaforge convert --from prisma --to django --input fixtures/sample.prisma

# Convert SQL → GraphQL
schemaforge convert --from sql --to graphql --input fixtures/sample.sql

# Convert SQL → JSON Schema
schemaforge convert --from sql --to json_schema --input fixtures/sample.sql

# Convert Prisma → Alembic migration
schemaforge convert --from prisma --to alembic --input fixtures/sample.prisma --output migrations/

# Custom type mapping demo
schemaforge convert --from sql --to prisma --input fixtures/sample.sql \
  --type-map fixtures/sample-type-overrides.yaml

# Batch convert all fixtures from SQL
schemaforge check --dir fixtures/

# Diff two format outputs
schemaforge diff fixtures/sample.sql fixtures/sample.prisma --format prisma
```

Each fixture demonstrates the same blog schema so you can compare ORM syntax side-by-side and verify roundtrip consistency.

## Features

- **Bidirectional conversion** — all 11 formats convert to and from every other format
- **Zero-loss roundtripping** — `sql → prisma → sql` reproduces the original schema exactly
- **Custom type mappings** — YAML/JSON config files to override any type mapping with template variables
- **VS Code extension** — live preview, schema diff, and one-click conversion from VS Code
- **Alembic migration generation** — create database migration scripts from any schema format
- **JSON Schema** — import/export schema definitions as JSON Schema (draft 2020-12)
- **GraphQL SDL** — generate or consume GraphQL type definitions with enums, directives, and scalars
- **EF Core (C#) support** — import/export Entity Framework entity classes with data annotations
- **Scala case class support** — generate case classes targeting Doobie/Quill/Slick
- **Diff mode** — compare two schemas in the same format with line-level differences
- **Batch mode** — convert entire directories of schema files with one command
- **Intelligent type mapping** — types map correctly across all 11 formats
- **Function default preservation** — `CURRENT_TIMESTAMP`, `NOW()`, `gen_random_uuid()` survive roundtrips
- **MySQL support** — ENGINE=InnoDB, AUTO_INCREMENT, DEFAULT CHARSET, COMMENT table options
- **Inline ENUM** — `ENUM('small', 'medium', 'large')` column types parsed and roundtripped
- **Relation preservation** — indexes, unique constraints maintained across all conversions
- **Custom type handling** — dialect-specific types (JSONB, etc.) pass through via CUSTOM type

## MCP Server

SchemaForge includes an **MCP (Model Context Protocol) server** that exposes all schema operations as tools for AI agents. This allows AI coding assistants like Claude Code, Cursor, and others to convert, diff, and check schemas directly.

```bash
# Install with MCP support
pip install "schemaforge[mcp] @ git+https://github.com/Coding-Dev-Tools/schemaforge.git"

# Start the server (stdio mode — default for AI clients)
schemaforge mcp

# Start as SSE HTTP server
schemaforge mcp --sse --port 8000
```

### Available Tools

| Tool | Description |
|------|-------------|
| `convert` | Convert a schema between any two of the 11 formats |
| `diff` | Compare two schemas and show differences |
| `check` | Verify schema consistency across a directory |
| `formats` | List all supported formats with descriptions |
| `detect_format` | Identify format from filename |

### Configuration for AI Clients

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "schemaforge": {
      "command": "schemaforge",
      "args": ["mcp"]
    }
  }
}
```

**Cursor**: Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "schemaforge": {
      "command": "schemaforge",
      "args": ["mcp"]
    }
  }
}
```

## VS Code Extension

The **SchemaForge VS Code extension** provides live schema preview, quick conversion, and schema diffing directly from your editor.

### Features

- **Live Preview** — opens a side panel showing your active schema file converted to all other formats (tabbed interface for quick comparison)
- **Quick Convert** — `Ctrl+Alt+S` / `Cmd+Alt+S` to convert the active editor's schema to your configured default target format
- **Format Detection** — `Ctrl+Alt+D` / `Cmd+Alt+D` to detect and display the format of the active schema file
- **Diff Two Schemas** — select two schema files to diff them side-by-side in VS Code's native diff editor
- **Right-Click Conversion** — right-click any schema file in the explorer to convert it
- **Custom Editor** — open `.schemaforge` files for a rich conversion preview
- **Auto-Refresh** — preview panel updates when you save a schema file or switch tabs

### Installation

1. Install SchemaForge: `pip install git+https://github.com/Coding-Dev-Tools/schemaforge.git`
2. Install the extension from the [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=devforge.vscode-schemaforge)
3. Open a `.sql`, `.prisma`, `.graphql`, `.cs`, or `.scala` file
4. Run `SchemaForge: Show Preview` from the command palette

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `schemaforge.cliPath` | `schemaforge` | Path to the schemaforge CLI executable |
| `schemaforge.defaultTargetFormat` | `prisma` | Default target format for quick conversions |
| `schemaforge.livePreview.enabled` | `true` | Enable live preview panel when editing schema files |

### Development

```bash
git clone https://github.com/Coding-Dev-Tools/vscode-schemaforge.git
cd vscode-schemaforge
npm install
npm run compile
# Press F5 in VS Code to launch extension host
```

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
| v1.0.0 | Stable release — comprehensive docs, CLI polish |
| v1.1.0 | Custom type mapping configuration (YAML/JSON overrides) |
| v1.2.0 | JSON Schema support (8th format) |
| **v1.3.0** | **GraphQL SDL support (9th format)** |
| v1.4.0 | Schema consistency check, CI/CD workflow, MCP server |
| **v1.5.0** | **Entity Framework Core (C#) support (10th format)** |
| **v1.6.0** | **Scala case class support (11th format)** |
| **v1.7.0** | **VS Code extension — live preview, diff, quick convert** |

### Planned

- [ ] VS Code extension: in-editor syntax highlighting for all 11 schema formats
- [ ] Live schema watch mode for automatic re-conversion on file change
- [ ] Mermaid/ERD diagram generation from schema IR
- [ ] Terraform/OpenTofu provider for schema drift detection
- [ ] Web dashboard with schema diff history

## Pricing

SchemaForge is one of 11 tools in the Revenue Holdings suite. One license covers all CLI tools.

| Plan | Price | Best For |
|------|-------|----------|
| **Free** | $0 | Individual devs, OSS — CLI only, rate-limited |
| **SchemaForge Individual** | **$15/mo** ($12 billed annually) | Professional devs — unlimited conversions, batch mode |
| **Suite (all 11 tools)** | **$49/mo** ($39 billed annually) | Full Revenue Holdings toolkit — 40% savings |
| **Team** | **$79/mo** ($63 billed annually) | Up to 5 devs — shared schemas, team dashboard, alerts |
| **Enterprise** | Custom | SSO, RBAC, compliance reports, dedicated support |

🔹 **No lock-in**: CLI works fully offline on the free tier — no telemetry, no phone-home.
🔹 **Annual billing**: Save 20%.

### Per-Tier Features

| Feature | Free | Individual | Suite | Team | Enterprise |
|---------|:----:|:----------:|:-----:|:----:|:----------:|
|| CLI: convert, diff | ✓ | ✓ | ✓ | ✓ | ✓ |
|| All 11 format directions | — | ✓ | ✓ | ✓ | ✓ |
|| Alembic migration generation | — | ✓ | ✓ | ✓ | ✓ |
|| JSON Schema import/export | — | ✓ | ✓ | ✓ | ✓ |
|| GraphQL SDL import/export | — | ✓ | ✓ | ✓ | ✓ |
|| MCP server (AI agent tools) | ✓ | ✓ | ✓ | ✓ | ✓ |
|| Custom type mappings | — | ✓ | ✓ | ✓ | ✓ |
|| Batch directory conversion | — | ✓ | ✓ | ✓ | ✓ |
|| Team shared type mappings | — | — | — | ✓ | ✓ |
|| Dashboard & analytics | — | — | — | ✓ | ✓ |
|| Compliance reports | — | — | — | — | ✓ |
|| RBAC / SSO / SAML / OIDC | — | — | — | — | ✓ |
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

<sub>Part of [Revenue Holdings](https://coding-dev-tools.github.io/revenueholdings.dev/) — a suite of 11 developer CLI tools built by autonomous AI agents. Also check out the [SchemaForge VS Code extension](https://github.com/Coding-Dev-Tools/vscode-schemaforge), [ConfigDrift](https://github.com/Coding-Dev-Tools/configdrift) (config drift detection), [DataMorph](https://github.com/Coding-Dev-Tools/datamorph) (data format conversion), [DeadCode](https://github.com/Coding-Dev-Tools/deadcode) (dead code cleanup), [DeployDiff](https://github.com/Coding-Dev-Tools/deploydiff) (infrastructure diffs), [Envault](https://github.com/Coding-Dev-Tools/envault) (env sync), [APIAuth](https://github.com/Coding-Dev-Tools/apiauth) (API key management), [APIGhost](https://github.com/Coding-Dev-Tools/apighost) (mock API server), [json2sql](https://github.com/Coding-Dev-Tools/json2sql) (JSON → SQL), [API Contract Guardian](https://github.com/Coding-Dev-Tools/api-contract-guardian) (breaking change detection), and [click-to-mcp](https://github.com/Coding-Dev-Tools/click-to-mcp) (CLI → MCP server).</sub>

