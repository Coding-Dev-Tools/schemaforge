# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.0] - 2026-05-15

### Added
- VS Code extension with live preview, diff, and quick convert
- Right-click conversion from file explorer
- Custom editor for `.schemaforge` files
- Auto-refresh preview on file save

## [1.6.0] - 2026-05-15

### Added
- Scala case class support (Doobie/Quill/Slick) as 11th format

## [1.5.0] - 2026-05-15

### Added
- Entity Framework Core (C#) support as 10th format
- Data annotations generation for EF Core entities

## [1.4.0] - 2026-05-15

### Added
- MCP (Model Context Protocol) server for AI agent integration
- `schemaforge mcp` command (stdio and SSE modes)
- `schemaforge check` command — schema consistency across directories
- `schemaforge formats` command — list supported formats
- `schemaforge detect_format` command — identify format from filename
- CI/CD workflow for automated testing and publishing

### Changed
- Consolidated test workflow configuration

## [1.3.0] - 2026-05-15

### Added
- GraphQL SDL format support as 9th schema format
- Bidirectional conversion between GraphQL and all other formats
- Enum, directive, and custom scalar support in GraphQL

## [1.2.0] - 2026-05-15

### Added
- JSON Schema support (draft 2020-12) as 8th format
- JSON Schema import/export with type mapping
- URI-friendly enum value generation

## [1.1.0] - 2026-05-15

### Added
- Custom type mapping configuration via YAML/JSON override files
- Template variables in type overrides: `{length}`, `{precision}`, `{scale}`, `{values}`
- `--type-map` CLI option for all convert commands

## [1.0.0] - 2026-05-15

### Added
- Stable release with comprehensive docs and CLI polish
- Licensing gating via `revenueholdings-license`
- Star badge and call-to-action in README

### Fixed
- Version bump from 1.0.0 to 1.7.0 alignment (internal consistency)

## [0.9.0] - 2026-05-15

### Changed
- Shared generator base module (`_base.py`) for reduced code duplication
- Refactored `fn:` default handling for cross-format function defaults

## [0.8.0] - 2026-05-15

### Added
- Alembic migration generation as 7th format (generator-only)
- `--output` support for migration script generation
- Alembic `op.create_table`, `op.add_column`, `op.create_index` output

## [0.7.0] - 2026-05-15

### Added
- MySQL table options: `ENGINE=InnoDB`, `AUTO_INCREMENT`, `DEFAULT CHARSET`, `COMMENT`
- Inline ENUM column type: `ENUM('small', 'medium', 'large')` parsing and roundtripping

## [0.6.0] - 2026-05-15

### Added
- SQL parser edge cases: `TEMPORARY TABLE`, backtick quoting, quoted identifiers
- `fn:` default prefix preservation across roundtrips

### Fixed
- Roundtrip fidelity for function-based default values

## [0.5.0] - 2026-05-15

### Added
- SQLAlchemy declarative model support as 5th format
- `schemaforge diff` command for line-level schema comparison
- Batch directory mode (`schemaforge check --dir`)
- Demo fixtures with blog schema in all formats
- 17 new roundtrip and edge-case tests

### Fixed
- PRAGMA KEY implies NOT NULL in SQL parser
- Generator index handling for SQLAlchemy

## [0.4.0] - 2026-05-15

### Added
- Django models support as 4th format
- TypeORM entities support as 3rd format
- Parser/generator registration system in convert registry

### Fixed
- `convert_schema` and `register_format` functions restored after merge conflict

## [0.3.0] - 2026-05-15

### Added
- TypeORM entities support as 3rd format
- Decorator-based entity parsing and generation

## [0.2.0] - 2026-05-15

### Added
- Drizzle ORM schema support as 2nd format
- Drizzle parser/generator registered in convert registry

## [0.1.0] - 2026-05-14

### Added
- Initial beta release
- Core bidirectional conversion engine
- SQL DDL ↔ Prisma schema conversion
- Internal Representation (IR) architecture
- CLI interface with `convert` command
- Test suite with 270+ passing tests
- CI workflow with ruff lint and pytest
- CONTRIBUTING.md for contributor guidance
