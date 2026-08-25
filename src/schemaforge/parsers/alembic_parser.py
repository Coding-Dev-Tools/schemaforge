"""Stub parser for Alembic migration scripts.

Parsing Alembic migrations back to IR is complex (requires AST analysis).
This parser is a placeholder — it raises NotImplementedError.
The AlembicGenerator is the primary use case (IR → migration).
"""

from __future__ import annotations

from ..ir import Schema


class AlembicParser:
    """Stub parser — Alembic migrations can only be generated, not parsed (yet)."""

    def parse(self, text: str) -> Schema:
        """Parse an Alembic migration script into Schema IR.

        Raises NotImplementedError — this is a stub for bidirectional
        format registration only.
        """
        raise NotImplementedError(
            "Parsing Alembic migrations back to Schema IR is not yet supported. "
            "Alembic is available as a generator-only format (IR → migration)."
        )
