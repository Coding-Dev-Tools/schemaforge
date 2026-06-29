"""Parser: Django model schema → SchemaForge IR."""

from __future__ import annotations

import contextlib
import re

from ..ir import Column, ColumnType, Schema, Table


class DjangoParser:
    """Parse Django model Python files into Schema IR."""

    _FIELD_MAP: dict[str, ColumnType] = {
        "CharField": ColumnType.STRING,
        "EmailField": ColumnType.STRING,
        "SlugField": ColumnType.STRING,
        "URLField": ColumnType.STRING,
        "FilePathField": ColumnType.STRING,
        "IPAddressField": ColumnType.STRING,
        "GenericIPAddressField": ColumnType.STRING,
        "TextField": ColumnType.TEXT,
        "IntegerField": ColumnType.INTEGER,
        "BigIntegerField": ColumnType.INTEGER,
        "SmallIntegerField": ColumnType.INTEGER,
        "PositiveIntegerField": ColumnType.INTEGER,
        "PositiveSmallIntegerField": ColumnType.INTEGER,
        "AutoField": ColumnType.INTEGER,
        "BigAutoField": ColumnType.INTEGER,
        "SmallAutoField": ColumnType.INTEGER,
        "BooleanField": ColumnType.BOOLEAN,
        "NullBooleanField": ColumnType.BOOLEAN,
        "FloatField": ColumnType.FLOAT,
        "DecimalField": ColumnType.DECIMAL,
        "DateTimeField": ColumnType.DATETIME,
        "DateField": ColumnType.DATE,
        "TimeField": ColumnType.TIME,
        "DurationField": ColumnType.INTEGER,
        "BinaryField": ColumnType.BLOB,
        "JSONField": ColumnType.JSON,
        "UUIDField": ColumnType.UUID,
    }

    # Fields that are typically auto-set (skip default generation)
    _AUTO_FIELDS = {"DateTimeField", "DateField", "TimeField"}

    def parse(self, text: str) -> Schema:
        """Parse Django model source into a Schema IR."""
        schema = Schema()

        # Find all model classes
        models = self._find_model_classes(text)
        for model_name, model_body in models:
            table = self._parse_model(model_name, model_body)
            if table:
                schema.tables.append(table)

        return schema

    def _find_model_classes(self, text: str) -> list[tuple[str, str]]:
        """Find all classes inheriting from models.Model or Model."""
        models: list[tuple[str, str]] = []
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Detect: class Foo(models.Model):
            model_m = re.match(
                r"class\s+(\w+)\s*\(\s*(?:models\.)?Model\s*\)\s*:",
                stripped,
            )
            if model_m:
                model_name = model_m.group(1)
                # Collect the body (indented lines)
                body_lines: list[str] = []
                i += 1
                while i < len(lines):
                    if lines[i].strip() and not lines[i].startswith((" ", "\t")):
                        break
                    # Skip blank lines and comments
                    stripped_body = lines[i].strip()
                    if stripped_body and not stripped_body.startswith("#"):
                        body_lines.append(lines[i])
                    i += 1

                models.append((model_name, "\n".join(body_lines)))
                continue

            i += 1

        return models

    def _parse_model(self, name: str, body: str) -> Table | None:
        """Parse a Django model body into a Table."""
        table = Table(name=name)

        # Track fields for index generation

        # Parse field declarations
        for line in body.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Check for class Meta inner class
            if stripped.startswith("class Meta"):
                # Skip to collect Meta options
                continue

            # Check for field assignment: name = models.FieldType(...)
            field_m = re.match(
                r"(\w+)\s*=\s*(?:models\.)?(\w+)\(",
                stripped,
            )
            if not field_m:
                continue

            field_name = field_m.group(1)
            field_class = field_m.group(2)

            # Extract args between the outermost parens
            args_start = stripped.index(
                "(", stripped.index(field_class) + len(field_class)
            )
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
            field_args = stripped[args_start + 1 : args_end]

            col_type = self._FIELD_MAP.get(field_class, ColumnType.CUSTOM)

            # Parse kwargs
            kwargs = self._parse_kwargs(field_args)

            type_args: dict[str, int] = {}
            if "max_length" in kwargs:
                with contextlib.suppress(ValueError, TypeError):
                    type_args["length"] = int(kwargs["max_length"])
            if "max_digits" in kwargs:
                with contextlib.suppress(ValueError, TypeError):
                    type_args["precision"] = int(kwargs["max_digits"])
            if "decimal_places" in kwargs:
                with contextlib.suppress(ValueError, TypeError):
                    type_args["scale"] = int(kwargs["decimal_places"])

            is_pk = kwargs.get("primary_key", "false").lower() == "true"
            nullable = kwargs.get("null", "false").lower() == "true"
            unique = kwargs.get("unique", "false").lower() == "true"

            col = Column(
                name=field_name,
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
                    col.nullable = True
                elif raw.isdigit():
                    col.default = int(raw)
                else:
                    try:
                        col.default = float(raw)
                    except ValueError:
                        col.default = raw.strip("'\"")

            # Auto-set fields (auto_now, auto_now_add)
            if field_class in ("DateTimeField", "DateField", "TimeField"):
                if kwargs.get("auto_now_add", "false").lower() == "true":
                    col.default = "fn:auto_now_add"
                elif kwargs.get("auto_now", "false").lower() == "true":
                    col.default = "fn:auto_now"

            if col_type == ColumnType.CUSTOM:
                col.custom_type = field_class

            table.columns.append(col)

        return table

    def _parse_kwargs(self, args_text: str) -> dict[str, str]:
        """Parse Django field keyword arguments into a dict."""
        kwargs: dict[str, str] = {}
        if not args_text.strip():
            return kwargs

        # Handle positional kwarg pattern: max_length=255
        # Use a depth-aware parser
        i = 0
        while i < len(args_text):
            # Skip whitespace and commas
            while i < len(args_text) and args_text[i] in ", \t\n":
                i += 1
            if i >= len(args_text):
                break

            # Read key: key=value
            kv_match = re.match(r"(\w+)\s*=", args_text[i:])
            if not kv_match:
                # Skip positional args (just move past)
                while i < len(args_text) and args_text[i] != ",":
                    i += 1
                continue

            key = kv_match.group(1)
            i += kv_match.end()

            # Skip whitespace
            while i < len(args_text) and args_text[i] in " \t\n":
                i += 1
            if i >= len(args_text):
                break

            # Read value
            if args_text[i] in ("'", '"'):
                quote = args_text[i]
                i += 1
                val_start = i
                while i < len(args_text) and args_text[i] != quote:
                    if args_text[i] == "\\":
                        i += 1
                    i += 1
                kwargs[key] = args_text[val_start:i]
                i += 1  # Skip closing quote
            elif args_text[i : i + 4].lower() == "true":
                kwargs[key] = "true"
                i += 4
            elif args_text[i : i + 5].lower() == "false":
                kwargs[key] = "false"
                i += 5
            elif args_text[i : i + 4].lower() == "none":
                kwargs[key] = "None"
                i += 4
            elif args_text[i] == "{":
                # Dict literal — skip to matching }
                depth = 1
                i += 1
                while i < len(args_text) and depth > 0:
                    if args_text[i] == "{":
                        depth += 1
                    elif args_text[i] == "}":
                        depth -= 1
                    i += 1
            elif args_text[i] == "(":
                # Tuple — skip
                depth = 1
                i += 1
                while i < len(args_text) and depth > 0:
                    if args_text[i] == "(":
                        depth += 1
                    elif args_text[i] == ")":
                        depth -= 1
                    i += 1
            elif args_text[i] == "[":
                # List — skip
                depth = 1
                i += 1
                while i < len(args_text) and depth > 0:
                    if args_text[i] == "[":
                        depth += 1
                    elif args_text[i] == "]":
                        depth -= 1
                    i += 1
            elif args_text[i] == "-" or args_text[i].isdigit():
                # Number (possibly negative)
                num_match = re.match(r"-?\d+(?:\.\d+)?", args_text[i:])
                if num_match:
                    kwargs[key] = num_match.group(0)
                    i += num_match.end()
                else:
                    i += 1
            else:
                # Bare identifier (callable, etc.)
                id_match = re.match(r"\w+", args_text[i:])
                if id_match:
                    kwargs[key] = id_match.group(0)
                    i += id_match.end()
                else:
                    i += 1

        return kwargs
