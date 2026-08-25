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

    # Diff enums
    a_enum_names = {e.name for e in schema_a.enums}
    b_enum_names = {e.name for e in schema_b.enums}
    enum_added = b_enum_names - a_enum_names
    enum_removed = a_enum_names - b_enum_names
    if enum_added:
        lines.append(f"\n+ Added enums: {', '.join(sorted(enum_added))}")
    if enum_removed:
        lines.append(f"\n- Removed enums: {', '.join(sorted(enum_removed))}")
    for ename in sorted(a_enum_names & b_enum_names):
        ea = next(e for e in schema_a.enums if e.name == ename)
        eb = next(e for e in schema_b.enums if e.name == ename)
        if ea.values != eb.values:
            lines.append(f"\n  enum {ename}:")
            lines.append(f"    values: {ea.values} → {eb.values}")

    # Determine if any differences were found
    has_table_diffs = any(
        bool(
            _diff_tables(
                next(t for t in schema_a.tables if t.name == name),
                next(t for t in schema_b.tables if t.name == name),
            )
        )
        for name in common
    )
    if (
        not added
        and not removed
        and not has_table_diffs
        and not enum_added
        and not enum_removed
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
        if ca.unique != cb.unique:
            diffs.append(f'~ column "{name}": unique={ca.unique} → {cb.unique}')
        if ca.comment != cb.comment:
            diffs.append(f'~ column "{name}": comment="{ca.comment}" → "{cb.comment}"')

    # Compare indexes
    a_idx = {idx.name: idx for idx in ta.indexes if idx.name}
    b_idx = {idx.name: idx for idx in tb.indexes if idx.name}
    for name in sorted(set(b_idx.keys()) - set(a_idx.keys())):
        diffs.append(f'+ index "{name}"')
    for name in sorted(set(a_idx.keys()) - set(b_idx.keys())):
        diffs.append(f'- index "{name}"')

    return diffs
