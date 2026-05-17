"""Parser: SQLAlchemy declarative model schema → SchemaForge IR."""
from __future__ import annotations

import contextlib
import re

from ..ir import Column, ColumnType, Schema, Table


class SQLAlchemyParser:
    """Parse SQLAlchemy declarative model Python files into Schema IR.

    Supports the standard declarative pattern:
        class User(Base):
            __tablename__ = 'users'
            id = Column(Integer, primary_key=True)
            name = Column(String(100), nullable=False)
    """

    _TYPE_MAP: dict[str, ColumnType] = {
        "String": ColumnType.STRING,
        "Text": ColumnType.TEXT,
        "Unicode": ColumnType.STRING,
        "UnicodeText": ColumnType.TEXT,
        "Integer": ColumnType.INTEGER,
        "BigInteger": ColumnType.INTEGER,
        "SmallInteger": ColumnType.INTEGER,
        "Float": ColumnType.FLOAT,
        "Double": ColumnType.FLOAT,
        "Real": ColumnType.FLOAT,
        "Boolean": ColumnType.BOOLEAN,
        "DateTime": ColumnType.DATETIME,
        "Date": ColumnType.DATE,
        "Time": ColumnType.TIME,
        "Interval": ColumnType.CUSTOM,
        "LargeBinary": ColumnType.BLOB,
        "BLOB": ColumnType.BLOB,
        "PickleType": ColumnType.CUSTOM,
        "JSON": ColumnType.JSON,
        "JSONB": ColumnType.CUSTOM,
        "ARRAY": ColumnType.CUSTOM,
        "Enum": ColumnType.ENUM,
        "Numeric": ColumnType.DECIMAL,
        "DECIMAL": ColumnType.DECIMAL,
        "UUID": ColumnType.UUID,
        "Uuid": ColumnType.UUID,
    }

    def parse(self, text: str) -> Schema:
        """Parse SQLAlchemy model source into a Schema IR."""
        schema = Schema()

        # Find all declarative model classes
        models = self._find_model_classes(text)
        for model_name, model_body in models:
            table = self._parse_model(model_name, model_body)
            if table:
                schema.tables.append(table)

        return schema

    def _find_model_classes(self, text: str) -> list[tuple[str, str]]:
        """Find all classes inheriting from a declarative base.

        Detects patterns like:
          class User(Base):
          class Product(DeclarativeBase):
        """
        models: list[tuple[str, str]] = []
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Detect class that inherits from a base (Base, DeclarativeBase, etc.)
            # Exclude classes that themselves define the base
            model_m = re.match(
                r"class\s+(\w+)\s*\(\s*(\w+)\s*\)\s*:",
                stripped,
            )
            # Also match: class User(mixins..., Base):
            model_multi = re.match(
                r"class\s+(\w+)\s*\((.+)\)\s*:",
                stripped,
            )

            if model_m:
                model_name = model_m.group(1)
                base_name = model_m.group(2)
                # Skip base class definitions themselves
                if base_name.lower() in ("declarative_base", "declarativebase",
                                          "as_declarative", "registry"):
                    i += 1
                    continue
                # Check if any base looks like a declarative base
                bases = [b.strip() for b in base_name.split(",")]
                is_model = any(
                    b in ("Base", "DeclarativeBase", "DeclarativeMeta")
                    or b.endswith("Base")
                    for b in bases
                )
                if not is_model:
                    i += 1
                    continue
            elif model_multi:
                model_name = model_multi.group(1)
                base_list = model_multi.group(2)
                bases = [b.strip() for b in base_list.split(",")]
                is_model = any(
                    b in ("Base", "DeclarativeBase", "DeclarativeMeta")
                    or b.endswith("Base")
                    for b in bases
                )
                if not is_model:
                    i += 1
                    continue
            else:
                i += 1
                continue

            # Collect the body (indented lines)
            body_lines: list[str] = []
            i += 1
            while i < len(lines):
                if lines[i].strip() and not lines[i].startswith((" ", "\t")):
                    break
                stripped_body = lines[i].strip()
                if stripped_body and not stripped_body.startswith("#"):
                    body_lines.append(lines[i])
                i += 1

            models.append((model_name, "\n".join(body_lines)))
            continue

        return models

    def _parse_model(self, name: str, body: str) -> Table | None:
        """Parse a SQLAlchemy model body into a Table."""
        # Try to extract __tablename__
        table_name_m = re.search(
            r'__tablename__\s*=\s*["\'](\w+)["\']',
            body,
        )
        table_name = table_name_m.group(1) if table_name_m else name

        table = Table(name=table_name)

        # Parse Column declarations: name = Column(Type, ...)
        # Also handle: name: type = Column(...)
        for line in body.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Skip special attributes
            if stripped.startswith("__"):
                continue
            # Skip relationship() calls and backrefs
            if "relationship(" in stripped or "backref" in stripped:
                continue
            # Skip association_proxy and hybrid_property
            if "association_proxy" in stripped or "hybrid_property" in stripped:
                continue

            # Detect Column assignment with type annotation
            # pattern: name: type = Column(Type, ...)  OR  name = Column(Type, ...)
            col_m = re.match(
                r"(\w+)\s*(?::\s*\w+\s*)?=\s*Column\s*\(",
                stripped,
            )
            if not col_m:
                continue

            col_name = col_m.group(1)

            # Extract everything inside Column(...)
            args_start = stripped.index("(", stripped.index("Column") + 6)
            paren_depth = 0
            args_end = len(stripped)
            for j, ch in enumerate(stripped[args_start:]):
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
                    if paren_depth == 0:
                        args_end = args_start + j
                        break
            col_args = stripped[args_start + 1:args_end]

            # Parse the Column contents
            col = self._parse_column(col_name, col_args)
            if col:
                table.columns.append(col)

        return table

    def _parse_column(self, name: str, args_text: str) -> Column | None:
        """Parse a Column(...) argument list into a Column object."""
        if not args_text.strip():
            return None

        # The first positional argument is typically the type
        # Split args respecting nested parens
        args = self._split_args(args_text)

        if not args:
            return None

        # First arg should be the type
        type_name = args[0].strip()

        # Handle generic types: String(255), Numeric(10, 2), etc.
        type_base, type_params = self._parse_generic_type(type_name)
        col_type = self._TYPE_MAP.get(type_base, ColumnType.CUSTOM)

        type_args: dict = {}
        if col_type == ColumnType.STRING and type_params:
            with contextlib.suppress(ValueError, TypeError):
                type_args["length"] = int(type_params[0])
        elif col_type == ColumnType.DECIMAL and type_params:
            try:
                if len(type_params) >= 1:
                    type_args["precision"] = int(type_params[0])
                if len(type_params) >= 2:
                    type_args["scale"] = int(type_params[1])
            except (ValueError, TypeError):
                pass

        # Parse kwargs from the remaining args
        kwargs = self._parse_kwargs(args[1:])

        nullable_str = kwargs.get("nullable", "")
        # SQLAlchemy default for nullable is True
        nullable = nullable_str.lower() != "false" if nullable_str else True

        unique = kwargs.get("unique", "false").lower() == "true"
        is_pk = kwargs.get("primary_key", "false").lower() == "true"
        autoincrement = kwargs.get("autoincrement", "")

        col = Column(
            name=name,
            type=col_type,
            type_args=type_args,
            primary_key=is_pk,
            nullable=nullable,
            unique=unique,
        )

        # Default value
        if "default" in kwargs:
            raw = kwargs["default"]
            if raw.lower() in ("true", "false"):
                col.default = raw.lower() == "true"
            elif raw == "None":
                col.default = None
            elif raw.startswith("func.") or raw.startswith("text("):
                # SQL function defaults: func.now(), text('...')
                fn_name = raw.replace("func.", "").replace("text(", "").strip("'\"")
                col.default = f"fn:{fn_name}"
            elif raw.isdigit() or raw.startswith("-") and raw[1:].isdigit():
                col.default = int(raw)
            else:
                try:
                    col.default = float(raw)
                except ValueError:
                    col.default = raw.strip("'\"")

        # server_default
        if "server_default" in kwargs:
            raw = kwargs["server_default"]
            if raw.startswith("func.") or raw.startswith("text("):
                fn_name = raw.replace("func.", "").replace("text(", "").strip("'\"")
                col.default = f"fn:{fn_name}"

        # Handle autoincrement=False on integer PK
        if is_pk and autoincrement.lower() == "false":
            col.type_args["autoincrement"] = False

        if col_type == ColumnType.CUSTOM and type_base:
            col.custom_type = type_base

        return col

    def _parse_generic_type(self, type_text: str) -> tuple[str, list[str]]:
        """Parse a type like 'String(255)' into ('String', ['255'])."""
        m = re.match(r"(\w+)\s*\(([^)]*)\)", type_text)
        if m:
            base = m.group(1)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            return base, params
        return type_text, []

    def _split_args(self, text: str) -> list[str]:
        """Split comma-separated arguments respecting nested parens and brackets."""
        args: list[str] = []
        depth = 0
        current = ""
        in_bracket = 0
        in_angle = 0

        for ch in text:
            if ch in "({[":
                if ch == "(" or ch == "{":
                    depth += 1
                if ch == "[":
                    in_bracket += 1
            elif ch in ")}]":
                if ch == ")" or ch == "}":
                    depth -= 1
                if ch == "]":
                    in_bracket -= 1
            elif ch == "<":
                in_angle += 1
            elif ch == ">":
                in_angle -= 1
            elif ch == "," and depth == 0 and in_bracket == 0 and in_angle == 0:
                args.append(current.strip())
                current = ""
                continue

            current += ch

        if current.strip():
            args.append(current.strip())

        return args

    def _parse_kwargs(self, args: list[str]) -> dict[str, str]:
        """Parse keyword arguments from a list of argument strings."""
        kwargs: dict[str, str] = {}
        for arg in args:
            kv_match = re.match(r"(\w+)\s*=\s*(.+)", arg)
            if not kv_match:
                continue
            key = kv_match.group(1)
            value = kv_match.group(2).strip()

            # Strip quotes from string values
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                kwargs[key] = value[1:-1]
            elif value.lower() in ("true", "false"):
                kwargs[key] = value.lower()
            elif value == "None":
                kwargs[key] = "None"
            elif value.startswith("func.") or value.startswith("text("):
                kwargs[key] = value
            else:
                kwargs[key] = value

        return kwargs
