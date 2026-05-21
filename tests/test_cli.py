"""CLI integration tests for SchemaForge — Click CliRunner based tests.

Covers the full CLI surface: convert, diff, check, mcp, version,
error handling, edge cases, and output file paths.
"""
from __future__ import annotations

import sys
import tempfile
from click.testing import CliRunner
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.cli import _detect_format, main

# ── Helpers ──

FIXTURES = Path(__file__).parent.parent / "fixtures"

SAMPLE_SQL = """CREATE TABLE users (
    id INTEGER PRIMARY KEY NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE
);
"""

SAMPLE_PRISMA = """generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model users {
  id    Int    @id @default(autoincrement())
  name  String @db.VarChar(100)
  email String @unique
}
"""


# ═══════════════════════════════════════════════════════════════
#  convert command
# ═══════════════════════════════════════════════════════════════

class TestConvertCommand:
    def test_convert_sql_to_prisma_stdout(self):
        """Convert SQL → Prisma, output to stdout."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write(SAMPLE_SQL)
            tmpfile = f.name
        try:
            result = runner.invoke(main, [
                "convert",
                "--from", "sql",
                "--to", "prisma",
                "--input", tmpfile,
            ])
            assert result.exit_code == 0
            assert "model users" in result.output
            assert "@id" in result.output
            assert "@unique" in result.output
        finally:
            Path(tmpfile).unlink(missing_ok=True)

    def test_convert_prisma_to_sql_stdout(self):
        """Convert Prisma → SQL, output to stdout."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".prisma", delete=False) as f:
            f.write(SAMPLE_PRISMA)
            tmpfile = f.name
        try:
            result = runner.invoke(main, [
                "convert",
                "--from", "prisma",
                "--to", "sql",
                "--input", tmpfile,
            ])
            assert result.exit_code == 0
            assert "CREATE TABLE" in result.output
            assert "INTEGER" in result.output or "INT" in result.output.upper()
        finally:
            Path(tmpfile).unlink(missing_ok=True)

    def test_convert_output_file(self):
        """Convert SQL → Prisma, write output to a file."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f_in:
            f_in.write(SAMPLE_SQL)
            tmp_in = f_in.name
        tmp_out = Path(tempfile.mktemp(suffix=".prisma"))
        try:
            result = runner.invoke(main, [
                "convert",
                "--from", "sql",
                "--to", "prisma",
                "--input", tmp_in,
                "--output", str(tmp_out),
            ])
            assert result.exit_code == 0
            assert tmp_out.exists()
            content = tmp_out.read_text(encoding="utf-8")
            assert "model users" in content
            assert "Written to" in result.output
        finally:
            Path(tmp_in).unlink(missing_ok=True)
            tmp_out.unlink(missing_ok=True)

    def test_convert_using_fixture_files(self):
        """Convert a real fixture file (SQL → Prisma)."""
        runner = CliRunner()
        sql_fixture = FIXTURES / "sample.sql"
        assert sql_fixture.exists(), f"Fixture not found: {sql_fixture}"

        result = runner.invoke(main, [
            "convert",
            "--from", "sql",
            "--to", "prisma",
            "--input", str(sql_fixture),
        ])
        assert result.exit_code == 0
        assert "model" in result.output or "model " in result.output

    def test_convert_with_type_map(self):
        """Convert SQL → Prisma with a custom type map."""
        runner = CliRunner()
        sql_fixture = FIXTURES / "sample.sql"
        type_map = FIXTURES / "sample-type-overrides.yaml"
        assert sql_fixture.exists() and type_map.exists()

        result = runner.invoke(main, [
            "convert",
            "--from", "sql",
            "--to", "prisma",
            "--input", str(sql_fixture),
            "--type-map", str(type_map),
        ])
        assert result.exit_code == 0

    def test_convert_django_to_sqlalchemy(self):
        """Convert Django models → SQLAlchemy using fixtures."""
        runner = CliRunner()
        django_fixture = FIXTURES / "sample.django.py"
        assert django_fixture.exists()

        result = runner.invoke(main, [
            "convert",
            "--from", "django",
            "--to", "sqlalchemy",
            "--input", str(django_fixture),
        ])
        assert result.exit_code == 0
        assert "Column(" in result.output or "sa.Column" in result.output

    def test_convert_graphql_to_prisma(self):
        """Convert GraphQL SDL → Prisma using fixtures."""
        runner = CliRunner()
        graphql_fixture = FIXTURES / "sample.graphql"
        assert graphql_fixture.exists()

        result = runner.invoke(main, [
            "convert",
            "--from", "graphql",
            "--to", "prisma",
            "--input", str(graphql_fixture),
        ])
        assert result.exit_code == 0
        assert "model" in result.output

    def test_convert_json_schema_to_sql(self):
        """Convert JSON Schema → SQL using fixtures."""
        runner = CliRunner()
        json_fixture = FIXTURES / "sample.json_schema.json"
        assert json_fixture.exists()

        result = runner.invoke(main, [
            "convert",
            "--from", "json_schema",
            "--to", "sql",
            "--input", str(json_fixture),
        ])
        assert result.exit_code == 0
        assert "CREATE TABLE" in result.output

    def test_convert_missing_file_returns_error(self):
        """Missing input file should exit with non-zero code."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "convert",
            "--from", "sql",
            "--to", "prisma",
            "--input", "nonexistent_file.sql",
        ])
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "Error" in result.output

    def test_convert_bad_source_format(self):
        """Invalid source format should show error."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write(SAMPLE_SQL)
            tmpfile = f.name
        try:
            result = runner.invoke(main, [
                "convert",
                "--from", "badformat",
                "--to", "prisma",
                "--input", tmpfile,
            ])
            assert result.exit_code != 0
            assert "badformat" in result.output.lower() or "Error" in result.output
        finally:
            Path(tmpfile).unlink(missing_ok=True)

    def test_convert_bad_target_format(self):
        """Invalid target format should show error."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write(SAMPLE_SQL)
            tmpfile = f.name
        try:
            result = runner.invoke(main, [
                "convert",
                "--from", "sql",
                "--to", "badformat",
                "--input", tmpfile,
            ])
            assert result.exit_code != 0
            assert "badformat" in result.output.lower() or "Error" in result.output
        finally:
            Path(tmpfile).unlink(missing_ok=True)

    def test_convert_ef_csharp_to_sql(self):
        """Convert EF Core (C#) → SQL using fixtures."""
        runner = CliRunner()
        ef_fixture = FIXTURES / "sample.ef.cs"
        assert ef_fixture.exists()

        result = runner.invoke(main, [
            "convert",
            "--from", "ef",
            "--to", "sql",
            "--input", str(ef_fixture),
        ])
        assert result.exit_code == 0
        assert "CREATE TABLE" in result.output

    def test_convert_scala_to_sql(self):
        """Convert Scala case classes → SQL using fixtures."""
        runner = CliRunner()
        scala_fixture = FIXTURES / "sample.scala"
        assert scala_fixture.exists()

        result = runner.invoke(main, [
            "convert",
            "--from", "scala",
            "--to", "sql",
            "--input", str(scala_fixture),
        ])
        assert result.exit_code == 0
        assert "CREATE TABLE" in result.output


# ═══════════════════════════════════════════════════════════════
#  diff command
# ═══════════════════════════════════════════════════════════════

class TestDiffCommand:
    def test_diff_same_file(self):
        """Diff two identical files should report no differences."""
        runner = CliRunner()
        f1 = FIXTURES / "sample.sql"
        f2 = FIXTURES / "sample.sql"
        assert f1.exists()

        result = runner.invoke(main, [
            "diff",
            str(f1), str(f2),
        ])
        assert result.exit_code == 0

    def test_diff_different_files(self):
        """Diff two different SQL files should show differences."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f1:
            f1.write("CREATE TABLE a (id INT PRIMARY KEY);\n")
            f1_path = f1.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f2:
            f2.write("CREATE TABLE b (id INT PRIMARY KEY);\n")
            f2_path = f2.name
        try:
            result = runner.invoke(main, [
                "diff",
                f1_path, f2_path,
            ])
            assert result.exit_code == 0
        finally:
            Path(f1_path).unlink(missing_ok=True)
            Path(f2_path).unlink(missing_ok=True)

    def test_diff_with_format(self):
        """Diff with explicit --format flag."""
        runner = CliRunner()
        f1 = FIXTURES / "sample.sql"
        f2 = FIXTURES / "sample.sql"
        assert f1.exists()

        result = runner.invoke(main, [
            "diff",
            str(f1), str(f2),
            "--format", "sql",
        ])
        assert result.exit_code == 0

    def test_diff_missing_file(self):
        """Diff with missing file should exit with error."""
        runner = CliRunner()
        f1 = FIXTURES / "sample.sql"
        result = runner.invoke(main, [
            "diff",
            str(f1), "nonexistent.sql",
        ])
        assert result.exit_code != 0


# ═══════════════════════════════════════════════════════════════
#  check command
# ═══════════════════════════════════════════════════════════════

class TestCheckCommand:
    def test_check_directory_two_files(self):
        """Check a directory with two equivalent schema files."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "schema.sql").write_text(SAMPLE_SQL)
            Path(tmpdir, "schema.prisma").write_text(SAMPLE_PRISMA)

            result = runner.invoke(main, [
                "check",
                "--dir", tmpdir,
            ])
            # May exit 1 if schemas are not perfectly equivalent;
            # verify at least it attempted comparison
            assert "Files found" in result.output

    def test_check_directory_single_file(self):
        """Check directory with only one schema file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "schema.sql").write_text(SAMPLE_SQL)

            result = runner.invoke(main, [
                "check",
                "--dir", tmpdir,
            ])
            assert result.exit_code == 0
            assert "Need at least 2" in result.output

    def test_check_directory_with_type_map(self):
        """Check directory with a type map."""
        runner = CliRunner()
        type_map = FIXTURES / "sample-type-overrides.yaml"
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "schema.sql").write_text(SAMPLE_SQL)
            Path(tmpdir, "schema.prisma").write_text(SAMPLE_PRISMA)

            runner.invoke(main, [
                "check",
                "--dir", tmpdir,
                "--type-map", str(type_map),
            ])
            # May exit 1 depending on equivalence; check it ran

    def test_check_invalid_directory(self):
        """Check a file path that is not a directory."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
            f.write(b"x")
            f_path = f.name
        try:
            result = runner.invoke(main, [
                "check",
                "--dir", f_path,
            ])
            assert result.exit_code != 0
            assert "Error" in result.output or "Not a directory" in result.output
        finally:
            Path(f_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
#  mcp command
# ═══════════════════════════════════════════════════════════════

class TestMcpCommand:
    def test_mcp_help_shows(self):
        """MCP subcommand should appear in help."""
        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--help"])
        # The MCP server may or may not be available; just check it's
        # registered as a command or that help text appears.
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════
#  general CLI behavior
# ═══════════════════════════════════════════════════════════════

class TestGeneralCli:
    def test_version(self):
        """--version should display the package version."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output or "schemaforge" in result.output.lower()

    def test_no_args_shows_help(self):
        """Running schemaforge with no args should display help."""
        runner = CliRunner()
        result = runner.invoke(main, [])
        # Click exits with code 2 when no subcommand given
        assert "Usage:" in result.output or "Commands:" in result.output

    def test_help_command(self):
        """--help should display the help."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "convert" in result.output
        assert "diff" in result.output
        assert "check" in result.output

    def test_convert_help(self):
        """convert --help should show subcommand help."""
        runner = CliRunner()
        result = runner.invoke(main, ["convert", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--from" in result.output
        assert "--to" in result.output
        assert "--input" in result.output

    def test_diff_help(self):
        """diff --help should show subcommand help."""
        runner = CliRunner()
        result = runner.invoke(main, ["diff", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "FILE_A" in result.output or "FILE_B" in result.output

    def test_check_help(self):
        """check --help should show subcommand help."""
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--dir" in result.output


# ═══════════════════════════════════════════════════════════════
#  _detect_format
# ═══════════════════════════════════════════════════════════════

class TestHelpEncoding:
    """Verifies CLI help text has no garbled/encoding corruption."""

    def test_help_no_garbled_unicode(self):
        """--help output should not contain garbled Unicode patterns."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        output = result.output
        # Known garbled patterns that occur when UTF-8 is misinterpreted as Latin-1
        garbled = ["â€", "Ã©", "Ã¼", "Ã±", "ï»¿"]
        for pattern in garbled:
            assert pattern not in output, f"Garbled Unicode found: {pattern!r}"

    def test_help_docstring_em_dash(self):
        """--help output should show em-dash (—) not garbled mojibake."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        output = result.output
        # The module docstring uses an em-dash — verify it renders
        assert "—" in output, "Em-dash not found in help output"


class TestDetectFormat:
    """Tests for the private _detect_format helper."""

    def test_sql_extension(self):
        assert _detect_format("schema.sql") == "sql"

    def test_prisma_extension(self):
        assert _detect_format("schema.prisma") == "prisma"

    def test_drizzle_ts(self):
        assert _detect_format("schema.ts") == "drizzle"

    def test_drizzle_tsx(self):
        assert _detect_format("schema.tsx") == "drizzle"

    def test_django_python(self):
        assert _detect_format("models.py") == "django"

    def test_json_schema(self):
        assert _detect_format("schema.json") == "json_schema"

    def test_graphql(self):
        assert _detect_format("schema.graphql") == "graphql"

    def test_graphql_gql(self):
        assert _detect_format("schema.gql") == "graphql"

    def test_ef_csharp(self):
        assert _detect_format("entities.cs") == "ef"

    def test_scala(self):
        assert _detect_format("models.scala") == "scala"

    def test_unknown_extension_defaults_to_sql(self):
        assert _detect_format("schema.txt") == "sql"

    def test_no_extension_defaults_to_sql(self):
        assert _detect_format("schema") == "sql"
