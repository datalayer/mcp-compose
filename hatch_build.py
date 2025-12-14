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
        ui_dir = Path(self.root) / "ui"
        dist_dir = ui_dir / "dist"
        
        # Check if UI dist exists and has content
        if not dist_dir.exists() or not list(dist_dir.iterdir()):
            print("Building UI...", file=sys.stderr)
            
            # Check if node_modules exists, if not run npm install
            if not (ui_dir / "node_modules").exists():
                print("Installing UI dependencies...", file=sys.stderr)
                subprocess.run(
                    ["npm", "install"],
                    cwd=ui_dir,
                    check=True,
                    capture_output=True,
                )
            
            # Build the UI
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=ui_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            
            if result.returncode == 0:
                print("✓ UI built successfully", file=sys.stderr)
            else:
                print(f"✗ UI build failed: {result.stderr}", file=sys.stderr)
                sys.exit(1)
        else:
            print("✓ UI already built, skipping build step", file=sys.stderr)
