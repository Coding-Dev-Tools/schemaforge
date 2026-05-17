"""Schema consistency checker — ensures all format representations are equivalent."""
from __future__ import annotations

from pathlib import Path

from .convert import convert_schema
from .diff import diff_schemas
from .type_config import TypeConfig

# Format extensions for auto-detection
_FORMAT_EXTENSIONS: dict[str, str] = {
    ".sql": "sql",
    ".prisma": "prisma",
    ".ts": "drizzle",
    ".tsx": "drizzle",
    ".py": "django",
    ".json": "json_schema",
    ".graphql": "graphql",
    ".gql": "graphql",
}


def detect_format(path: str) -> str | None:
    """Detect schema format from file extension."""
    ext = Path(path).suffix.lower()
    return _FORMAT_EXTENSIONS.get(ext)


def check_directory(
    directory: str,
    canonical: str = "sql",
    type_map_path: str | None = None,
) -> str:
    """Check that all schema files in a directory produce equivalent schemas.

    Converts each file to the canonical format and diffs them pairwise.
    Returns a human-readable report string suitable for CI output.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    # Load type config if specified
    type_config: TypeConfig | None = None
    if type_map_path:
        type_config = TypeConfig.from_file(type_map_path)

    # Collect all schema files by format
    schema_files: list[tuple[str, str, str]] = []  # (path, format, display_name)
    for fpath in sorted(dir_path.iterdir()):
        if not fpath.is_file():
            continue
        fmt = detect_format(str(fpath))
        if fmt and fmt != "alembic":  # Skip Alembic (generator-only)
            schema_files.append((str(fpath), fmt, fpath.name))

    if len(schema_files) < 2:
        return f"Need at least 2 schema files to compare (found {len(schema_files)})"

    # Convert all to canonical format
    converted: list[tuple[str, str, str]] = []
    failures: list[str] = []

    for fpath, fmt, name in schema_files:
        try:
            text = Path(fpath).read_text(encoding="utf-8")
            result = convert_schema(text, fmt, canonical, type_config=type_config)
            converted.append((fpath, name, result))
        except Exception as e:
            failures.append(f"  FAIL {name}: {e}")

    if not converted:
        return "No files could be converted to {}\n{}".format(
            canonical, "\n".join(failures)
        )

    # Compare pairwise
    mismatches: list[str] = []
    for i in range(len(converted)):
        for j in range(i + 1, len(converted)):
            _, name_a, text_a = converted[i]
            _, name_b, text_b = converted[j]

            if text_a == text_b:
                continue

            # Found a mismatch — run a proper diff
            try:
                diff_result = diff_schemas(text_a, text_b, canonical)
                mismatches.append(
                    f"MISMATCH: {name_a} vs {name_b}\n{diff_result}\n"
                )
            except Exception as e:
                mismatches.append(
                    f"ERROR diffing {name_a} vs {name_b}: {e}\n"
                )

    # Build report
    lines: list[str] = []
    lines.append(f"Schema consistency check — all files compared via {canonical}")
    lines.append(f"  Files found: {len(schema_files)}")
    lines.append(f"  Files converted: {len(converted)}")

    if failures:
        lines.append(f"  Conversion failures: {len(failures)}")
        lines.extend(failures)

    if mismatches:
        lines.append(f"  Mismatches: {len(mismatches)}")
        lines.append("")
        for m in mismatches:
            lines.append(m)
        lines.append("FAIL: Schema files are not equivalent")
    else:
        lines.append("  Mismatches: 0")
        if not failures:
            lines.append("PASS: All schema files are equivalent")

    return "\n".join(lines)
