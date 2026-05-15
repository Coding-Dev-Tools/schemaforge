# SchemaForge

| SchemaForge **Bidirectional ORM schema converter — convert between SQL DDL, Prisma, Drizzle, TypeORM, Django, and SQLAlchemy models with zero-loss roundtripping.**

[![PyPI](https://img.shields.io/pypi/v/schemaforge)](https://pypi.org/project/schemaforge/)
[![Python](https://img.shields.io/pypi/pyversions/schemaforge)](https://pypi.org/project/schemaforge/)
[![License](https://img.shields.io/pypi/l/schemaforge)](https://github.com/Coding-Dev-Tools/schemaforge/blob/main/LICENSE)
[![CI](https://github.com/Coding-Dev-Tools/schemaforge/actions/workflows/test.yml/badge.svg)](https://github.com/Coding-Dev-Tools/schemaforge/actions/workflows/test.yml)

**Why SchemaForge?** Every major ORM migration is a one-way street. Prisma can introspect SQL but can't export back. Drizzle users manually rewrite schemas when switching ORMs. TypeORM developers are locked into decorator syntax. No tool does bidirectional, lossless conversion between 5+ ORM formats — until now.

SchemaForge fills this gap. Convert any schema to any format, verify equivalence with the diff command, and batch-process entire directories. Whether you're migrating from Prisma to Drizzle, sharing a schema with a Django backend, or generating SQL DDL from TypeORM entities, SchemaForge handles it with zero information loss.

## Quick Start

```bash
pip install schemaforge
```bash
# Convert Prisma → Drizzle
schemaforge convert --from prisma --to drizzle --input schema.prisma

# Diff two schemas
schemaforge diff schema.prisma schema.drizzle.ts

# Batch convert all schemas in directory
schemaforge convert --from sql --to prisma --dir ./schemas/
```

## Commands

### `schemaforge convert`

Convert a schema from one format to another.

```bash
schemaforge convert --from prisma --to drizzle --input schema.prisma
schemaforge convert --from sql --to prisma --input schema.sql --output schema.prisma
schemaforge convert --from typeorm --to django --input entities/
schemaforge convert --from django --to drizzle --input models.py --output schema.drizzle.ts
schemaforge convert --from sqlalchemy --to prisma --input models.py
schemaforge convert --from sql --to sqlalchemy --input schema.sql
```

All direction pairs are fully supported — every format can convert to every other format.

### `schemaforge diff`

Show differences between two schema files in the same format.

```bash
schemaforge diff schema-v1.prisma schema-v2.prisma
schemaforge diff schema.sql schema-updated.sql --format sql
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

## Demo Fixtures

Try SchemaForge immediately with our example blog schema. The `fixtures/` directory contains an equivalent schema (users, posts, categories with foreign keys, enums, and various data types) in all 5 supported formats:

```bash
# Convert SQL → Prisma
schemaforge convert --from sql --to prisma --input fixtures/sample.sql

# Convert Prisma → Django
schemaforge convert --from prisma --to django --input fixtures/sample.prisma

# Convert TypeORM → Drizzle
schemaforge convert --from typeorm --to drizzle --input fixtures/sample.typeorm.ts

# Batch convert all fixtures from SQL
schemaforge convert --from sql --to prisma --dir fixtures/

# Diff two format outputs
schemaforge diff fixtures/sample.sql fixtures/sample.prisma --format prisma
```

Each fixture demonstrates the same blog schema so you can compare ORM syntax side-by-side and verify roundtrip consistency.

## Features

- **Bidirectional conversion** — every supported format can convert to and from every other format
- **Zero-loss roundtripping** — `sql → prisma → sql` produces the same schema you started with
- **Diff mode** — compare two schemas in the same format and see line-level differences
- **Batch mode** — convert entire directories of schema files
- **Type mapping** — intelligent type system mapping between ORMs (e.g., Prisma `String` ↔ Django `CharField` ↔ SQL `VARCHAR`)
- **Relation preservation** — foreign keys, indexes, and unique constraints maintained across conversions

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
| All 5 format directions | — | ✓ | ✓ | ✓ | ✓ |
| Batch directory conversion | — | ✓ | ✓ | ✓ | ✓ |
| Zero-loss roundtrip verification | — | ✓ | ✓ | ✓ | ✓ |
| Custom type mappings | — | ✓ | ✓ | ✓ | ✓ |
| Team shared type mappings | — | — | — | ✓ | ✓ |
| Dashboard & analytics | — | — | — | ✓ | ✓ |
| Compliance reports | — | — | — | — | ✓ |
| RBAC / SSO / SAML / OIDC | — | — | — | — | ✓ |
| Priority support | Community | 24h | 24h | 8h | Dedicated |

---

<p align="center">
  <sub>Part of <a href="https://coding-dev-tools.github.io/revenueholdings.dev/">Revenue Holdings</a> — CLI tools built by autonomous AI.</sub>
</p>

## Roadmap

| Version | Features |
|---------|----------|
| v0.1.0 | SQL DDL ↔ Prisma bidirectional conversion |
| v0.2.0 | Drizzle support |
| v0.3.0 | TypeORM support |
| v0.4.0 | Django models support |
| v0.5.0 | SQLAlchemy support, diff mode, batch mode, custom type mappings |

### Planned

- [ ] Custom type mapping configuration files
- [ ] JSON Schema import/export
- [ ] GraphQL schema export
- [ ] MCP server for AI-assisted schema operations
- [ ] VS Code extension with live diff
- [ ] CI/CD check: enforce schema consistency across branches

## License

MIT — see [LICENSE](LICENSE)

---

<sub>Part of [Revenue Holdings](https://coding-dev-tools.github.io/revenueholdings.dev/) — a suite of 10 developer CLI tools built by autonomous AI agents. Also check out [API Contract Guardian](https://github.com/Coding-Dev-Tools/api-contract-guardian) (breaking change detection), [DeployDiff](https://github.com/Coding-Dev-Tools/deploydiff) (infrastructure diffs), [json2sql](https://github.com/Coding-Dev-Tools/json2sql) (JSON → SQL), [ConfigDrift](https://github.com/Coding-Dev-Tools/configdrift) (config drift detection), [DeadCode](https://github.com/Coding-Dev-Tools/deadcode) (dead code cleanup), [APIAuth](https://github.com/Coding-Dev-Tools/apiauth) (API key management), [APIGhost](https://github.com/Coding-Dev-Tools/apighost) (mock API server), [Envault](https://github.com/Coding-Dev-Tools/envault) (env sync), and [click-to-mcp](https://github.com/Coding-Dev-Tools/click-to-mcp) (CLI → MCP server).</sub>
