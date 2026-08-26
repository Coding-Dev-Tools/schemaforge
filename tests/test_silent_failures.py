"""Silent-failure regression tests: unsupported constructs must warn, not vanish."""

from __future__ import annotations

import pytest
import warnings
from schemaforge.generators.json_schema_generator import JSONSchemaGenerator
from schemaforge.parsers.sql_parser import SQLParser
from schemaforge.type_config import TypeConfig


def test_sql_parser_warns_on_foreign_key_constraint() -> None:
    sql = """
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        SQLParser().parse(sql)
    assert any("FOREIGN KEY" in str(w.message) for w in caught)


def test_sql_parser_warns_on_named_check_constraint() -> None:
    sql = """
    CREATE TABLE products (
        price NUMERIC,
        CONSTRAINT positive_price CHECK (price >= 0)
    );
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        SQLParser().parse(sql)
    assert any("CHECK" in str(w.message) for w in caught)


def test_sql_parser_no_warning_for_plain_table() -> None:
    sql = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email VARCHAR(255) NOT NULL
    );
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        SQLParser().parse(sql)
    assert not caught


def test_json_schema_generator_warns_on_malformed_override() -> None:
    from schemaforge.ir import Column, ColumnType

    class MalformedOverrideCfg(TypeConfig):
        """Returns an override that looks like JSON but fails to parse."""

        def get_override(self, col, fmt, type_args=None):  # noqa: D102
            return "{broken json}"

    col = Column(name="email", type=ColumnType.STRING, nullable=True)
    gen = JSONSchemaGenerator(type_config=MalformedOverrideCfg())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        gen._column_to_prop(col)
    assert any("failed to parse" in str(w.message) for w in caught)


def _make_column(name: str):
    from schemaforge.ir import Column, ColumnType

    return Column(name=name, type=ColumnType.STRING, nullable=True)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE t (a INT, CONSTRAINT fk_a FOREIGN KEY (a) REFERENCES o(a));",
        "CREATE TABLE t (a INT, FOREIGN KEY (a) REFERENCES o(a));",
    ],
)
def test_warning_includes_table_name(sql: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        SQLParser().parse(sql)
    assert any("'t'" in str(w.message) for w in caught)
