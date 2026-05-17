"""Generator: SchemaForge IR → SQLAlchemy declarative model schema."""
from __future__ import annotations

from ..ir import Column, ColumnType, Schema
from ..type_config import TypeConfig
from ._base import build_type_string, format_literal_default, resolve_fn_default


class SQLAlchemyGenerator:
    """Convert Schema IR to SQLAlchemy declarative model Python format."""

    def __init__(self, type_config: TypeConfig | None = None) -> None:
        """Initialize with optional custom type overrides."""
        self._type_config = type_config

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

        # Build type string using shared helper
        sa_type = build_type_string(col, self._TYPE_MAP,
            string_fmt="{}({})",
            string_default="String",
            decimal_fmt="{}({}, {})",
            decimal_default="Numeric",
            decimal_precision=10,
            decimal_scale=2,
            fmt="sqlalchemy",
            type_config=self._type_config,
        )
        types_used.add(sa_type.split("(")[0])

        type_str = sa_type

        kwargs: list[str] = []

        # Primary key
        if col.primary_key:
            kwargs.append("primary_key=True")
            if col.type != ColumnType.INTEGER or col.type_args.get("autoincrement") is False:
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

        # fn: defaults (server_default)
        fn_default = resolve_fn_default(col, fn_wrapper="func.{}", expr_fallback="text('{}')")
        if fn_default:
            kwargs.append(f"server_default={fn_default}")

        # Literal defaults
        if col.default is not None and not (isinstance(col.default, str) and col.default.startswith("fn:")):
            lit = format_literal_default(col)
            if isinstance(col.default, (bool, int, float, str)):
                kwargs.append(f"default={lit}")

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
