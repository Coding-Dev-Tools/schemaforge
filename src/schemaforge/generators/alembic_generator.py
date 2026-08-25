"""Generator: SchemaForge IR → Alembic migration script.

Generates op.create_table() / op.create_index() migration code
for initial schema setup, deployable as Alembic revision scripts.
"""

from __future__ import annotations

from ..ir import Column, ColumnType, Schema, Table
from ..type_config import TypeConfig
from ._base import build_type_string, format_literal_default, resolve_fn_default


class AlembicGenerator:
    """Convert Schema IR to an Alembic migration script."""

    def __init__(self, type_config: TypeConfig | None = None) -> None:
        """Initialize with optional custom type overrides."""
        self._type_config = type_config

    _TYPE_MAP: dict[ColumnType, str] = {
        ColumnType.STRING: "sa.String",
        ColumnType.INTEGER: "sa.Integer",
        ColumnType.FLOAT: "sa.Float",
        ColumnType.BOOLEAN: "sa.Boolean",
        ColumnType.DATETIME: "sa.DateTime",
        ColumnType.DATE: "sa.Date",
        ColumnType.TIME: "sa.Time",
        ColumnType.TEXT: "sa.Text",
        ColumnType.BLOB: "sa.LargeBinary",
        ColumnType.JSON: "sa.JSON",
        ColumnType.UUID: "sa.Uuid",
        ColumnType.ENUM: "sa.Enum",
        ColumnType.DECIMAL: "sa.Numeric",
    }

    def generate(
        self,
        schema: Schema,
        *,
        revision_id: str = "initial",
        down_revision: str | None = None,
        message: str = "Initial schema",
    ) -> str:
        """Generate an Alembic migration script from the schema IR.

        Args:
            schema: The schema to generate a migration for.
            revision_id: Alembic revision identifier (default: "initial").
            down_revision: Parent revision (default: None for initial).
            message: Migration message / docstring.

        Returns:
            A complete Alembic migration script as a string.
        """
        from datetime import datetime, timezone

        create_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        lines: list[str] = []
        lines.append(f'"""{message}')
        lines.append("")
        lines.append(f"Revision ID: {revision_id}")
        lines.append(f"Revises: {down_revision or ''}")
        lines.append(f"Create Date: {create_date}")
        lines.append('"""')
        lines.append("from alembic import op")
        lines.append("import sqlalchemy as sa")
        lines.append("")

        # Enum type definitions (as raw SQL for database ENUMs)
        if schema.enums:
            lines.append("# ### enum type definitions ###")
            for enum_type in schema.enums:
                values = ", ".join(f"'{v}'" for v in enum_type.values)
                lines.append(
                    f'op.execute("CREATE TYPE {enum_type.name} AS ENUM ({values})")'
                )
            lines.append("")

        lines.append("# revision identifiers, used by Alembic.")
        lines.append(f"revision = '{revision_id}'")
        lines.append(f"down_revision = {repr(down_revision)}")
        lines.append("")

        # ── upgrade() ──
        lines.append("")
        lines.append("def upgrade() -> None:")
        if not schema.tables:
            lines.append("    pass")
        else:
            for table in schema.tables:
                col_lines, index_lines = self._generate_table(table)
                for cl in col_lines:
                    lines.append(f"    {cl}")
                for il in index_lines:
                    lines.append(f"    {il}")

        # ── downgrade() ──
        lines.append("")
        lines.append("")
        lines.append("def downgrade() -> None:")
        if not schema.tables and not schema.enums:
            lines.append("    pass")
        else:
            # Drop indexes first, then tables, then enums
            for table in reversed(schema.tables):
                for idx in reversed(table.indexes):
                    idx_name = idx.name or f"idx_{'_'.join(idx.columns)}"
                    lines.append(
                        f"    op.drop_index('{idx_name}', table_name='{table.name}')"
                    )
            for table in reversed(schema.tables):
                lines.append(f"    op.drop_table('{table.name}')")
            for enum_type in reversed(schema.enums):
                lines.append(f"    op.execute('DROP TYPE {enum_type.name}')")

        return "\n".join(lines) + "\n"

    def _generate_table(self, table: Table) -> tuple[list[str], list[str]]:
        """Generate op.create_table() and op.create_index() calls for a table.

        Returns (create_table_lines, create_index_lines).
        """
        col_defs: list[str] = []
        for col in table.columns:
            col_defs.append(f"        {self._column_def(col)},")

        table_lines: list[str] = []
        if col_defs:
            table_lines.append(f"    op.create_table('{table.name}',")
            table_lines.extend(col_defs)
            table_lines.append("    )")
        else:
            table_lines.append(f"    op.create_table('{table.name}')")

        index_lines: list[str] = []
        for idx in table.indexes:
            col_list = ", ".join(f"'{c}'" for c in idx.columns)
            idx_name = idx.name or f"idx_{'_'.join(idx.columns)}"
            if idx.unique:
                index_lines.append(
                    f"    op.create_unique_constraint('{idx_name}', "
                    f"'{table.name}', [{col_list}])"
                )
            else:
                index_lines.append(
                    f"    op.create_index('{idx_name}', '{table.name}', [{col_list}])"
                )

        return table_lines, index_lines

    def _column_def(self, col: Column) -> str:
        """Generate a sa.Column() definition string."""
        sa_type = build_type_string(
            col,
            self._TYPE_MAP,
            string_fmt="{}({})",
            string_default="sa.String",
            decimal_fmt="{}({}, {})",
            decimal_default="sa.Numeric",
            decimal_precision=10,
            decimal_scale=2,
            enum_fmt="{}({})",
            fmt="alembic",
            type_config=self._type_config,
        )

        kwargs: list[str] = [sa_type]

        if col.primary_key:
            kwargs.append("primary_key=True")
        if not col.nullable:
            kwargs.append("nullable=False")
        if col.unique and not col.primary_key:
            kwargs.append("unique=True")

        # fn: defaults (server_default)
        fn_default = resolve_fn_default(
            col, fn_wrapper="sa.func.{}", expr_fallback="sa.text('{}')"
        )
        if fn_default:
            kwargs.append(f"server_default={fn_default}")

        # Literal defaults
        if col.default is not None and not (
            isinstance(col.default, str) and col.default.startswith("fn:")
        ):
            lit = format_literal_default(col)
            kwargs.append(f"server_default={lit}")

        return f"sa.Column('{col.name}', {', '.join(kwargs)})"
