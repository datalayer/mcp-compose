# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""Custom build hook to ensure UI is built before packaging."""
import subprocess
import sys
from pathlib import Path
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Build hook to compile the UI before creating the Python package."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        """Build the UI before packaging."""
        import os

        ui_dir = Path(self.root) / "ui"
        dist_dir = ui_dir / "dist"
        
        # Allow skipping the UI build entirely via environment variable.
        # Useful in CI environments where Node.js/npm may not be available.
        if os.environ.get("MCP_COMPOSE_SKIP_UI_BUILD", "").lower() in ("1", "true", "yes"):
            print("⏭  Skipping UI build (MCP_COMPOSE_SKIP_UI_BUILD is set)", file=sys.stderr)
            return

        # Check if UI dist exists and has content
        if not dist_dir.exists() or not list(dist_dir.iterdir()):
            print("Building UI...", file=sys.stderr)
            
            # Check if node_modules exists, if not run npm install
            if not (ui_dir / "node_modules").exists():
                print("Installing UI dependencies...", file=sys.stderr)
                try:
                    subprocess.run(
                        ["npm", "install"],
                        cwd=ui_dir,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    print(f"✗ npm install failed with exit code {e.returncode}", file=sys.stderr)
                    print("Make sure Node.js and npm are installed and accessible", file=sys.stderr)
                    sys.exit(1)
                except FileNotFoundError:
                    print("⚠ npm not found, skipping UI build. The web UI will not be available.", file=sys.stderr)
                    return
            
            # Build the UI
            print("Running npm build...", file=sys.stderr)
            try:
                subprocess.run(
                    ["npm", "run", "build"],
                    cwd=ui_dir,
                    check=True,
                )
                print("✓ UI built successfully", file=sys.stderr)
            except subprocess.CalledProcessError as e:
                print(f"✗ npm build failed with exit code {e.returncode}", file=sys.stderr)
                sys.exit(1)
            except FileNotFoundError:
                print("⚠ npm not found, skipping UI build. The web UI will not be available.", file=sys.stderr)
                return
        else:
            print("✓ UI already built, skipping build step", file=sys.stderr)
