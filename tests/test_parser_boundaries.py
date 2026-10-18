"""Regression coverage for incomplete parser input at delimiter boundaries."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schemaforge.ir import ColumnType
from schemaforge.parsers.sql_parser import SQLParser
from schemaforge.parsers.typeorm_parser import TypeORMParser


@pytest.mark.parametrize(
    "incomplete",
    ["CREATE TABLE broken (id INTEGER", "CREATE TABLE broken (price DECIMAL(10, 2)"],
)
def test_sql_rejects_unclosed_table_body(incomplete):
    with pytest.raises(ValueError, match="Unclosed column definitions for table 'broken'"):
        SQLParser().parse(incomplete)


def test_sql_still_skips_statement_without_column_list():
    schema = SQLParser().parse("CREATE TABLE broken; CREATE TABLE kept (id INTEGER NOT NULL);")

    assert len(schema.tables) == 1
    table = schema.tables[0]
    assert table.name == "kept"
    assert len(table.columns) == 1
    assert table.columns[0].name == "id"
    assert table.columns[0].type == ColumnType.INTEGER
    assert table.columns[0].nullable is False


@pytest.mark.parametrize(
    ("decorator", "primary_key"),
    [("@Column", False), ("@PrimaryColumn", True), ("@PrimaryGeneratedColumn", True)],
)
def test_typeorm_bare_column_decorator_uses_field_type(decorator, primary_key):
    source = f"""
@Entity()
export class Entry {{
    {decorator}
    id: number;
}}
"""
    schema = TypeORMParser().parse(source)

    assert len(schema.tables) == 1
    table = schema.tables[0]
    assert table.name == "Entry"
    assert len(table.columns) == 1
    assert table.columns[0].name == "id"
    assert table.columns[0].type == ColumnType.INTEGER
    assert table.columns[0].primary_key is primary_key
