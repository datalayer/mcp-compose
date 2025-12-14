# UI Example Configuration Summary

## Overview

The UI example has been configured to run MCP Compose with:
- **Web UI** on port **9456** (default)
- **Basic Authentication** (username/password)
- **REST API** on the same port
- **UI artifacts packaging** for Python builds

## Changes Made

### 1. Configuration Updates

#### Backend Configuration ([mcp_compose/config.py](../../mcp_compose/config.py))
- Added `port` field to `UiConfig` with default value `9456`
- Port is used when UI mode is 'separate', otherwise uses API port

#### Example Configuration ([examples/ui/mcp_compose.toml](mcp_compose.toml))
- Added authentication section with basic username/password
- Added UI configuration with port 9456
- Added API configuration with port 9456
- Default credentials: `admin` / `demo123`

#### Reference Configuration ([references/mcp_compose.toml](../../references/mcp_compose.toml))
- Updated to include UI port field with documentation

### 2. Build System Updates

#### PyProject.toml ([pyproject.toml](../../pyproject.toml))
Added Hatchling build configuration to package UI artifacts:

```toml
[tool.hatch.build.targets.wheel.force-include]
"ui/dist" = "mcp_compose/ui/dist"

[tool.hatch.build.targets.sdist]
include = [
    "mcp_compose",
    "ui/dist",
    "tests",
    "README.md",
    "LICENSE",
]
```

This ensures that when you run `python -m build`, the UI artifacts from `ui/dist/` are included in the distribution.

### 3. Makefile Enhancements

#### Main Makefile ([Makefile](../../Makefile))
Added targets for UI builds:
- `build-ui`: Build UI artifacts
- `build-all`: Build both UI and Python package
- `clean-ui`: Clean UI build artifacts

#### Example Makefile ([examples/ui/Makefile](Makefile))
Added targets:
- `install-ui`: Install UI dependencies
- `build-ui`: Build UI artifacts
- `start`: Start MCP Compose with UI on port 9456

### 4. Documentation

Created comprehensive documentation:
- [README.md](README.md): Example overview and quick start
- [CONFIGURATION.md](CONFIGURATION.md): Detailed configuration guide

## Usage Workflow

### Building for Distribution

```bash
# From project root
make build-ui     # Build UI artifacts
make build        # Build Python package (includes UI)
```

Or in one command:
```bash
make build-all
```

### Running the Example

```bash
cd examples/ui

# Install dependencies
make install install-ui

# Build UI
make build-ui

# Start the server
make start
```

Then access:
- **Web UI**: http://localhost:9456/ui
- **API Docs**: http://localhost:9456/docs
- Login with `admin` / `demo123`

### Development Workflow

1. **UI Development**:
   ```bash
   cd ui
   npm install
   npm run dev  # Development server with hot reload
   ```

2. **Backend Development**:
   ```bash
   # In another terminal
   cd examples/ui
   mcp-compose --config mcp_compose.toml
   ```

3. **Production Build**:
   ```bash
   cd ui
   npm run build  # Creates ui/dist/
   
   cd ..
   python -m build  # Packages everything including UI
   ```

## Port Configuration

The default port is **9456** and can be configured in multiple ways:

### Via Configuration File

```toml
[ui]
port = 9456

[api]
port = 9456
```

### Via Environment Variables

```bash
export MCP_API_PORT=9456
export MCP_UI_PORT=9456
```

### Via Command Line

```bash
mcp-compose --config mcp_compose.toml --port 9456
```

## Authentication Setup

### Default Credentials

```toml
[authentication]
enabled = true
providers = ["basic"]
default_provider = "basic"

[authentication.basic]
username = "admin"
password = "demo123"
```

### Using Environment Variables (Recommended)

```toml
[authentication.basic]
username = "${MCP_USERNAME}"
password = "${MCP_PASSWORD}"
```

Then:
```bash
export MCP_USERNAME=admin
export MCP_PASSWORD=your-secure-password
mcp-compose --config mcp_compose.toml
```

## Package Distribution

When you build the package with `python -m build`, the UI artifacts are automatically included:

```
dist/
├── mcp_compose-0.1.0.tar.gz       # Source distribution with UI
└── mcp_compose-0.1.0-py3-none-any.whl  # Wheel with UI
```

The UI files from `ui/dist/` are packaged at `mcp_compose/ui/dist/` inside the distribution.

## Deployment

### Local Development

```bash
pip install -e .
cd examples/ui
make start
```

### Production Installation

```bash
pip install mcp-compose
# UI artifacts are already included

# Create config
cat > mcp_compose.toml << EOF
[authentication.basic]
username = "admin"
password = "${MCP_PASSWORD}"

[ui]
enabled = true
port = 9456

[api]
port = 9456
EOF

# Start
mcp-compose --config mcp_compose.toml
```

### Docker Deployment

The Dockerfile already includes UI build steps. Build with:

```bash
docker build -t mcp-compose:latest .
docker run -p 9456:9456 -e MCP_USERNAME=admin -e MCP_PASSWORD=secret mcp-compose:latest
```

## Verification

After building, verify UI artifacts are included:

```bash
# Build the package
python -m build

# Check contents
unzip -l dist/mcp_compose-*.whl | grep ui/dist

# Or for source distribution
tar -tzf dist/mcp_compose-*.tar.gz | grep ui/dist
```

You should see files like:
```
mcp_compose/ui/dist/index.html
mcp_compose/ui/dist/assets/index-*.js
mcp_compose/ui/dist/assets/index-*.css
```

## Troubleshooting

### UI Not Found After Install

1. Rebuild UI: `cd ui && npm run build`
2. Rebuild package: `python -m build`
3. Reinstall: `pip install --force-reinstall dist/mcp_compose-*.whl`

### Port Already in Use

Change port in configuration:
```toml
[ui]
port = 9457

[api]
port = 9457
```

### Authentication Fails

1. Check credentials in config
2. Verify authentication is enabled
3. Check browser console for errors

## Next Steps

- Review [CONFIGURATION.md](CONFIGURATION.md) for detailed config options
- See [README.md](README.md) for usage examples
- Check [../../UI_MIGRATION_SUMMARY.md](../../UI_MIGRATION_SUMMARY.md) for UI architecture details
