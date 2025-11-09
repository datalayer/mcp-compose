<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# Demo MCP Servers Example

This example demonstrates how to use MCP Server Composer to manage multiple MCP servers from a configuration file.

## 🎯 Overview

This configuration launches two simple Python MCP servers managed by the composer:

1. **Calculator Server** (`mcp1.py`) - Math operations (add, subtract, multiply, divide)
2. **Echo Server** (`mcp2.py`) - String operations (ping, echo, reverse, uppercase, lowercase, count_words)

Both servers run in **proxy mode** via STDIO transport and are managed by the MCP Server Composer.

## 📋 Features

- **Two Simple Servers**: Calculator and Echo servers with basic tools
- **Pure Python**: No external dependencies beyond FastMCP
- **Configuration-Based**: Define servers in `mcp_compose.toml`
- **Process Management**: Composer manages server lifecycles
- **STDIO Transport**: Standard input/output for MCP communication
- **SSE API**: Unified MCP server endpoint for client connections (coming soon)
- **AI Agent Support**: Connect pydantic-ai agents to the composed server (coming soon)
- **Easy Management**: Simple make commands to control everything

## 🚀 Quick Start

> **⚠️ Note**: The serve command currently starts the child MCP servers but does not yet expose a unified SSE endpoint. The composer architecture is being implemented to provide a unified MCP protocol server that proxies requests to the child servers. For now, the example demonstrates configuration-based process management.

### 1. Install Dependencies

```bash
make install
```

This will install:
- `mcp-compose` (the orchestrator)
- `fastmcp` (for the demo MCP servers)

The example includes two simple Python MCP servers:
- `mcp1.py` - Calculator tools (add, subtract, multiply, divide)
- `mcp2.py` - Echo tools (ping, echo, reverse, uppercase, lowercase, count_words)

### 2. Start the Composer

```bash
make start
```

The composer will:
- Read configuration from `mcp_compose.toml`
- Start both Calculator and Echo MCP servers as child processes
- Manage their lifecycles (coming soon: unified SSE endpoint)

### 3. Use the AI Agent (Coming Soon)

> **🚧 Work in Progress**: The agent integration requires the unified SSE endpoint to be implemented in the serve command. The agent.py file is ready and demonstrates the intended usage pattern.

```bash
# Install pydantic-ai
make install-agent

# Run the agent (requires SSE endpoint - coming soon!)
make agent
```

The agent is designed to:
- Connect to the MCP Server Composer via SSE
- Access tools from both Calculator and Echo servers through a unified interface
- Provide an interactive CLI powered by Anthropic Claude

Example interactions (once SSE endpoint is available):
- "What is 15 plus 27?"
- "Multiply 8 by 9"
- "Reverse the text 'hello world'"
- "Convert 'Hello World' to uppercase"
- "Count the words in 'The quick brown fox jumps'"

### 4. Stop the Composer

Press `Ctrl+C` in the terminal where the composer is running.

## � Features

- **Multiple Servers**: Git and Filesystem servers orchestrated together
- **Configuration-Based**: Define servers in `mcp_compose.toml`
- **Process Management**: Composer manages server lifecycles
- **STDIO Transport**: Standard input/output for MCP communication
- **Easy Management**: Simple make commands to control everything

## �🚀 Quick Start

### 1. Install Dependencies

```bash
make install
```

This will install:
- `mcp-compose` (the orchestrator)
- `mcp-server-git` (Git operations)
- `mcp-server-filesystem` (File operations)

### 2. Start the Composer

```bash
make start
```

The composer will:
- Read configuration from `mcp_compose.toml`
- Start both Git and Filesystem MCP servers
- Manage their processes
- Handle auto-restart if servers crash

### 3. Stop the Composer

Press `Ctrl+C` in the terminal where the composer is running.

## 📖 Usage Examples

### List Available Tools

```bash
# All tools
make list-tools

# Git tools only
make list-git

# Filesystem tools only
make list-fs
```

### Test Git Server

```bash
# Get commit log
make test-git

# Get git status
make test-git-status
```

### Test Filesystem Server

```bash
# List directory
make test-fs

# Read a file
make test-fs-read
```

### Manual API Calls

#### Git Operations

**Get commit log:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/git:log/invoke \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

**Get repository status:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/git:status/invoke \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Show diff:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/git:diff/invoke \
  -H "Content-Type: application/json" \
  -d '{"cached": false}'
```

#### Filesystem Operations

**List directory:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/filesystem:list_directory/invoke \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp"}'
```

**Read file:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/filesystem:read_file/invoke \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/myfile.txt"}'
```

**Write file:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/filesystem:write_file/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/tmp/test.txt",
    "content": "Hello from MCP!"
  }'
```

## 🎨 Web UI Features

Access the Web UI at http://localhost:8000

### Dashboard
- View active servers count
- See total available tools
- Monitor system health
- Quick navigation

### Server Management
- Start/stop individual servers
- View server status and uptime
- Monitor process IDs
- See restart counts

### Tool Browser
- Search and filter tools
- View tool schemas
- Invoke tools interactively
- See results in real-time

### Configuration Editor
- Edit server configuration
- Validate before applying
- Reload from file
- Live updates

### Log Viewer
- Real-time log streaming
- Filter by level and server
- Search log messages
- Download logs

### Metrics Dashboard
- Request rates
- Tool invocations
- Response latency
- System resources

## 🔧 Configuration

The configuration file `mcp_compose.toml` defines:

```toml
[composer]
name = "git-file-composer"
conflict_resolution = "prefix"  # Tools are prefixed: git:log, filesystem:read_file

[[servers]]
name = "git"
command = "uvx"
args = ["mcp-server-git", "--repository", "."]
transport = "stdio"
auto_start = true

[[servers]]
name = "filesystem"
command = "uvx"
args = ["mcp-server-filesystem", "/tmp"]
transport = "stdio"
auto_start = true
```

### Customization Options

**Change Git Repository:**
```toml
args = ["mcp-server-git", "--repository", "/path/to/your/repo"]
```

**Change Filesystem Root:**
```toml
args = ["mcp-server-filesystem", "/your/allowed/path"]
```

**Add Environment Variables:**
```toml
[servers.env]
GIT_AUTHOR_NAME = "Bot"
GIT_AUTHOR_EMAIL = "bot@example.com"
```

## 🛠️ Makefile Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make install` | Install dependencies |
| `make start` | Start composer (foreground) |
| `make start-bg` | Start composer (background) |
| `make stop` | Stop composer |
| `make restart` | Restart composer |
| `make status` | Check status |
| `make health` | Check health endpoint |
| `make logs` | View real-time logs |
| `make list-tools` | List all tools |
| `make list-git` | List Git tools |
| `make list-fs` | List Filesystem tools |
| `make test-git` | Test Git server |
| `make test-fs` | Test Filesystem server |
| `make test-all` | Run all tests |
| `make open-ui` | Open Web UI |
| `make examples` | Show API examples |
| `make clean` | Clean up files |

## 🔧 Available Tools

### Git Server Tools

The Git MCP server typically provides:

- `git:status` - Get repository status
- `git:log` - Get commit history
- `git:diff` - Show changes
- `git:commit` - Create commits
- `git:add` - Stage files
- `git:branch` - Manage branches
- `git:checkout` - Switch branches
- And more...

### Filesystem Server Tools

The Filesystem MCP server provides:

- `filesystem:read_file` - Read file contents
- `filesystem:write_file` - Write to file
- `filesystem:list_directory` - List directory contents
- `filesystem:create_directory` - Create directories
- `filesystem:delete_file` - Delete files
- `filesystem:move_file` - Move/rename files
- And more...

Run `make list-tools` to see the exact tools available with your versions.

## 📊 Monitoring

### Prometheus Metrics

Metrics are exposed at: http://localhost:8000/metrics

Example metrics:
- `mcp_http_requests_total` - Total HTTP requests
- `mcp_tool_invocations_total` - Tool invocation count
- `mcp_request_duration_seconds` - Request latency

### Health Checks

```bash
# Simple health check
curl http://localhost:8000/api/v1/health

# Detailed status
curl http://localhost:8000/api/v1/status
```

## 🐛 Troubleshooting

### Server Won't Start

1. Check if port 8000 is available:
   ```bash
   lsof -i :8000
   ```

2. View logs:
   ```bash
   make logs
   ```

3. Check server status:
   ```bash
   make status
   ```

### Tools Not Found

1. Verify servers are running:
   ```bash
   curl http://localhost:8000/api/v1/servers
   ```

2. Restart servers:
   ```bash
   make restart
   ```

### Permission Errors (Filesystem)

The filesystem server is limited to `/tmp` by default. To access other directories, update the configuration:

```toml
args = ["mcp-server-filesystem", "/your/allowed/path"]
```

## 🔒 Security Notes

⚠️ **This example runs with NO AUTHENTICATION**

For production use:

1. **Enable authentication** in the config:
   ```toml
   [authentication]
   enabled = true
   providers = ["api_key"]
   
   [authentication.api_key]
   keys = ["your-secret-key"]
   ```

2. **Restrict filesystem access** to specific directories

3. **Use HTTPS** in production

4. **Enable CORS** only for trusted origins

5. **Add rate limiting** for public-facing deployments

See the [Security documentation](../../docs/DEPLOYMENT.md#security-hardening) for more details.

## 📚 Learn More

- **[User Guide](../../docs/USER_GUIDE.md)** - Complete feature documentation
- **[API Reference](../../docs/API_REFERENCE.md)** - REST API documentation  
- **[Deployment Guide](../../docs/DEPLOYMENT.md)** - Production deployment
- **[Architecture](../../ARCHITECTURE.md)** - System design

## 🤝 Contributing

Found an issue or want to improve this example? Please open an issue or PR!

## 📄 License

BSD 3-Clause License - see [LICENSE](../../LICENSE)

---

**Made with ❤️ by [Datalayer](https://datalayer.ai)**
