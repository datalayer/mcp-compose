# MCP Server Composer - User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Web UI Usage](#web-ui-usage)
5. [Configuration](#configuration)
6. [Server Management](#server-management)
7. [Tool Usage](#tool-usage)
8. [Monitoring](#monitoring)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

## Introduction

MCP Server Composer is a comprehensive solution for managing and composing multiple Model Context Protocol (MCP) servers. It provides:

- **Unified Interface**: Single entry point for multiple MCP servers
- **Web UI**: Modern web interface for management and monitoring
- **REST API**: Full-featured API for programmatic control
- **Real-time Monitoring**: Live logs, metrics, and status updates
- **Protocol Translation**: Support for STDIO and SSE transports

### Who Should Use This?

- **Developers** building AI applications that need multiple MCP servers
- **Teams** managing MCP server infrastructure
- **Organizations** deploying production MCP services
- **Researchers** experimenting with MCP tool combinations

## Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager
- Node.js 18+ (for Web UI development)

### Install from PyPI

```bash
pip install mcp-compose
```

### Install from Source

```bash
git clone https://github.com/datalayer/mcp-compose.git
cd mcp-compose
pip install -e .
```

### Verify Installation

```bash
mcp-composer --version
```

## Quick Start

### 1. Create Configuration File

Create `mcp_compose.toml`:

```toml
[composer]
name = "my-composer"
conflict_resolution = "prefix"  # or "error", "suffix"

[[servers]]
name = "filesystem"
command = "python"
args = ["-m", "mcp_server_filesystem", "/path/to/directory"]
transport = "stdio"

[[servers]]
name = "calculator"
command = "python"
args = ["-m", "mcp_server_calculator"]
transport = "stdio"
```

### 2. Start the Composer

```bash
mcp-composer serve --config mcp_compose.toml
```

### 3. Access the Web UI

Open your browser to:
```
http://localhost:8000
```

### 4. Use via CLI

```bash
# List all available tools
mcp-composer list-tools

# Invoke a tool
mcp-composer invoke-tool calculator:add '{"a": 5, "b": 3}'
```

## Web UI Usage

The Web UI provides a complete management interface for your MCP servers.

### Dashboard

**Access:** `http://localhost:8000/`

The dashboard shows:
- Active server count
- Total tools available
- System health status
- API request statistics
- Quick navigation buttons

**Key Metrics:**
- **Active Servers**: Number of running servers / total configured
- **Total Tools**: Sum of all tools from all servers
- **System Health**: Overall health check status
- **API Requests**: Total HTTP requests processed

### Server Management

**Access:** `http://localhost:8000/servers`

#### View Servers

- See all configured servers in a card layout
- Color-coded status indicators:
  - 🟢 **Running**: Server is operational
  - ⚪ **Stopped**: Server is not running
  - 🔵 **Starting**: Server is initializing
  - 🔵 **Stopping**: Server is shutting down
  - 🔴 **Crashed**: Server encountered an error

#### Start/Stop Servers

1. Click the **Play** button (▶) to start a stopped server
2. Click the **Stop** button (■) to stop a running server
3. Click the **Restart** button (↻) to restart a server

#### Monitor Server Status

Each server card shows:
- Command and arguments
- Transport type (STDIO/SSE)
- Process ID (when running)
- Uptime (formatted as hours and minutes)
- Restart count

### Tool Browser

**Access:** `http://localhost:8000/tools`

#### Search and Filter Tools

1. **Search Bar**: Type to filter by tool name or description
2. **Server Filter**: Dropdown to show tools from specific server
3. **Combined Filtering**: Use both search and server filter together

#### View Tool Details

Click on any tool card to see:
- Full description
- Server source
- Input parameter schema
- Required vs optional parameters

#### Invoke Tools

1. Select a tool from the list
2. Fill in the required parameters
3. Click **Invoke Tool** button
4. View the result (success or error)

**Parameter Input:**
- Try entering JSON first for complex objects
- Falls back to string values if JSON parsing fails
- Required fields marked with red asterisk (*)

### Configuration Editor

**Access:** `http://localhost:8000/configuration`

#### Edit Configuration

1. Modify the JSON configuration in the textarea
2. Click **Validate** to check syntax and schema
3. Click **Save** to apply changes
4. Servers will restart automatically if needed

**Validation:**
- ✅ Green banner: Configuration is valid
- ❌ Red banner: Shows specific errors
- ℹ️ Blue banner: Unsaved changes present

#### Reload from File

Click **Reload** to discard changes and reload from disk.

**Warning:** This will restart servers with current disk configuration.

### Log Viewer

**Access:** `http://localhost:8000/logs`

#### View Logs

Real-time log streaming shows:
- Timestamp (local time)
- Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- Server name (if applicable)
- Log message

#### Filter Logs

**By Level:**
- All Levels
- Debug
- Info
- Warning
- Error
- Critical

**By Server:**
- All Servers
- Individual server selection

**By Search:**
- Type in search box to filter by message content
- Case-insensitive matching

#### Log Statistics

Four stat cards show:
- **Total Lines**: Number of log entries
- **Errors**: Count of ERROR and CRITICAL logs
- **Warnings**: Count of WARNING logs
- **Info**: Count of INFO logs

#### Manage Logs

- **Download**: Export logs to text file
- **Clear**: Remove all logs from view
- **Auto-scroll**: Toggle automatic scrolling to newest logs
- **Max Lines**: Set buffer size (100-5000 lines)

### Metrics Dashboard

**Access:** `http://localhost:8000/metrics`

#### Key Metrics

Four main metric cards:
1. **Total Requests**: HTTP requests with trend indicator
2. **Tool Invocations**: Tool calls with trend indicator
3. **Average Latency**: Response time in milliseconds
4. **Active Servers**: Running servers count

**Trend Indicators:**
- 📈 Green arrow up: Increasing
- 📉 Red arrow down: Decreasing
- Percentage change from previous reading

#### Charts

**Request Rate Over Time (Area Chart)**
- Shows HTTP request rate
- Blue gradient area
- Last 60 data points
- Auto-refreshes every 5 seconds

**Tool Invocations (Bar Chart)**
- Purple bars showing tool call frequency
- Last 20 data points
- Useful for understanding usage patterns

**Response Latency (Line Chart)**
- Yellow line showing response times
- Helps identify performance issues
- Measured in milliseconds

**System Resources (Multi-line Chart)**
- Green line: CPU usage percentage
- Orange line: Memory usage percentage
- Monitor resource consumption

#### Performance Summary

Three cards at bottom:
- **Average CPU Usage**: With progress bar
- **Average Memory Usage**: With progress bar
- **Uptime**: System running time

### Translator Management

**Access:** `http://localhost:8000/translators`

#### About Translators

Protocol translators enable cross-transport communication:

**STDIO → SSE**: Exposes STDIO servers via Server-Sent Events for web clients
**SSE → STDIO**: Connects to SSE servers using STDIO interface

#### Create Translator

1. Click **Add Translator** button
2. Select translator type:
   - **STDIO → SSE**: For exposing STDIO via HTTP
   - **SSE → STDIO**: For connecting to SSE endpoints
3. Fill in required fields:
   - Translator name (unique identifier)
   - SSE URL (for STDIO→SSE)
   - Command and args (for SSE→STDIO)
4. Click **Create**

#### Delete Translator

Click the trash icon (🗑️) on any translator card and confirm deletion.

### Settings

**Access:** `http://localhost:8000/settings`

#### Appearance

**Theme Selector:**
- Light mode
- Dark mode
- Applies immediately

#### API Configuration

**API Endpoint:**
- Base URL for backend API
- Default: `http://localhost:8000`

**Auto-refresh Interval:**
- How often to refresh data (1-60 seconds)
- Use slider to adjust
- Default: 5 seconds

#### Notifications

**Enable Notifications:**
- Browser notifications for important events
- Requires browser permission

**Enable Sounds:**
- Audio alerts for errors and warnings

#### Logs Configuration

**Maximum Log Lines:**
- Buffer size: 100 / 500 / 1,000 / 5,000 / 10,000
- Higher values use more memory

#### Advanced

**Clear Cache & Reload:**
- Clears all local storage
- Reloads application
- Use if experiencing issues

#### About

View application information:
- Version number
- License
- Documentation link

## Configuration

### Configuration File Format

The configuration file uses TOML format with two main sections:

#### Composer Section

```toml
[composer]
name = "my-unified-server"           # Composer instance name
conflict_resolution = "prefix"        # Strategy for name conflicts
```

**Conflict Resolution Strategies:**

- **`prefix`**: Add server name prefix (e.g., `filesystem:read_file`)
- **`suffix`**: Add server name suffix (e.g., `read_file:filesystem`)
- **`error`**: Fail if naming conflicts occur

#### Servers Section

```toml
[[servers]]
name = "filesystem"                   # Unique server identifier
command = "python"                    # Executable to run
args = ["-m", "mcp_server_filesystem", "/data"]  # Command arguments
transport = "stdio"                   # Transport type (stdio or sse)
env = { DEBUG = "1" }                # Optional environment variables
auto_start = true                    # Start automatically (default: true)
```

### Environment Variables

Configure via environment:

```bash
# API Configuration
export MCP_COMPOSER_HOST=0.0.0.0
export MCP_COMPOSER_PORT=8000

# Logging
export MCP_COMPOSER_LOG_LEVEL=INFO

# Authentication (if enabled)
export MCP_COMPOSER_AUTH_TOKEN=your-secret-token
```

### Advanced Configuration

```toml
[composer]
name = "production-composer"
conflict_resolution = "prefix"
max_tool_invocation_time = 30        # Timeout in seconds
enable_metrics = true                 # Enable Prometheus metrics
enable_health_checks = true          # Enable health endpoints

[[servers]]
name = "filesystem"
command = "python"
args = ["-m", "mcp_server_filesystem", "/data"]
transport = "stdio"
auto_start = true
restart_on_failure = true            # Auto-restart on crash
max_restarts = 3                     # Maximum restart attempts
restart_delay = 5                    # Seconds between restarts

[servers.env]
DEBUG = "0"
LOG_LEVEL = "INFO"
CACHE_DIR = "/tmp/cache"
```

## Server Management

### Starting Servers

**Via CLI:**
```bash
# Start all servers
mcp-composer start-all

# Start specific server
mcp-composer start-server filesystem
```

**Via Python:**
```python
from mcp_compose import MCPServerComposer

composer = MCPServerComposer.from_config("config.toml")
await composer.start_server("filesystem")
```

**Via REST API:**
```bash
curl -X POST http://localhost:8000/api/v1/servers/filesystem/start
```

### Stopping Servers

**Via CLI:**
```bash
# Stop all servers
mcp-composer stop-all

# Stop specific server
mcp-composer stop-server filesystem
```

**Via REST API:**
```bash
curl -X POST http://localhost:8000/api/v1/servers/filesystem/stop
```

### Restarting Servers

**Via CLI:**
```bash
mcp-composer restart-server filesystem
```

**Via REST API:**
```bash
curl -X POST http://localhost:8000/api/v1/servers/filesystem/restart
```

### Monitoring Server Health

**Via CLI:**
```bash
# Check overall health
mcp-composer health

# Get detailed status
mcp-composer status
```

**Via REST API:**
```bash
# Health check
curl http://localhost:8000/api/v1/health

# Detailed status
curl http://localhost:8000/api/v1/status
```

## Tool Usage

### Listing Tools

**Via CLI:**
```bash
# List all tools
mcp-composer list-tools

# List tools from specific server
mcp-composer list-tools --server filesystem

# Show detailed information
mcp-composer list-tools --verbose
```

**Via REST API:**
```bash
# All tools
curl http://localhost:8000/api/v1/tools

# Filter by server
curl http://localhost:8000/api/v1/tools?server=filesystem
```

### Invoking Tools

**Via CLI:**
```bash
# Simple invocation
mcp-composer invoke-tool calculator:add '{"a": 5, "b": 3}'

# With file input
mcp-composer invoke-tool filesystem:read_file @input.json

# Capture output
mcp-composer invoke-tool my-tool '{}' > output.json
```

**Via Python:**
```python
composer = MCPServerComposer.from_config("config.toml")

# Invoke tool
result = await composer.invoke_tool(
    "calculator:add",
    {"a": 5, "b": 3}
)
print(result)
```

**Via REST API:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/calculator:add/invoke \
  -H "Content-Type: application/json" \
  -d '{"a": 5, "b": 3}'
```

### Tool Discovery

Tools are automatically discovered from configured servers. Each tool has:

- **Name**: Unique identifier (with conflict resolution)
- **Description**: What the tool does
- **Input Schema**: JSON Schema for parameters
- **Server Source**: Which server provides it

## Monitoring

### Prometheus Metrics

Access metrics at: `http://localhost:8000/metrics`

**Available Metrics:**

- `mcp_http_requests_total`: Total HTTP requests
- `mcp_tool_invocations_total`: Total tool invocations
- `mcp_auth_attempts_total`: Authentication attempts
- `mcp_server_restarts_total`: Server restart count
- `mcp_request_duration_seconds`: Request latency histogram

**Example Query:**
```bash
curl http://localhost:8000/metrics | grep mcp_http_requests_total
```

### Health Checks

**Liveness:** `http://localhost:8000/api/v1/health`
**Readiness:** `http://localhost:8000/api/v1/status`

**Health Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": "2h 15m"
}
```

### Logging

Logs are written to stdout and available in Web UI.

**Log Levels:**
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages
- **ERROR**: Error conditions
- **CRITICAL**: Critical failures

**Configure Log Level:**
```bash
export MCP_COMPOSER_LOG_LEVEL=DEBUG
mcp-composer serve
```

## Troubleshooting

### Common Issues

#### Server Won't Start

**Symptoms:** Server status shows "crashed" or "stopped"

**Solutions:**
1. Check server logs in Web UI
2. Verify command and arguments are correct
3. Ensure server executable is in PATH
4. Check file permissions
5. Verify environment variables

**Debug:**
```bash
# Test server command manually
python -m mcp_server_filesystem /path/to/dir

# Check logs
mcp-composer logs --server filesystem
```

#### Tool Invocation Fails

**Symptoms:** Error when calling tool

**Solutions:**
1. Verify tool name (check for prefix/suffix)
2. Validate input parameters match schema
3. Check server is running
4. Review server logs for errors

**Debug:**
```bash
# Get tool details
mcp-composer describe-tool calculator:add

# Test with minimal input
mcp-composer invoke-tool calculator:add '{}'
```

#### Port Already in Use

**Symptoms:** Error: "Address already in use"

**Solutions:**
1. Change port: `mcp-composer serve --port 8001`
2. Kill existing process: `lsof -ti:8000 | xargs kill`
3. Use different configuration

#### Web UI Not Loading

**Symptoms:** Blank page or connection error

**Solutions:**
1. Verify API is running: `curl http://localhost:8000/api/v1/health`
2. Check browser console for errors
3. Clear browser cache
4. Try different browser
5. Check firewall settings

#### High Memory Usage

**Symptoms:** System becomes slow

**Solutions:**
1. Reduce max log lines in settings
2. Decrease refresh intervals
3. Stop unused servers
4. Check for memory leaks in servers

### Getting Help

**Documentation:** https://github.com/datalayer/mcp-compose

**Issues:** https://github.com/datalayer/mcp-compose/issues

**Community:** Join our discussions on GitHub

## Best Practices

### Configuration

✅ **DO:**
- Use descriptive server names
- Set reasonable timeouts
- Enable auto-restart for production
- Use environment variables for secrets
- Version control your configuration

❌ **DON'T:**
- Hardcode sensitive data
- Use conflicting server names
- Set very short timeouts
- Disable health checks in production

### Server Management

✅ **DO:**
- Monitor server health regularly
- Set up alerts for failures
- Test servers individually first
- Use log levels appropriately
- Implement graceful shutdown

❌ **DON'T:**
- Run too many servers simultaneously
- Ignore restart failures
- Disable logging in production
- Skip health checks

### Tool Usage

✅ **DO:**
- Validate input parameters
- Handle errors gracefully
- Set appropriate timeouts
- Log tool invocations
- Cache results when possible

❌ **DON'T:**
- Ignore error responses
- Use undefined tools
- Skip parameter validation
- Block on long-running operations

### Security

✅ **DO:**
- Enable authentication in production
- Use HTTPS in production
- Validate all inputs
- Limit exposed endpoints
- Regular security updates

❌ **DON'T:**
- Expose to public internet without auth
- Use default passwords
- Trust user input blindly
- Skip input sanitization

### Performance

✅ **DO:**
- Use appropriate refresh intervals
- Limit log buffer sizes
- Monitor resource usage
- Optimize tool implementations
- Use caching where appropriate

❌ **DON'T:**
- Refresh too frequently
- Keep unlimited logs in memory
- Run synchronous operations
- Ignore performance metrics

### Monitoring

✅ **DO:**
- Set up Prometheus monitoring
- Configure alerts
- Review metrics regularly
- Monitor error rates
- Track tool usage patterns

❌ **DON'T:**
- Ignore warning signs
- Disable metrics collection
- Skip log reviews
- Overlook trends

---

## Next Steps

- Read the [API Documentation](API_REFERENCE.md)
- Check out [Deployment Guide](DEPLOYMENT.md)
- Review [Examples](../examples/)
- Explore [Advanced Topics](ADVANCED.md)

## License

BSD 3-Clause License - see [LICENSE](../LICENSE) file
