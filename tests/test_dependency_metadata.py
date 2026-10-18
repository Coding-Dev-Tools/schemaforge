"""Keep the installed MCP extras on the supported security-patched SDK line."""

import pytest
from importlib.metadata import requires
from packaging.requirements import Requirement


@pytest.mark.parametrize("extra", ["dev", "mcp"])
def test_mcp_extra_requires_patched_v1_sdk(extra):
    requirements = [Requirement(value) for value in requires("schemaforge-cli") or []]
    mcp_requirements = [
        requirement
        for requirement in requirements
        if requirement.name == "mcp"
        and requirement.marker is not None
        and requirement.marker.evaluate({"extra": extra})
    ]

    assert len(mcp_requirements) == 1
    supported = mcp_requirements[0].specifier
    assert "1.30.0" in supported
    assert "1.29.1" not in supported  # CVE-2026-59951 is patched in 1.30.0.
    assert "2.0.0" not in supported  # SchemaForge uses the v1 FastMCP API.
