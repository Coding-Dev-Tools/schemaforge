# SchemaForge

**Bidirectional ORM schema converter** — convert between SQL DDL, Prisma, Drizzle, TypeORM, and Django models with zero-loss roundtripping.

## Why SchemaForge?

Every major ORM migration is a one-way street. Prisma can introspect SQL but can't export back. Drizzle users manually rewrite schemas when switching ORMs. No tool does bidirectional, lossless conversion between 5+ ORM formats.

SchemaForge fills this gap — the #1 market opportunity according to our research.

## Quick Start

```bash
pip install schemaforge

# Convert Prisma → Drizzle
schemaforge convert --from prisma --to drizzle --input schema.prisma

# Diff two schemas
schemaforge diff schema.prisma schema.drizzle.ts

# Batch convert all schemas in directory
schemaforge convert --from sql --to prisma --dir ./schemas/
```

## Supported Formats

| Format | Import | Export |
|--------|--------|--------|
| SQL DDL | ✅ | ✅ |
| Prisma schema | ✅ | ✅ |
| Drizzle schema | ✅ | ✅ |
| TypeORM entities | ✅ | ✅ |
| Django models | ✅ | ✅ |

## Roadmap

- v0.1.0: SQL DDL ↔ Prisma bidirectional conversion
- v0.2.0: Drizzle support added
- v0.3.0: TypeORM support
- v0.4.0: Django models support
- v0.5.0: Diff mode, batch mode, custom type mappings

## License

MIT — Revenue Holdings
