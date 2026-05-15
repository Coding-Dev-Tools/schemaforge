"""Generator: SchemaForge IR → SQLAlchemy declarative model schema."""
from __future__ import annotations

from ..ir import Schema, Column, ColumnType


class SQLAlchemyGenerator:
    """Convert Schema IR to SQLAlchemy declarative model Python format."""

    _TYPE_MAP: dict[ColumnType, str] = {
        ColumnType.STRING: "String",
        ColumnType.INTEGER: "Integer",
        ColumnType.FLOAT: "Float",
        ColumnType.BOOLEAN: "Boolean",
        ColumnType.DATETIME: "DateTime",
        ColumnType.DATE: "Date",
        ColumnType.TIME: "Time",
        ColumnType.TEXT: "Text",
        ColumnType.BLOB: "LargeBinary",
        ColumnType.JSON: "JSON",
        ColumnType.UUID: "Uuid",
        ColumnType.ENUM: "Enum",
        ColumnType.DECIMAL: "Numeric",
    }

    def generate(self, schema: Schema) -> str:
        """Generate SQLAlchemy models from schema IR."""
        parts: list[str] = [
            "from sqlalchemy import Column, Integer, String, Boolean, DateTime,"
            " Text, Float, Numeric, JSON, LargeBinary, Date, Time, Enum, Uuid,"
            " ForeignKey, Index, UniqueConstraint, func, text",
            "from sqlalchemy.orm import declarative_base",
            "",
            "Base = declarative_base()",
        ]

        for table in schema.tables:
            parts.append("")
            parts.append(self._generate_model(table))

        return "\n".join(parts) + "\n"

    def _generate_model(self, table) -> str:
        """Generate a single SQLAlchemy model class."""
        lines: list[str] = []

        # Class name (PascalCase from table name)
        class_name = self._to_pascal(table.name)
        lines.append(f"class {class_name}(Base):")
        lines.append(f'    __tablename__ = "{table.name}"')
        lines.append("")

        # Collect needed imports for this model
        needed_types: set[str] = set()

        # Columns
        for col in table.columns:
            col_lines, types_used = self._column_def(col)
            lines.extend(col_lines)
            needed_types.update(types_used)

        # Indexes — collect all into a single __table_args__ tuple
        table_args_entries: list[str] = []
        for idx in table.indexes:
            col_list = ", ".join(f"'{c}'" for c in idx.columns)
            if idx.unique:
                table_args_entries.append(f"UniqueConstraint({col_list})")
            else:
                table_args_entries.append(f"Index({col_list})")

        if table_args_entries:
            lines.append("    __table_args__ = (")
            for entry in table_args_entries:
                lines.append(f"        {entry},")
            lines.append("    )")

        if not table.columns:
            lines.append("    pass")

        return "\n".join(lines)

    def _column_def(self, col: Column) -> tuple[list[str], set[str]]:
        """Generate a Column definition line.

        Returns (lines, type_names_used).
        """
        lines: list[str] = []
        types_used: set[str] = set()

        # Determine SQLAlchemy type
        if col.type == ColumnType.CUSTOM and col.custom_type:
            sa_type = col.custom_type
            types_used.add(sa_type)
        else:
            sa_type = self._TYPE_MAP.get(col.type, "String")
            types_used.add(sa_type)

        # Build type string with args
        type_str = sa_type
        if col.type == ColumnType.STRING:
            length = col.type_args.get("length", 255)
            type_str = f"String({length})"
        elif col.type == ColumnType.DECIMAL:
            precision = col.type_args.get("precision", 10)
            scale = col.type_args.get("scale", 2)
            type_str = f"Numeric({precision}, {scale})"

        kwargs: list[str] = []

        # Primary key
        if col.primary_key:
            kwargs.append("primary_key=True")
            # autoincrement=False for non-integer PKs or explicit setting
            if col.type != ColumnType.INTEGER:
                kwargs.append("autoincrement=False")
            elif col.type_args.get("autoincrement") is False:
                kwargs.append("autoincrement=False")

        # Nullable — SQLAlchemy defaults to True, so only emit when False
        if not col.nullable:
            kwargs.append("nullable=False")

        # Unique
        if col.unique and not col.primary_key:
            kwargs.append("unique=True")

        # Index
        if col.type_args.get("index"):
            kwargs.append("index=True")

        # Server default (func expressions)
        if col.default is not None:
            if isinstance(col.default, str) and col.default.startswith("fn:"):
                fn_raw = col.default[3:]
                fn_upper = fn_raw.upper().rstrip("()")
                if fn_upper in ("NOW", "CURRENT_TIMESTAMP"):
                    kwargs.append('server_default=func.now()')
                elif fn_upper == "CURRENT_DATE":
                    kwargs.append('server_default=func.current_date()')
                elif fn_upper == "CURRENT_TIME":
                    kwargs.append('server_default=func.current_time()')
                elif fn_upper in ("RANDOM", "RAND"):
                    kwargs.append('server_default=func.random()')
                elif fn_upper == "GEN_RANDOM_UUID":
                    kwargs.append('server_default=func.gen_random_uuid()')
                elif fn_upper == "AUTO_NOW":
                    kwargs.append('server_default=func.now()')
                    kwargs.append("onupdate=func.now()")
                elif fn_upper == "AUTO_NOW_ADD":
                    kwargs.append('server_default=func.now()')
                elif fn_raw.endswith("()"):
                    kwargs.append(f"server_default=func.{fn_raw}")
                else:
                    kwargs.append(f"server_default=text('{fn_raw}')")
            elif isinstance(col.default, bool):
                kwargs.append(f"default={str(col.default).lower()}")
            elif isinstance(col.default, str):
                kwargs.append(f"default='{col.default}'")
            elif isinstance(col.default, (int, float)):
                kwargs.append(f"default={col.default}")

        if kwargs:
            lines.append(f"    {col.name} = Column({type_str}, {', '.join(kwargs)})")
        else:
            lines.append(f"    {col.name} = Column({type_str})")

        return lines, types_used

    def _to_pascal(self, name: str) -> str:
        """Convert a snake_case or mixed name to PascalCase."""
        # Handle snake_case
        parts = name.split("_")
        return "".join(p.capitalize() for p in parts if p)
