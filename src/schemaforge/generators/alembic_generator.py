"""Generator: SchemaForge IR → Alembic migration script.

Generates op.create_table() / op.create_index() migration code
for initial schema setup, deployable as Alembic revision scripts.
"""
from __future__ import annotations

from ..ir import Schema, Column, ColumnType, Table, Index
from ..ir import EnumType  # noqa: F401 — used in signature type hints


class AlembicGenerator:
    """Convert Schema IR to an Alembic migration script."""

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
                    f"op.execute(\"CREATE TYPE {enum_type.name} AS ENUM ({values})\")"
                )
            lines.append("")

        lines.append("# revision identifiers, used by Alembic.")
        lines.append(f"revision = '{revision_id}'")
        lines.append(
            f"down_revision = {repr(down_revision)}"
        )
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
                lines.append(
                    f"    op.execute('DROP TYPE {enum_type.name}')"
                )

        return "\n".join(lines) + "\n"

    def _generate_table(
        self, table: Table
    ) -> tuple[list[str], list[str]]:
        """Generate op.create_table() and op.create_index() calls for a table.

        Returns (create_table_lines, create_index_lines).
        """
        col_defs: list[str] = []
        for col in table.columns:
            col_defs.append(f"        {self._column_def(col)},")

        table_lines: list[str] = []
        if col_defs:
            table_lines.append(
                f"    op.create_table('{table.name}',"
            )
            table_lines.extend(col_defs)
            table_lines.append("    )")
        else:
            table_lines.append(
                f"    op.create_table('{table.name}')"
            )

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
                    f"    op.create_index('{idx_name}', "
                    f"'{table.name}', [{col_list}])"
                )

        return table_lines, index_lines

    def _column_def(self, col: Column) -> str:
        """Generate a sa.Column() definition string."""
        if col.type == ColumnType.CUSTOM and col.custom_type:
            sa_type = col.custom_type
        elif col.type == ColumnType.ENUM and col.type_args.get("values"):
            values = ", ".join(f"'{v}'" for v in col.type_args["values"])
            sa_type = f"sa.Enum({values})"
        else:
            sa_type = self._TYPE_MAP.get(col.type, "sa.String")
            if col.type == ColumnType.STRING:
                length = col.type_args.get("length", 255)
                sa_type = f"sa.String({length})"
            elif col.type == ColumnType.DECIMAL:
                precision = col.type_args.get("precision", 10)
                scale = col.type_args.get("scale", 2)
                sa_type = f"sa.Numeric({precision}, {scale})"

        kwargs: list[str] = [sa_type]

        if col.primary_key:
            kwargs.append("primary_key=True")
        if not col.nullable:
            kwargs.append("nullable=False")
        if col.unique and not col.primary_key:
            kwargs.append("unique=True")

        # Server default handling
        if col.default is not None:
            if isinstance(col.default, str) and col.default.startswith("fn:"):
                fn_raw = col.default[3:]
                fn_upper = fn_raw.upper().rstrip("()")
                if fn_upper in ("NOW", "CURRENT_TIMESTAMP"):
                    kwargs.append("server_default=sa.func.now()")
                elif fn_upper == "CURRENT_DATE":
                    kwargs.append("server_default=sa.func.current_date()")
                elif fn_upper == "CURRENT_TIME":
                    kwargs.append("server_default=sa.func.current_time()")
                elif fn_upper == "GEN_RANDOM_UUID":
                    kwargs.append("server_default=sa.func.gen_random_uuid()")
                elif fn_raw.endswith("()"):
                    kwargs.append(f"server_default=sa.func.{fn_raw}")
                else:
                    kwargs.append(f"server_default=sa.text('{fn_raw}')")
            elif isinstance(col.default, bool):
                kwargs.append(f"server_default={str(col.default).lower()}")
            elif isinstance(col.default, str):
                kwargs.append(f"server_default='{col.default}'")
            elif isinstance(col.default, (int, float)):
                kwargs.append(f"server_default={col.default}")

        return f"sa.Column('{col.name}', {', '.join(kwargs)})"
