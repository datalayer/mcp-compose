# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""The Earthdata + Jupyter composition loads, and says what it means to say.

The example is a promise about how discovery and execution are split between
two servers; this checks the composition file keeps that promise rather than
proof-reading it: both servers are there, both are stdio subprocesses the
composer owns, the tools are prefixed by server so an agent can tell
`earthdata_*` from `jupyter_*`, and the composition is reachable over
Streamable HTTP, which is how a Contents MCP source would address it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_compose.config import ConflictResolutionStrategy, RestartPolicy
from mcp_compose.config_loader import load_config

EXAMPLE = Path(__file__).parent.parent / "examples" / "earthdata-jupyter"
CREDENTIALS = {
    "EARTHDATA_USERNAME": "nasa-user",
    "EARTHDATA_PASSWORD": "nasa-secret",
    "DOCUMENT_URL": "http://jupyter:8888",
    "DOCUMENT_TOKEN": "doc-token",
    "DOCUMENT_ID": "notebook.ipynb",
    "RUNTIME_URL": "http://jupyter:8888",
    "RUNTIME_TOKEN": "runtime-token",
}


@pytest.fixture
def composition(monkeypatch: pytest.MonkeyPatch):
    for name, value in CREDENTIALS.items():
        monkeypatch.setenv(name, value)
    return load_config(EXAMPLE / "mcp_compose.toml")


def test_the_composition_carries_both_servers_as_managed_stdio_subprocesses(composition) -> None:
    servers = {server.name: server for server in composition.servers.proxied.stdio}

    assert set(servers) == {"earthdata", "jupyter"}
    assert servers["earthdata"].command[0] == "earthdata-mcp-server"
    assert servers["jupyter"].command[0] == "jupyter-mcp-server"
    for server in servers.values():
        assert "--transport" in server.command and "stdio" in server.command
        assert server.restart_policy is RestartPolicy.ON_FAILURE
        # The working directory resolves to the example, not to a literal.
        assert server.working_dir == str(EXAMPLE.resolve())
    assert not composition.servers.proxied.sse
    assert not composition.servers.proxied.streamable_http


def test_tools_are_prefixed_by_server_and_exposed_over_streamable_http(composition) -> None:
    assert composition.composer.name == "earthdata-jupyter"
    assert composition.composer.conflict_resolution is ConflictResolutionStrategy.PREFIX
    assert composition.transport.streamable_http_enabled is True
    assert composition.transport.streamable_http_path == "/mcp"
    assert composition.transport.stdio_enabled is False
    assert composition.transport.sse_enabled is False


def test_credentials_come_from_the_environment_and_never_from_the_file(composition) -> None:
    servers = {server.name: server for server in composition.servers.proxied.stdio}
    text = (EXAMPLE / "mcp_compose.toml").read_text()

    assert servers["earthdata"].env["EARTHDATA_PASSWORD"] == "nasa-secret"
    assert servers["jupyter"].env["DOCUMENT_TOKEN"] == "doc-token"
    for value in CREDENTIALS.values():
        assert value not in text


def test_the_manifest_call_asks_for_a_manifest_not_a_download() -> None:
    """The README's example arguments must not be the one mode that moves bytes."""
    arguments = json.loads((EXAMPLE / "manifest.json").read_text())

    assert arguments["mode"] == "manifest"
    assert arguments["short_name"]
    assert len(arguments["bounding_box"]) == 4


def test_the_readme_walks_manifest_then_script_then_execute() -> None:
    readme = (EXAMPLE / "README.md").read_text()
    readme = readme[readme.index("## Manifest") :]
    manifest = readme.index('"mode": "manifest"')
    script = readme.index('"mode": "script"')
    execute = readme.index("jupyter_execute_code")

    assert manifest < script < execute
    assert "download" in readme
