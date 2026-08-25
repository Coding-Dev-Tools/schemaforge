"""Custom type mapping configuration for SchemaForge.

Allows users to override default type mappings between ColumnTypes
and format-specific type strings via YAML or JSON configuration files.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .ir import Column

# Supported config file extensions
_CONFIG_EXTENSIONS = {".yaml", ".yml", ".json"}


class TypeConfig:
    """Loads and manages custom type mapping overrides.

    Loaded from YAML/JSON files with the format::

        overrides:
          sql:
            STRING: "VARCHAR({length})"
            UUID: "UUID"
          prisma:
            STRING: "String @db.VarChar({length})"

    Template variables in override strings:
        ``{length}`` — string/numeric length
        ``{precision}`` — decimal precision
        ``{scale}`` — decimal scale
        ``{values}`` — comma-separated ENUM values
    """

    def __init__(self, overrides: dict[str, dict[str, str]] | None = None):
        """Initialize with optional format → type overrides.

        Args:
            overrides: Nested dict keyed by format name (e.g. 'sql', 'prisma')
                then ColumnType enum value (e.g. 'STRING', 'UUID') to type string.
        """
        self._overrides: dict[str, dict[str, str]] = overrides or {}

    def get_override(
        self, col: Column, fmt: str, type_args: dict[str, Any] | None = None
    ) -> str | None:
        """Resolve a custom type override for a column in a format.

        Args:
            col: The column to resolve.
            fmt: Format name (e.g. 'sql', 'prisma', 'sqlalchemy').
            type_args: Optional type arguments dict (uses col.type_args if None).

        Returns:
            Overridden type string, or None if no override exists.
        """
        fmt_overrides = self._overrides.get(fmt)
        if not fmt_overrides:
            return None

        key = col.type.name  # e.g. "STRING", "UUID", "DECIMAL"
        template = fmt_overrides.get(key)
        if not template:
            return None

        args = type_args if type_args is not None else col.type_args
        # Apply template variables
        result = template
        if args:
            for arg_key, arg_val in args.items():
                if isinstance(arg_val, list):
                    result = result.replace(
                        "{" + arg_key + "}", ", ".join(f"'{v}'" for v in arg_val)
                    )
                else:
                    result = result.replace("{" + arg_key + "}", str(arg_val))
        # Remove any remaining unresolved placeholders
        result = re.sub(r"\{[^}]+\}", "", result)
        return result

    def get_custom_type(self, custom_type_name: str, fmt: str) -> str | None:
        """Resolve a custom type name to a format-specific type string.

        Custom types are overrides keyed by type name (e.g. 'JSONB', 'HSTORE')
        rather than ColumnType enum names. The override must be defined in the
        config under ``overrides.<fmt>.<CUSTOM_TYPE_NAME>``.

        Args:
            custom_type_name: Name of the custom type (e.g. 'JSONB', 'HSTORE').
            fmt: Format name.

        Returns:
            Format-specific type string, or None if not defined.
        """
        fmt_overrides = self._overrides.get(fmt)
        if fmt_overrides:
            return fmt_overrides.get(custom_type_name.upper())
        return None

    @classmethod
    def from_file(cls, path: str | os.PathLike) -> TypeConfig:
        """Load type configuration from a YAML or JSON file.

        Args:
            path: Path to config file (.yaml, .yml, or .json).

        Returns:
            Loaded TypeConfig instance.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file extension is unsupported or parsing fails.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Type config not found: {path}")
        if path.suffix.lower() not in _CONFIG_EXTENSIONS:
            raise ValueError(
                f"Unsupported config format: {path.suffix}. "
                f"Supported: {', '.join(sorted(_CONFIG_EXTENSIONS))}"
            )

        raw: dict[str, Any] = {}
        if path.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore[import-untyped]
            except ImportError:
                raise ImportError(
                    "PyYAML is required for YAML type config files. "
                    "Install it with: pip install pyyaml"
                ) from None
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
        else:
            with open(path) as f:
                raw = json.load(f)

        overrides = raw.get("overrides", {}) or {}
        return cls(overrides)

    def merge(self, other: TypeConfig) -> TypeConfig:
        """Merge another TypeConfig into this one (other takes precedence).

        Args:
            other: Another TypeConfig whose overrides take priority.

        Returns:
            New merged TypeConfig.
        """
        merged = dict(self._overrides)
        for fmt, overrides in other._overrides.items():
            if fmt in merged:
                merged[fmt] = {**merged[fmt], **overrides}
            else:
                merged[fmt] = dict(overrides)
        return TypeConfig(merged)


# Default shared instance (no overrides)
EMPTY_CONFIG = TypeConfig()
