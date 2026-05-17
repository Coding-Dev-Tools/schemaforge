"""Schema diffing — compare two schemas and show differences.

Uses the IR directly to compare schemas structurally.
"""
from __future__ import annotations

from .convert import _registry


def diff_schemas(text_a: str, text_b: str, fmt: str) -> str:
    """Diff two schema files in the same format.

    Args:
        text_a: First schema text
        text_b: Second schema text
        fmt: Format of both schemas

    Returns:
        Human-readable diff output
    """
    if fmt not in _registry:
        return f"Unsupported format: {fmt} (detailed diff coming in v0.5.0)"

    parser_cls, _ = _registry[fmt]
    parser = parser_cls()
    schema_a = parser.parse(text_a)
    schema_b = parser.parse(text_b)

    lines = ["=== Schema Diff ==="]

    a_names = {t.name for t in schema_a.tables}
    b_names = {t.name for t in schema_b.tables}

    added = b_names - a_names
    removed = a_names - b_names

    if added:
        lines.append(f"\n+ Added tables: {', '.join(sorted(added))}")
    if removed:
        lines.append(f"\n- Removed tables: {', '.join(sorted(removed))}")

    common = a_names & b_names
    for name in sorted(common):
        ta = next(t for t in schema_a.tables if t.name == name)
        tb = next(t for t in schema_b.tables if t.name == name)
        diffs = _diff_tables(ta, tb)
        if diffs:
            lines.append(f"\n  {name}:")
            lines.extend(f"    {d}" for d in diffs)

    if not added and not removed and not any(
        _diff_tables(
            next(t for t in schema_a.tables if t.name == name),
            next(t for t in schema_b.tables if t.name == name)
        ) for name in common
    ):
        lines.append("No differences found.")

    return "\n".join(lines)


def _diff_tables(ta, tb) -> list[str]:
    """Diff two tables and return list of differences."""
    diffs = []

    a_cols = {c.name: c for c in ta.columns}
    b_cols = {c.name: c for c in tb.columns}

    added = set(b_cols.keys()) - set(a_cols.keys())
    removed = set(a_cols.keys()) - set(b_cols.keys())

    for name in sorted(added):
        diffs.append(f'+ column "{name}" ({b_cols[name].type.value})')
    for name in sorted(removed):
        diffs.append(f'- column "{name}" ({a_cols[name].type.value})')

    for name in sorted(a_cols.keys() & b_cols.keys()):
        ca = a_cols[name]
        cb = b_cols[name]
        if ca.type != cb.type:
            diffs.append(f'~ column "{name}": {ca.type.value} → {cb.type.value}')
        if ca.nullable != cb.nullable:
            diffs.append(f'~ column "{name}": nullable={ca.nullable} → {cb.nullable}')
        if ca.primary_key != cb.primary_key:
            diffs.append(f'~ column "{name}": PK={ca.primary_key} → {cb.primary_key}')
        if ca.default != cb.default:
            diffs.append(f'~ column "{name}": default={ca.default} → {cb.default}')

    return diffs
