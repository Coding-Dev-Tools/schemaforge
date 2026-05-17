"""Shared base utilities for SchemaForge generators.

Provides common helpers for type resolution, type arguments,
and default value handling to reduce duplication across generators.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..ir import Column, ColumnType

if TYPE_CHECKING:
    from ..type_config import TypeConfig


def resolve_type(
    col: Column,
    type_map: dict[ColumnType, str],
    *,
    fmt: str = "",
    type_config: TypeConfig | None = None,
) -> str:
    """Resolve a column's base type string from the type map.

    Handles CUSTOM types (drops through to col.custom_type),
    custom type overrides from TypeConfig, and unknown types
    (falls back to "String").

    Args:
        col: The column to resolve.
        type_map: Default ColumnType → format-specific type string mapping.
        fmt: Format name for TypeConfig override lookup (e.g. 'sql').
        type_config: Optional custom type overrides.

    Returns:
        Format-specific type string.
    """
    # CUSTOM type takes priority
    if col.type == ColumnType.CUSTOM and col.custom_type:
        return col.custom_type

    # Check TypeConfig overrides first (full resolution including type_args)
    if type_config and fmt:
        overridden = type_config.get_override(col, fmt)
        if overridden:
            return overridden

    return type_map.get(col.type, "String")


def has_type_override(col: Column, fmt: str, type_config: TypeConfig | None) -> bool:
    """Check if a column has a custom type override for a given format.

    Generators can use this to skip their special-case formatting
    when an override is active (e.g. String with @db.VarChar).
    """
    if not type_config or not fmt:
        return False
    fmt_overrides = type_config._overrides.get(fmt)  # type: ignore[union-attr]
    if not fmt_overrides:
        return False
    return col.type.name in fmt_overrides


def build_type_string(
    col: Column,
    type_map: dict[ColumnType, str],
    *,
    string_fmt: str = "{}({})",
    string_default: str = "String",
    decimal_fmt: str = "{}({}, {})",
    decimal_default: str = "Numeric",
    decimal_precision: int = 10,
    decimal_scale: int = 2,
    enum_fmt: str = "Enum({})",
    fmt: str = "",
    type_config: TypeConfig | None = None,
) -> str:
    """Build a full type string including type arguments.

    Base type is resolved via ``resolve_type()``, then type arguments
    (length for STRING, precision/scale for DECIMAL, values for ENUM)
    are appended using the provided format strings.

    Args:
        col: The column to build a type string for.
        type_map: ColumnType → format-specific type string mapping.
        string_fmt: Format for STRING with length (e.g. '{}({})' for
            'VARCHAR(255)' or 'String({})' for 'String(255)').
        string_default: Base type name for STRING when no length.
        decimal_fmt: Format for DECIMAL with precision/scale.
        decimal_default: Base type name for DECIMAL.
        decimal_precision: Default precision when not in type_args.
        decimal_scale: Default scale when not in type_args.
        enum_fmt: Format for inline ENUM values (e.g. 'Enum({})' for
            'Enum(small, medium, large)').
        fmt: Format name for TypeConfig override lookup (e.g. 'sql').
        type_config: Optional custom type overrides.

    Returns:
        Full type string (e.g. 'VARCHAR(255)', 'Numeric(10, 2)').
    """
    base = resolve_type(col, type_map, fmt=fmt, type_config=type_config)

    if col.type == ColumnType.STRING and "length" in col.type_args:
        return string_fmt.format(base, col.type_args["length"])

    if col.type == ColumnType.DECIMAL:
        p = col.type_args.get("precision", decimal_precision)
        s = col.type_args.get("scale", decimal_scale)
        return decimal_fmt.format(base, p, s)

    if col.type == ColumnType.ENUM and col.type_args.get("values"):
        values = ", ".join(f"'{v}'" for v in col.type_args["values"])
        return enum_fmt.format(values)

    return base


# ── fn: default resolution ──

# Mapping of SQL function names to canonical representations.
# Keys are the UPPER case function name without parens.
FN_DEFAULT_MAP: dict[str, str] = {
    "CURRENT_TIMESTAMP": "now()",
    "NOW": "now()",
    "CURRENT_DATE": "current_date()",
    "CURRENT_TIME": "current_time()",
    "LOCALTIMESTAMP": "now()",
    "LOCALTIME": "current_time()",
    "GEN_RANDOM_UUID": "gen_random_uuid()",
    "RANDOM": "random()",
    "RAND": "random()",
    "UUID": "gen_random_uuid()",
    "CURDATE": "current_date()",
    "CURTIME": "current_time()",
    "SYSDATE": "now()",
    "UTC_TIMESTAMP": "now()",
    "UTC_DATE": "current_date()",
    "UTC_TIME": "current_time()",
}

# Fallback function name for unknown functions ending with ().
FN_UNKNOWN_CALL_FMT = "{}"


def resolve_fn_default(
    col: Column,
    fn_wrapper: str = "func.{}",
    call_fallback: str | None = None,
    expr_fallback: str = "text('{}')",
) -> str | None:
    """Resolve a column's fn: default to a format-specific expression.

    Args:
        col: The column whose default to resolve.
        fn_wrapper: Format string wrapping the resolved function name
            (e.g. 'func.{}' → 'func.now()').
        call_fallback: Optional override format for unknown function calls.
            If None, falls back to ``fn_wrapper`` + raw fn expression.
        expr_fallback: Format for non-call fn expressions
            (e.g. 'text(\"{}\")' for SQLAlchemy).

    Returns:
        Formatted default expression string, or None if no fn: default.
    """
    if col.default is None:
        return None
    if not (isinstance(col.default, str) and col.default.startswith("fn:")):
        return None

    fn_expr = col.default[3:]
    fn_upper = fn_expr.upper().rstrip("()")

    if fn_upper in FN_DEFAULT_MAP:
        return fn_wrapper.format(FN_DEFAULT_MAP[fn_upper])

    if fn_expr.endswith("()"):
        fmt = call_fallback if call_fallback is not None else fn_wrapper
        return fmt.format(fn_expr)

    return expr_fallback.format(fn_expr)


def format_literal_default(col: Column) -> str | None:
    """Format a literal (non-fn) default value as a string.

    Handles bool, str, int, float. Returns None if no default or fn: default.

    The returned string is the value itself (not wrapped in DEFAULT/@default).
    """
    if col.default is None:
        return None
    if isinstance(col.default, str) and col.default.startswith("fn:"):
        return None

    if isinstance(col.default, bool):
        return str(col.default).lower()
    if isinstance(col.default, str):
        return f"'{col.default}'"
    if isinstance(col.default, (int, float)):
        return str(col.default)
    return None
