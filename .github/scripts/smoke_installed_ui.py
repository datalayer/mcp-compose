# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""Check that an installed mcp-compose wheel serves its packaged UI at /ui.

Run it from outside the source checkout, so the installed package is imported
and no ./ui/dist from the working directory is picked up.
"""

from pathlib import Path

from fastapi.testclient import TestClient

import mcp_compose
from mcp_compose.api.app import create_app, find_ui_dist_path

package_dir = Path(mcp_compose.__file__).resolve().parent
ui_dist = find_ui_dist_path()
print(f"mcp-compose {mcp_compose.__version__} from {package_dir}")
print(f"UI resolved to {ui_dist}")
assert ui_dist == package_dir / "ui" / "dist", "the packaged UI was not picked up"

client = TestClient(create_app())
for path in ("/ui", "/ui/", "/ui/servers"):
    response = client.get(path)
    assert response.status_code == 200, f"GET {path} -> {response.status_code}"
    assert b'<div id="root">' in response.content, f"GET {path} did not return the UI"
print("UI served at /ui")
