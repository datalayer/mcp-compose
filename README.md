<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# ✨ MCP Compose

[![PyPI - Version](https://img.shields.io/pypi/v/mcp-compose)](https://pypi.org/project/mcp-compose)
[![Github Actions Status](https://github.com/datalayer/mcp-compose/workflows/Build/badge.svg)](https://github.com/datalayer/mcp-compose/actions/workflows/build.yml)
[![Test Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)](https://github.com/datalayer/mcp-compose)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](Dockerfile)

> **Similar to Docker Compose - Orchestrate Model Context Protocol (MCP) servers with management capabilities, REST API, and Web UI.**

## 🎯 Overview

MCP Compose is a comprehensive solution for managing multiple MCP servers in a unified environment. It provides automatic discovery, intelligent composition, protocol translation, real-time monitoring, and a beautiful web interface for managing your MCP infrastructure.

### Key Capabilities

🔧 **Multi-Server Management** - Start, stop, and monitor multiple MCP servers from a single interface  
🌐 **REST API** - Complete REST API with 32 endpoints for programmatic control  
🎨 **Modern Web UI** - Beautiful React-based interface with real-time updates  
🔄 **Protocol Translation** - Seamlessly translate between STDIO and SSE protocols  
📊 **Real-Time Monitoring** - Live metrics, logs, and health checks  
🔐 **Security First** - Token authentication, CORS support, rate limiting  
📦 **Easy Deployment** - Docker support with docker-compose orchestration  
🧪 **Well Tested** - 95% test coverage with 265+ tests  
📚 **Comprehensive Docs** - Full API reference, user guide, and deployment guide

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI
pip install mcp-compose

# Or install from source
git clone https://github.com/datalayer/mcp-compose.git
cd mcp-compose
pip install -e .
```

### Using Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/datalayer/mcp-compose.git
cd mcp-compose

# Start with docker-compose (includes Prometheus & Grafana)
docker-compose up -d

# Access the Web UI
open http://localhost:8000
```

### Using CLI

```bash
# Start the server with Web UI
mcp-composer serve --config examples/mcp_compose.toml

# Access Web UI at http://localhost:8000
# Access API at http://localhost:8000/api/v1
# Access API docs at http://localhost:8000/docs

# Discover available MCP servers
mcp-composer discover

# Invoke a tool
mcp-composer invoke-tool calculator:add '{"a": 5, "b": 3}'
```

### Using Python API

```python
from mcp_compose import MCPServerComposer

# Create composer and start servers
composer = MCPServerComposer()
composer.load_config("config.toml")

# Start all servers
for server in composer.servers.values():
    await composer.start_server(server.name)

# List available tools
tools = await composer.list_tools()
print(f"Available tools: {[t.name for t in tools]}")

# Invoke a tool
result = await composer.invoke_tool("calculator:add", {"a": 5, "b": 3})
print(f"Result: {result}")
```

## 🎨 Web UI Features

The modern web interface provides:

- **📊 Dashboard** - Overview of all servers, tools, and system metrics
- **🖥️ Server Management** - Start, stop, restart servers with real-time status
- **🔧 Tool Browser** - Search and invoke tools with interactive forms
- **⚙️ Configuration Editor** - Edit and validate configuration files
- **📋 Log Viewer** - Real-time log streaming with filtering
- **📈 Metrics Dashboard** - Charts for CPU, memory, and request metrics
- **🔄 Translator Management** - Create and manage protocol translators
- **⚙️ Settings** - Configure theme, API settings, and preferences

## 📖 Documentation

- **[User Guide](docs/USER_GUIDE.md)** - Complete guide for using MCP Compose
- **[API Reference](docs/API_REFERENCE.md)** - Full REST API and Python API documentation
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment with Docker & Kubernetes
- **[Architecture](ARCHITECTURE.md)** - System architecture and design decisions

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Web UI (React)                       │
│  Dashboard │ Servers │ Tools │ Config │ Logs │ Metrics      │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/WebSocket
┌──────────────────────────┴──────────────────────────────────┐
│                    REST API (FastAPI)                        │
│  /servers │ /tools │ /config │ /translators │ /metrics      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                 MCP Compose Core                     │
│  Server Manager │ Tool Broker │ Config Manager              │
└───────┬──────────┬──────────┬──────────┬────────────────────┘
        │          │          │          │
   ┌────┴───┐ ┌───┴────┐ ┌───┴────┐ ┌───┴────┐
   │ Server │ │ Server │ │ Server │ │ Server │
   │   A    │ │   B    │ │   C    │ │   D    │
   └────────┘ └────────┘ └────────┘ └────────┘
```

## ✨ Core Features

### Server Management

## ✨ Core Features

### Server Management

- **Multi-Server Orchestration** - Run multiple MCP servers simultaneously
- **Lifecycle Management** - Start, stop, restart, and monitor server health
- **Auto-restart** - Automatically restart failed servers
- **Environment Isolation** - Each server runs in its own isolated environment
- **Configuration Hot-Reload** - Update configuration without restarting

### Tool & Prompt Composition

- **Automatic Discovery** - Find tools and prompts from all running servers
- **Intelligent Composition** - Combine capabilities from multiple sources
- **Conflict Resolution** - Handle naming conflicts with prefix/suffix/override strategies
- **Dynamic Loading** - Tools appear as servers start
- **Unified Interface** - Single API to access all tools

### Protocol Translation

- **STDIO ↔ SSE** - Translate between different transport protocols
- **Transparent Bridging** - No changes needed to existing servers
- **Bidirectional** - Full request/response support
- **Multiple Translators** - Run many translators simultaneously

### Monitoring & Observability

- **Real-Time Metrics** - CPU, memory, request rates, and latency
- **Structured Logging** - JSON logs with correlation IDs
- **Health Checks** - Continuous monitoring of server health
- **Prometheus Integration** - Export metrics for Prometheus
- **WebSocket Streaming** - Live log and metric updates

### Security

- **Token Authentication** - Secure API access
- **CORS Support** - Configurable origin policies
- **Rate Limiting** - Prevent abuse
- **Input Validation** - Comprehensive request validation
- **Non-root Containers** - Run as unprivileged user

## 🛠️ Configuration

Create `mcp_compose.toml`:

```toml
[composer]
name = "my-composer"
conflict_resolution = "prefix"

[[servers]]
name = "filesystem"
command = "python"
args = ["-m", "mcp_server_filesystem", "/data"]
transport = "stdio"
auto_start = true

[[servers]]
name = "calculator"
command = "python"
args = ["-m", "mcp_server_calculator"]
transport = "stdio"
auto_start = true

[logging]
level = "INFO"
format = "json"

[security]
auth_enabled = true
cors_origins = ["http://localhost:3000"]
```

See [User Guide](docs/USER_GUIDE.md) for complete configuration options.

## 🔌 REST API

### Key Endpoints

```bash
# Health & Status
GET  /api/v1/health
GET  /api/v1/version
GET  /api/v1/status
GET  /api/v1/status/composition

# Server Management
GET  /api/v1/servers
POST /api/v1/servers/{id}/start
POST /api/v1/servers/{id}/stop
POST /api/v1/servers/{id}/restart

# Tool Management
GET  /api/v1/tools
POST /api/v1/tools/{name}/invoke

# Configuration
GET  /api/v1/config
PUT  /api/v1/config
POST /api/v1/config/validate
POST /api/v1/config/reload

# Translators
GET    /api/v1/translators
POST   /api/v1/translators
DELETE /api/v1/translators/{id}

# WebSocket
WS   /ws/logs
WS   /ws/metrics
```

See [API Reference](docs/API_REFERENCE.md) for complete documentation.

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test
pytest tests/test_composer.py -v

# Type checking
make type-check

# Linting
make lint
```

## 📦 Development

```bash
# Clone repository
git clone https://github.com/datalayer/mcp-compose.git
cd mcp-compose

# Install development dependencies
pip install -e ".[dev]"

# Install UI dependencies
cd ui
npm install
npm run dev

# Run tests
make test

# Build UI
make build-ui

# Run server
mcp-composer serve
```

## 🐳 Docker Deployment

### Quick Start

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Production Deployment

```bash
# Build with production settings
docker build -t mcp-composer:prod .

# Run with environment variables
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -e MCP_COMPOSER_AUTH_TOKEN=secret \
  --name mcp-composer \
  mcp-composer:prod
```

See [Deployment Guide](docs/DEPLOYMENT.md) for Kubernetes and production setup.

## 📚 Examples

### Git + File MCP Servers

A complete example demonstrating how to orchestrate Git and Filesystem MCP servers with anonymous access.

**Location:** [`examples/git-file/`](examples/git-file/)

**Features:**
- Git operations (status, log, diff, commit)
- Filesystem operations (read, write, list)
- Unified API with tool prefixing
- No authentication required
- Full Makefile for easy management

**Quick Start:**
```bash
cd examples/git-file
make install
make start
make open-ui
```

See the [Git-File Example README](examples/git-file/README.md) for complete documentation.

### OAuth Authentication Example

Production-ready example with GitHub OAuth2 authentication.

**Location:** [`references/oauth/`](references/oauth/)

**Features:**
- OAuth2 authentication flow
- JWT tokens
- Protected MCP server endpoints
- Pydantic AI agent integration

See the [MCP Auth Example README](references/oauth/README.md) for details.

## 🗂️ Resources

Configuration files and infrastructure resources are located in the [`resources/`](resources/) directory:

- `nginx.conf` - Nginx reverse proxy configuration
- `prometheus.yml` - Prometheus metrics collection
- `grafana/` - Grafana dashboards and datasources

## 📊 Project Status

### Phase 4: Complete ✅

**Week 13-16 Deliverables:**
- ✅ Modern React-based Web UI with 8 pages
- ✅ Real-time monitoring dashboard
- ✅ Log viewer with streaming
- ✅ Metrics visualization with Recharts
- ✅ Protocol translator management
- ✅ Settings and preferences
- ✅ Comprehensive documentation
- ✅ Docker deployment setup
- ✅ Production-ready configuration

**Test Coverage:** 95% (265+ tests)  
**Code Quality:** Type-checked with mypy  
**Lines of Code:** ~15,000 (including UI)

## 🗺️ Roadmap

### Completed
- ✅ Core composition engine
- ✅ CLI interface
- ✅ REST API (32 endpoints)
- ✅ Web UI (8 pages)
- ✅ Real-time monitoring
- ✅ Protocol translation
- ✅ Docker deployment
- ✅ Comprehensive documentation

### Future Enhancements
- 🔄 Plugin system for custom extensions
- 🔄 GraphQL API support
- 🔄 Advanced caching strategies
- 🔄 Distributed deployment support
- 🔄 Enhanced analytics
- 🔄 CLI auto-completion

## 🤝 Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/mcp-compose.git

# Create feature branch
git checkout -b feature/amazing-feature

# Make changes and test
make test

# Commit and push
git commit -m "Add amazing feature"
git push origin feature/amazing-feature

# Create Pull Request
```

## 📄 License

BSD 3-Clause License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Built on [FastMCP](https://github.com/jlowin/fastmcp) framework
- Inspired by the Model Context Protocol specification
- UI built with React, TypeScript, and Recharts
- Special thanks to all contributors

## 📧 Support

- **Documentation**: [Full documentation](docs/)
- **Issues**: [GitHub Issues](https://github.com/datalayer/mcp-compose/issues)
- **Discussions**: [GitHub Discussions](https://github.com/datalayer/mcp-compose/discussions)
- **Sponsor**: [Become a sponsor](https://github.com/sponsors/datalayer)

---

Made with ❤️ by [Datalayer](https://datalayer.ai)
composer = MCPServerComposer(
    composed_server_name="unified-data-server",
    conflict_resolution=ConflictResolution.PREFIX
)

# Compose from current directory's pyproject.toml
unified_server = composer.compose_from_pyproject()

# Get detailed composition information
summary = composer.get_composition_summary()
print(f"Created server with {summary['total_tools']} tools")
```

#### Advanced Configuration

```python
from pathlib import Path
from mcp_compose import MCPServerComposer, ConflictResolution

# Specify custom pyproject.toml location
composer = MCPServerComposer(
    composed_server_name="my-server",
    conflict_resolution=ConflictResolution.SUFFIX
)

# Compose with filtering
unified_server = composer.compose_from_pyproject(
    pyproject_path=Path("custom/pyproject.toml"),
    include_servers=["jupyter-mcp-server", "earthdata-mcp-server"],
    exclude_servers=["deprecated-server"]
)

# Access composed tools and prompts
tools = composer.list_tools()
prompts = composer.list_prompts()
source_info = composer.get_source_info()

print(f"Tools: {', '.join(tools)}")
print(f"Sources: {', '.join(source_info.keys())}")
```

#### Discovery Only

```python
from mcp_compose import MCPServerDiscovery

# Discover MCP servers without composing
discovery = MCPServerDiscovery()
servers = discovery.discover_from_pyproject("pyproject.toml")

for name, info in servers.items():
    print(f"{name}: {len(info.tools)} tools, {len(info.prompts)} prompts")
```

## Configuration

### Conflict Resolution Strategies

When multiple servers provide tools or prompts with the same name, you can choose how to resolve conflicts:

- **PREFIX** (default): Add server name as prefix (`server1_tool_name`)
- **SUFFIX**: Add server name as suffix (`tool_name_server1`)
- **OVERRIDE**: Last server wins (overwrites previous)
- **IGNORE**: Skip conflicting items
- **ERROR**: Raise an error on conflicts

### Example Conflict Resolution

```python
# If two servers both have a "search" tool:
# PREFIX: jupyter_mcp_server_search, earthdata_mcp_server_search
# SUFFIX: search_jupyter_mcp_server, search_earthdata_mcp_server
# OVERRIDE: Only the last server's "search" tool is kept
```

## Real-World Examples

### Data Science Workflow

Create a unified MCP server combining Jupyter notebook capabilities with Earth science data access:

```toml
# pyproject.toml
[project]
dependencies = [
    "jupyter-mcp-server>=1.0.0",
    "earthdata-mcp-server>=0.1.0",
    "weather-mcp-server>=2.0.0"
]
```

```bash
# Discover available tools
python -m mcp_compose discover

# Create unified server for data science workflow
python -m mcp_compose compose \
  --name "data-science-server" \
  --conflict-resolution prefix \
  --output unified_server.py
```

This creates a server with tools like:
- `jupyter_create_notebook` - Create analysis notebooks
- `earthdata_search_datasets` - Find Earth science data
- `weather_get_forecast` - Access weather data
- Combined prompts for data analysis workflows

### Development Environment

Combine development tools and documentation servers:

```python
from mcp_compose import MCPServerComposer, ConflictResolution

composer = MCPServerComposer(
    composed_server_name="dev-environment",
    conflict_resolution=ConflictResolution.PREFIX
)

# Compose development-focused servers
dev_server = composer.compose_from_pyproject(
    include_servers=[
        "code-review-mcp-server",
        "documentation-mcp-server", 
        "testing-mcp-server"
    ]
)

# Access all development tools in one place
print("Available tools:", composer.list_tools())
```

### Custom Integration

```python
from mcp_compose import MCPServerComposer
from my_custom_server import MyMCPServer

# Create composer
composer = MCPServerComposer()

# Compose discovered servers
unified_server = composer.compose_from_pyproject()

# Add your custom server manually if needed
composer.add_server("custom", MyMCPServer())

# Get final composition summary
summary = composer.get_composition_summary()
print(f"Final server has {summary['total_tools']} tools from {summary['source_servers']} sources")
```

## Project Structure

When using MCP Compose, structure your project like this:

```
my-project/
├── pyproject.toml          # Define MCP server dependencies
├── src/
│   └── my_project/
│       ├── __init__.py
│       └── main.py         # Use composed server
├── composed_server.py      # Generated unified server (optional)
└── README.md
```

### Sample pyproject.toml

```toml
[project]
name = "my-data-project"
dependencies = [
    "jupyter-mcp-server>=1.0.0",
    "earthdata-mcp-server>=0.1.0",
    "fastmcp>=1.2.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "mcp-compose>=1.0.0"
]
```

## Error Handling

The library provides comprehensive error handling:

```python
from mcp_compose import MCPServerComposer, MCPComposerError, MCPDiscoveryError

try:
    composer = MCPServerComposer()
    server = composer.compose_from_pyproject()
except MCPDiscoveryError as e:
    print(f"Discovery failed: {e}")
    print(f"Search paths: {e.search_paths}")
except MCPComposerError as e:
    print(f"Composition failed: {e}")
    print(f"Server count: {e.server_count}")
```

## Troubleshooting

### Common Issues

1. **No MCP servers found**: Ensure your dependencies include packages with "mcp" in the name
2. **Import errors**: Check that MCP server packages are properly installed
3. **Naming conflicts**: Use appropriate conflict resolution strategy
4. **Missing tools**: Verify that server packages export an `app` variable

### Debug Mode

```bash
# Enable verbose logging
python -m mcp_compose discover --verbose

# Check specific package
python -c "
from mcp_compose import MCPServerDiscovery
discovery = MCPServerDiscovery()
result = discovery._analyze_mcp_server('your-package-name')
print(result)
"
```

```

## API Reference

### MCPServerComposer

Main class for composing MCP servers:

```python
MCPServerComposer(
    composed_server_name: str = "composed-mcp-server",
    conflict_resolution: ConflictResolution = ConflictResolution.PREFIX
)
```

**Methods:**
- `compose_from_pyproject(pyproject_path, include_servers, exclude_servers)` - Compose servers from dependencies
- `get_composition_summary()` - Get summary of composition results
- `list_tools()` - List all available tools
- `list_prompts()` - List all available prompts
- `get_source_info()` - Get mapping of tools/prompts to source servers

### MCPServerDiscovery

Class for discovering MCP servers:

```python
MCPServerDiscovery(mcp_server_patterns: List[str] = None)
```

**Methods:**
- `discover_from_pyproject(pyproject_path)` - Discover servers from pyproject.toml
- `get_package_version(dependency_spec)` - Extract version from dependency string

### ConflictResolution

Enum for conflict resolution strategies:
- `PREFIX` - Add server name as prefix
- `SUFFIX` - Add server name as suffix  
- `OVERRIDE` - Last server wins
- `IGNORE` - Skip conflicting items
- `ERROR` - Raise error on conflicts

## Requirements

- Python 3.8+
- FastMCP >= 1.2.0
- TOML parsing support

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes and add tests
4. Ensure all tests pass (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

## Support

- 📖 **Documentation**: Full API documentation and examples in this README
- 🐛 **Issues**: Report bugs and request features on [GitHub Issues](https://github.com/datalayer/mcp-compose/issues)
- 💬 **Discussions**: Join the conversation in [GitHub Discussions](https://github.com/datalayer/mcp-compose/discussions)

## Related Projects

- [FastMCP](https://github.com/modelcontextprotocol/python-sdk) - Python SDK for Model Context Protocol
- [MCP Specification](https://spec.modelcontextprotocol.io/) - Official MCP specification
- [Jupyter MCP Server](https://github.com/datalayer/jupyter-mcp-server) - MCP server for Jupyter functionality
- [Earthdata MCP Server](https://github.com/datalayer/earthdata-mcp-server) - MCP server for NASA Earthdata access

---

**Made with ❤️ by the Datalayer team**
- [Earthdata MCP Server](https://github.com/your-org/earthdata-mcp-server) - MCP server for NASA Earthdata

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/your-org/mcp-compose/issues)
- Documentation: [Full documentation](https://your-org.github.io/mcp-compose/)
- Community: [Join the discussion](https://github.com/your-org/mcp-compose/discussions)
