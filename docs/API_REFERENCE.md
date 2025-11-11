# MCP Compose - API Reference

## Table of Contents

1. [REST API Overview](#rest-api-overview)
2. [Authentication](#authentication)
3. [Endpoints](#endpoints)
4. [Python API](#python-api)
5. [WebSocket API](#websocket-api)
6. [Error Handling](#error-handling)

## REST API Overview

The MCP Compose provides a comprehensive REST API for programmatic control.

**Base URL:** `http://localhost:8000/api/v1`

**Content Type:** `application/json`

**Response Format:** JSON

### API Versioning

The API is versioned via the URL path (`/api/v1`). Breaking changes will increment the major version.

## Authentication

### Token Authentication (Optional)

When authentication is enabled, include the token in request headers:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/status
```

**Enable Authentication:**
```bash
export MCP_COMPOSER_AUTH_TOKEN=your-secret-token
mcp-composer serve
```

### API Keys (Future)

API key authentication will be supported in future versions.

## Endpoints

### Health & Status

#### GET /health

Health check endpoint for monitoring.

**Request:**
```bash
curl http://localhost:8000/api/v1/health
```

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": "2h 15m 30s"
}
```

#### GET /version

Get application version information.

**Request:**
```bash
curl http://localhost:8000/api/v1/version
```

**Response:** `200 OK`
```json
{
  "version": "1.0.0",
  "api_version": "v1",
  "python_version": "3.10.12"
}
```

#### GET /status

Get detailed system status.

**Request:**
```bash
curl http://localhost:8000/api/v1/status
```

**Response:** `200 OK`
```json
{
  "composer_name": "my-composer",
  "servers_total": 3,
  "servers_running": 2,
  "servers_stopped": 1,
  "tools_total": 45,
  "prompts_total": 5,
  "resources_total": 3,
  "uptime": "2h 15m 30s",
  "platform": "Linux-5.15.0-86-generic-x86_64-with-glibc2.35"
}
```

#### GET /status/composition

Get detailed composition information.

**Request:**
```bash
curl http://localhost:8000/api/v1/status/composition
```

**Response:** `200 OK`
```json
{
  "servers": [
    {
      "name": "filesystem",
      "state": "running",
      "tools_count": 8,
      "prompts_count": 2,
      "resources_count": 1
    },
    {
      "name": "calculator",
      "state": "running",
      "tools_count": 4,
      "prompts_count": 0,
      "resources_count": 0
    }
  ],
  "conflict_resolution": "prefix",
  "total_tools": 12,
  "total_prompts": 2,
  "total_resources": 1
}
```

#### GET /status/metrics

Get performance metrics.

**Request:**
```bash
curl http://localhost:8000/api/v1/status/metrics
```

**Response:** `200 OK`
```json
{
  "http_requests_total": 1234,
  "tool_invocations_total": 567,
  "auth_attempts_total": 0,
  "server_restarts_total": 2,
  "avg_request_duration_ms": 45.3,
  "timestamp": "2025-10-13T10:30:00Z"
}
```

### Server Management

#### GET /servers

List all configured servers.

**Request:**
```bash
curl http://localhost:8000/api/v1/servers
```

**Response:** `200 OK`
```json
{
  "servers": [
    {
      "id": "filesystem",
      "name": "filesystem",
      "command": "python",
      "args": ["-m", "mcp_server_filesystem", "/data"],
      "env": {},
      "transport": "stdio",
      "state": "running",
      "pid": 12345,
      "uptime": 7530,
      "restart_count": 0
    },
    {
      "id": "calculator",
      "name": "calculator",
      "command": "python",
      "args": ["-m", "mcp_server_calculator"],
      "env": {},
      "transport": "stdio",
      "state": "stopped",
      "pid": null,
      "uptime": null,
      "restart_count": 0
    }
  ]
}
```

#### GET /servers/{server_id}

Get details for a specific server.

**Request:**
```bash
curl http://localhost:8000/api/v1/servers/filesystem
```

**Response:** `200 OK`
```json
{
  "id": "filesystem",
  "name": "filesystem",
  "command": "python",
  "args": ["-m", "mcp_server_filesystem", "/data"],
  "env": {},
  "transport": "stdio",
  "state": "running",
  "pid": 12345,
  "uptime": 7530,
  "restart_count": 0,
  "tools": ["read_file", "write_file", "list_directory"],
  "prompts": ["analyze_file"],
  "resources": ["file_system"]
}
```

**Error:** `404 Not Found`
```json
{
  "detail": "Server not found: nonexistent"
}
```

#### POST /servers/{server_id}/start

Start a server.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/servers/filesystem/start
```

**Response:** `200 OK`
```json
{
  "message": "Server started successfully",
  "server_id": "filesystem",
  "pid": 12345
}
```

**Error:** `400 Bad Request`
```json
{
  "detail": "Server is already running"
}
```

#### POST /servers/{server_id}/stop

Stop a server.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/servers/filesystem/stop
```

**Response:** `200 OK`
```json
{
  "message": "Server stopped successfully",
  "server_id": "filesystem"
}
```

#### POST /servers/{server_id}/restart

Restart a server.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/servers/filesystem/restart
```

**Response:** `200 OK`
```json
{
  "message": "Server restarted successfully",
  "server_id": "filesystem",
  "pid": 12346
}
```

### Tool Management

#### GET /tools

List all available tools.

**Query Parameters:**
- `server` (optional): Filter by server name
- `search` (optional): Search in name/description
- `limit` (optional): Max results (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Request:**
```bash
# All tools
curl http://localhost:8000/api/v1/tools

# Filter by server
curl "http://localhost:8000/api/v1/tools?server=filesystem"

# Search
curl "http://localhost:8000/api/v1/tools?search=read"

# Pagination
curl "http://localhost:8000/api/v1/tools?limit=10&offset=0"
```

**Response:** `200 OK`
```json
{
  "tools": [
    {
      "name": "filesystem:read_file",
      "description": "Read contents of a file",
      "input_schema": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "Path to file"
          }
        },
        "required": ["path"]
      },
      "server": "filesystem"
    },
    {
      "name": "calculator:add",
      "description": "Add two numbers",
      "input_schema": {
        "type": "object",
        "properties": {
          "a": {"type": "number"},
          "b": {"type": "number"}
        },
        "required": ["a", "b"]
      },
      "server": "calculator"
    }
  ],
  "total": 2,
  "limit": 100,
  "offset": 0
}
```

#### GET /tools/{tool_name}

Get details for a specific tool.

**Request:**
```bash
curl http://localhost:8000/api/v1/tools/calculator:add
```

**Response:** `200 OK`
```json
{
  "name": "calculator:add",
  "description": "Add two numbers",
  "input_schema": {
    "type": "object",
    "properties": {
      "a": {"type": "number", "description": "First number"},
      "b": {"type": "number", "description": "Second number"}
    },
    "required": ["a", "b"]
  },
  "server": "calculator",
  "examples": [
    {
      "input": {"a": 5, "b": 3},
      "output": {"result": 8}
    }
  ]
}
```

#### POST /tools/{tool_name}/invoke

Invoke a tool.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/calculator:add/invoke \
  -H "Content-Type: application/json" \
  -d '{"a": 5, "b": 3}'
```

**Response:** `200 OK`
```json
{
  "result": {
    "sum": 8
  },
  "execution_time_ms": 12.5
}
```

**Error:** `400 Bad Request`
```json
{
  "detail": "Validation error: Missing required field 'a'"
}
```

**Error:** `500 Internal Server Error`
```json
{
  "detail": "Tool execution failed: Division by zero"
}
```

### Prompt Management

#### GET /prompts

List all available prompts.

**Request:**
```bash
curl http://localhost:8000/api/v1/prompts
```

**Response:** `200 OK`
```json
{
  "prompts": [
    {
      "name": "filesystem:analyze_file",
      "description": "Analyze a file and provide insights",
      "arguments": [
        {
          "name": "path",
          "description": "Path to file",
          "required": true
        }
      ],
      "server": "filesystem"
    }
  ],
  "total": 1
}
```

#### GET /prompts/{prompt_name}

Get details for a specific prompt.

**Request:**
```bash
curl http://localhost:8000/api/v1/prompts/filesystem:analyze_file
```

**Response:** `200 OK`
```json
{
  "name": "filesystem:analyze_file",
  "description": "Analyze a file and provide insights",
  "arguments": [
    {
      "name": "path",
      "description": "Path to file to analyze",
      "required": true
    },
    {
      "name": "depth",
      "description": "Analysis depth (1-5)",
      "required": false
    }
  ],
  "template": "Analyze the file at {path} with depth {depth}",
  "server": "filesystem"
}
```

### Resource Management

#### GET /resources

List all available resources.

**Request:**
```bash
curl http://localhost:8000/api/v1/resources
```

**Response:** `200 OK`
```json
{
  "resources": [
    {
      "uri": "file:///data/file.txt",
      "name": "data file",
      "description": "A data file",
      "mime_type": "text/plain",
      "server": "filesystem"
    }
  ],
  "total": 1
}
```

#### GET /resources/{resource_uri}

Get a specific resource.

**Request:**
```bash
curl "http://localhost:8000/api/v1/resources/file%3A%2F%2F%2Fdata%2Ffile.txt"
```

**Response:** `200 OK`
```json
{
  "uri": "file:///data/file.txt",
  "name": "data file",
  "contents": "File contents here...",
  "mime_type": "text/plain",
  "server": "filesystem"
}
```

### Configuration Management

#### GET /config

Get current configuration.

**Request:**
```bash
curl http://localhost:8000/api/v1/config
```

**Response:** `200 OK`
```json
{
  "composer": {
    "name": "my-composer",
    "conflict_resolution": "prefix"
  },
  "servers": [
    {
      "name": "filesystem",
      "command": "python",
      "args": ["-m", "mcp_server_filesystem", "/data"],
      "transport": "stdio",
      "env": {},
      "auto_start": true
    }
  ]
}
```

#### PUT /config

Update configuration.

**Request:**
```bash
curl -X PUT http://localhost:8000/api/v1/config \
  -H "Content-Type: application/json" \
  -d @new_config.json
```

**Response:** `200 OK`
```json
{
  "message": "Configuration updated successfully",
  "servers_restarted": ["filesystem", "calculator"]
}
```

**Error:** `400 Bad Request`
```json
{
  "detail": "Invalid configuration: Missing required field 'name'"
}
```

#### POST /config/validate

Validate configuration without applying.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/config/validate \
  -H "Content-Type: application/json" \
  -d @config.json
```

**Response:** `200 OK`
```json
{
  "valid": true,
  "message": "Configuration is valid"
}
```

**Error:** `400 Bad Request`
```json
{
  "valid": false,
  "errors": [
    "Server 'filesystem': command not found",
    "Invalid conflict_resolution value"
  ]
}
```

#### POST /config/reload

Reload configuration from file.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/config/reload
```

**Response:** `200 OK`
```json
{
  "message": "Configuration reloaded successfully",
  "servers_restarted": ["filesystem"]
}
```

### Translator Management

#### GET /translators

List all translators.

**Request:**
```bash
curl http://localhost:8000/api/v1/translators
```

**Response:** `200 OK`
```json
{
  "translators": [
    {
      "name": "my-translator",
      "type": "stdio-to-sse",
      "sse_url": "http://localhost:3001/sse",
      "created_at": "2025-10-13T10:00:00Z"
    }
  ],
  "total": 1
}
```

#### POST /translators/stdio-to-sse

Create STDIO to SSE translator.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/translators/stdio-to-sse \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-translator",
    "sse_url": "http://localhost:3001/sse",
    "headers": {"Authorization": "Bearer token"},
    "timeout": 30
  }'
```

**Response:** `201 Created`
```json
{
  "message": "Translator created successfully",
  "name": "my-translator",
  "type": "stdio-to-sse"
}
```

#### POST /translators/sse-to-stdio

Create SSE to STDIO translator.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/translators/sse-to-stdio \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-translator",
    "command": "python",
    "args": ["-m", "mcp_server"],
    "env": {"DEBUG": "1"},
    "cwd": "/app"
  }'
```

**Response:** `201 Created`
```json
{
  "message": "Translator created successfully",
  "name": "my-translator",
  "type": "sse-to-stdio"
}
```

#### DELETE /translators/{name}

Delete a translator.

**Request:**
```bash
curl -X DELETE http://localhost:8000/api/v1/translators/my-translator
```

**Response:** `200 OK`
```json
{
  "message": "Translator deleted successfully",
  "name": "my-translator"
}
```

#### POST /translators/{name}/translate

Translate a message.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/translators/my-translator/translate \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/list", "params": {}}'
```

**Response:** `200 OK`
```json
{
  "result": {
    "tools": [...]
  }
}
```

## Python API

### MCPServerComposer Class

```python
from mcp_compose import MCPServerComposer, ConflictResolution

# Create composer from config
composer = MCPServerComposer.from_config("config.toml")

# Or create programmatically
composer = MCPServerComposer(
    composed_server_name="my-composer",
    conflict_resolution=ConflictResolution.PREFIX
)
```

### Server Management

```python
# Add server
await composer.add_server(
    name="filesystem",
    command="python",
    args=["-m", "mcp_server_filesystem", "/data"],
    transport="stdio"
)

# Start server
await composer.start_server("filesystem")

# Stop server
await composer.stop_server("filesystem")

# Restart server
await composer.restart_server("filesystem")

# Get server status
status = await composer.get_server_status("filesystem")
print(status.state, status.pid, status.uptime)
```

### Tool Operations

```python
# List tools
tools = await composer.list_tools()
for tool in tools:
    print(tool.name, tool.description)

# Get tool details
tool = await composer.get_tool("calculator:add")
print(tool.input_schema)

# Invoke tool
result = await composer.invoke_tool(
    "calculator:add",
    {"a": 5, "b": 3}
)
print(result)
```

### Prompt Operations

```python
# List prompts
prompts = await composer.list_prompts()

# Get prompt
prompt = await composer.get_prompt("filesystem:analyze_file")

# Get prompt with arguments
rendered = await composer.get_prompt(
    "filesystem:analyze_file",
    arguments={"path": "/data/file.txt"}
)
```

### Resource Operations

```python
# List resources
resources = await composer.list_resources()

# Read resource
content = await composer.read_resource("file:///data/file.txt")
print(content)
```

### Health Checks

```python
# Check health
health = await composer.health_check()
print(health.status, health.uptime)

# Get metrics
metrics = await composer.get_metrics()
print(metrics.http_requests_total)
```

## WebSocket API

### Real-time Log Streaming

Connect to WebSocket endpoint for real-time logs:

**Endpoint:** `ws://localhost:8000/ws/logs`

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/logs');

ws.onmessage = (event) => {
  const log = JSON.parse(event.data);
  console.log(`[${log.level}] ${log.message}`);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

**Message Format:**
```json
{
  "timestamp": "2025-10-13T10:30:00.123Z",
  "level": "INFO",
  "server": "filesystem",
  "message": "File read successfully"
}
```

### Real-time Metrics

**Endpoint:** `ws://localhost:8000/ws/metrics`

**Message Format:**
```json
{
  "timestamp": "2025-10-13T10:30:00Z",
  "http_requests_total": 1234,
  "tool_invocations_total": 567,
  "cpu_percent": 25.5,
  "memory_percent": 40.2
}
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

### Error Response Format

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong",
  "error_code": "OPTIONAL_ERROR_CODE",
  "timestamp": "2025-10-13T10:30:00Z"
}
```

### Common Error Codes

- `SERVER_NOT_FOUND`: Server doesn't exist
- `SERVER_ALREADY_RUNNING`: Attempt to start running server
- `SERVER_NOT_RUNNING`: Attempt to stop stopped server
- `TOOL_NOT_FOUND`: Tool doesn't exist
- `TOOL_EXECUTION_FAILED`: Tool execution error
- `VALIDATION_ERROR`: Input validation failed
- `CONFIG_INVALID`: Configuration validation failed
- `TIMEOUT_ERROR`: Operation timed out

### Retry Logic

Implement exponential backoff for transient errors:

```python
import time

def retry_request(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            time.sleep(wait_time)
```

---

## Rate Limiting

Currently no rate limiting is implemented. Future versions may include configurable rate limits.

## Deprecation Policy

- Deprecated endpoints will be marked in documentation
- Deprecated endpoints remain functional for at least one major version
- Migration guides provided for deprecated features

## Support

- Documentation: https://github.com/datalayer/mcp-compose
- Issues: https://github.com/datalayer/mcp-compose/issues
- API Updates: Check CHANGELOG.md
