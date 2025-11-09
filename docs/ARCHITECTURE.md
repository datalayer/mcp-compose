<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# ✨ MCP Server Composer

[![PyPI - Version](https://img.shields.io/pypi/v/mcp-compose)](https://pypi.org/project/mcp-compose)

[![Github Actions Status](https://github.com/datalayer/mcp-compose/workflows/Build/badge.svg)](https://github.com/datalayer/mcp-compose/actions/workflows/build.yml)

# Architecture

The MCP Server Composer is a Python facade for multiple `Managed MCP Servers`.

The MCP Server Composer exposes all the tools of the managed MCP Servers as a single unified MCP Server, aggregating the tools, prompts, and resources.

## Overview

A `Managed MCP Server` can be:

- **`Embedded`**: Python packages that implement MCP servers using the Python MCP SDK. These are loaded in-process and configured via a manual list in `mcp_compose.toml`.
- **`Proxied`**: External MCP servers accessible via `STDIO` or `SSE (Server-Sent Events)`. The startup commands and configurations for these proxied servers are defined in `mcp_compose.toml`.

The supported exposed **transports** are the official MCP transports: `STDIO` and `SSE (Server-Sent Events)`.

## Component Architecture

```
┌───────────────────────────────────────────────────────────────┐
│              MCP Server Composer (Facade)                     │
├───────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │    Authn     │  │    Authz     │  │    Transport       │   │
│  │  Middleware  │  │  Middleware  │  │  Layer             │   │
│  │              │  │              │  │  (STDIO/SSE)       │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
├───────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │     Tool     │  │   Process    │  │    REST API        │   │
│  │   Manager    │  │   Manager    │  │    Server          │   │
│  │              │  │              │  │                    │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
├───────────────────────────────────────────────────────────────┤
│  Managed MCP Servers                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │  Embedded    │  │   Proxied    │  │    Proxied         │   │
│  │   Python     │  │   (STDIO)    │  │    (SSE)           │   │
│  │  Packages    │  │              │  │                    │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Web UI         │
                    │   (React)        │
                    └──────────────────┘
```

## Configuration

All configuration is managed through a single `mcp_compose.toml` file. The previous dependency on `pyproject.toml` is removed.

### Configuration Schema

```toml
# mcp_compose.toml

# ============================================================================
# Composer Settings
# ============================================================================
[composer]
name = "my-unified-server"
conflict_resolution = "prefix"  # prefix, suffix, ignore, error, override, custom
log_level = "INFO"
port = 8080  # For HTTP/SSE transport and REST API

# ============================================================================
# Transport Configuration
# ============================================================================
[transport]
stdio_enabled = true
sse_enabled = true       # Server-Sent Events for streaming
sse_path = "/sse"        # SSE endpoint path
sse_cors_enabled = true  # Enable CORS for SSE

# ============================================================================
# Authentication Configuration
# ============================================================================
[authentication]
enabled = true
providers = ["api_key", "jwt", "oauth2", "mtls"]  # Multiple providers supported
default_provider = "api_key"

# API Key Authentication
[authentication.api_key]
header_name = "X-API-Key"
# Keys can be environment variables or direct values
keys = ["${MCP_API_KEY_1}", "${MCP_API_KEY_2}"]

# JWT Authentication
[authentication.jwt]
secret = "${JWT_SECRET}"
algorithm = "HS256"
issuer = "mcp-composer"
audience = "mcp-clients"

# OAuth2/OIDC Authentication
[authentication.oauth2]
provider = "auth0"  # auth0, keycloak, custom
client_id = "${OAUTH_CLIENT_ID}"
client_secret = "${OAUTH_CLIENT_SECRET}"
discovery_url = "${OAUTH_DISCOVERY_URL}"

# Mutual TLS Authentication
[authentication.mtls]
ca_cert = "/path/to/ca.crt"
client_cert = "/path/to/client.crt"
client_key = "/path/to/client.key"

# ============================================================================
# Authorization Configuration
# ============================================================================
[authorization]
enabled = true
model = "rbac"  # rbac (Role-Based Access Control)

# Role Definitions
[[authorization.roles]]
name = "admin"
permissions = ["*"]  # All permissions

[[authorization.roles]]
name = "developer"
permissions = ["tools:*", "servers:read", "logs:read"]

[[authorization.roles]]
name = "user"
permissions = ["tools:execute", "tools:list"]

# Tool-Level Permissions (optional fine-grained control)
[authorization.tools]
"jupyter_notebook_create" = ["admin", "developer"]
"file_system_delete" = ["admin"]
"*" = ["admin", "developer", "user"]  # Default for unlisted tools

# Rate Limiting
[authorization.rate_limiting]
enabled = true
default_limit = 100  # requests per minute
per_role_limits = { admin = 1000, developer = 500, user = 100 }

# ============================================================================
# Embedded MCP Servers
# ============================================================================
[servers.embedded]
# Manual list of Python packages to load as embedded MCP servers
# These must be MCP servers built with the Python MCP SDK

[[servers.embedded.servers]]
name = "jupyter-mcp-server"
package = "jupyter_mcp_server"
enabled = true
# Optional: Tool name mappings for conflict resolution
tool_mappings = { "create" = "jupyter_create", "run" = "jupyter_run" }

[[servers.embedded.servers]]
name = "earthdata-mcp-server"
package = "earthdata_mcp_server"
enabled = true
version = ">=0.1.0"  # Optional version constraint

# ============================================================================
# Proxied STDIO MCP Servers
# ============================================================================
[[servers.proxied.stdio]]
name = "weather-server"
command = ["uvx", "mcp-server-weather"]
env = { WEATHER_API_KEY = "${WEATHER_API_KEY}" }
working_dir = "/opt/mcp-servers/weather"

# Restart Policy
restart_policy = "on-failure"  # never, on-failure, always
max_restarts = 3
restart_delay = 5  # seconds

# Health Checks
health_check_enabled = true
health_check_interval = 30  # seconds
health_check_timeout = 5     # seconds
health_check_method = "tool"  # tool, ping, custom
health_check_tool = "health"  # Tool to invoke for health check

# Resource Limits
resource_limits = { max_memory_mb = 512, max_cpu_percent = 50 }

# Logging
log_stdout = true
log_stderr = true
log_file = "/var/log/mcp-composer/weather-server.log"

[[servers.proxied.stdio]]
name = "filesystem-server"
command = ["node", "/path/to/mcp-server-filesystem/dist/index.js"]
env = { ALLOWED_PATHS = "/home/user/workspace" }
restart_policy = "always"

# ============================================================================
# Proxied SSE (Server-Sent Events) MCP Servers
# ============================================================================
[[servers.proxied.sse]]
name = "remote-analytics-server"
url = "https://analytics.example.com/mcp/sse"
auth_token = "${REMOTE_SERVER_TOKEN}"
timeout = 30  # seconds
retry_interval = 5  # seconds

# Connection Settings
keep_alive = true
reconnect_on_failure = true
max_reconnect_attempts = 10

# Health Checks
health_check_enabled = true
health_check_interval = 60
health_check_endpoint = "/health"

# Mode: proxy or translator
# - proxy: Forward requests as-is (reverse proxy mode)
# - translator: Translate between transport protocols
mode = "proxy"

[[servers.proxied.sse]]
name = "cloud-ml-server"
url = "https://ml.example.com/mcp/sse"
auth_type = "bearer"  # bearer, basic, custom
auth_token = "${ML_SERVER_TOKEN}"
mode = "translator"

# ============================================================================
# Tool Manager Configuration
# ============================================================================
[tool_manager]
# Global conflict resolution strategy
conflict_resolution = "prefix"  # prefix, suffix, ignore, error, override, custom

# Per-tool conflict resolution (overrides global)
[[tool_manager.tool_overrides]]
tool_pattern = "notebook_*"
resolution = "prefix"

[[tool_manager.tool_overrides]]
tool_pattern = "search_*"
resolution = "suffix"

# Custom naming template (when conflict_resolution = "custom")
[tool_manager.custom_template]
template = "{server_name}::{tool_name}"

# Tool aliasing (manual aliases)
[tool_manager.aliases]
"jupyter_create" = "create_notebook"
"fs_read" = "read_file"

# Tool versioning support
[tool_manager.versioning]
enabled = true
allow_multiple_versions = true
version_suffix_format = "_v{version}"

# ============================================================================
# REST API Configuration
# ============================================================================
[api]
enabled = true
path_prefix = "/api/v1"
host = "0.0.0.0"
port = 8080

# CORS Configuration
cors_enabled = true
cors_origins = ["http://localhost:3000", "https://app.example.com"]
cors_methods = ["GET", "POST", "PUT", "DELETE"]

# API Documentation
docs_enabled = true
docs_path = "/docs"
openapi_path = "/openapi.json"

# ============================================================================
# Web UI Configuration
# ============================================================================
[ui]
enabled = true
framework = "react"  # react, vue, svelte
mode = "embedded"    # embedded, separate
path = "/ui"
static_dir = "/var/www/mcp-composer/ui"

# UI Features
features = [
    "server_management",
    "tool_testing",
    "logs_viewing",
    "metrics_dashboard",
    "configuration_editor"
]

# ============================================================================
# Monitoring & Observability
# ============================================================================
[monitoring]
enabled = true

# Metrics
[monitoring.metrics]
enabled = true
provider = "prometheus"  # prometheus, statsd, custom
endpoint = "/metrics"
collection_interval = 15  # seconds

# Metrics to collect
collect = [
    "tool_invocation_count",
    "tool_invocation_duration",
    "tool_error_rate",
    "server_health_status",
    "process_cpu_usage",
    "process_memory_usage",
    "request_rate",
    "response_time"
]

# Logging
[monitoring.logging]
level = "INFO"
format = "json"  # json, text
output = "stdout"  # stdout, file, both
log_file = "/var/log/mcp-composer/composer.log"
rotation = "daily"  # daily, size
max_size_mb = 100
max_files = 7

# Log aggregation from managed processes
aggregate_managed_logs = true

# Tracing
[monitoring.tracing]
enabled = true
provider = "opentelemetry"  # opentelemetry, jaeger, zipkin
endpoint = "http://localhost:4317"
sample_rate = 1.0  # 0.0 to 1.0

# Health Checks
[monitoring.health]
endpoint = "/health"
detailed_endpoint = "/health/detailed"
```

## Core Components

### 1. Transport Layer

The Transport Layer handles client connections using official MCP transports:

#### STDIO Transport
- Standard input/output communication
- Suitable for CLI tools and local integrations
- Blocking, synchronous communication

#### SSE (Server-Sent Events) Transport
- HTTP-based streaming transport
- Enables web-based clients and remote access
- Non-blocking, asynchronous communication
- CORS support for web applications

Both transports can be enabled simultaneously, allowing clients to choose their preferred connection method.

### 2. Authentication Middleware

The Authentication (Authn) middleware validates client identity before processing requests.

#### Supported Methods:
1. **API Key**: Simple header-based authentication
2. **JWT (JSON Web Tokens)**: Stateless token-based authentication
3. **OAuth2/OIDC**: Delegated authorization with external providers
4. **Mutual TLS**: Certificate-based authentication

#### Flow:
```
Client Request → Authn Middleware → Validate Credentials → Set Auth Context → Proceed
                                          ↓
                                      Invalid
                                          ↓
                                   401 Unauthorized
```

Multiple authentication providers can be configured simultaneously with a fallback chain.

### 3. Authorization Middleware

The Authorization (Authz) middleware controls access to resources based on authenticated identity.

#### Features:
- **Role-Based Access Control (RBAC)**: Assign permissions via roles
- **Tool-Level Permissions**: Fine-grained control over tool execution
- **Rate Limiting**: Per-user and per-role request limits
- **Transport-Level & Execution-Level Enforcement**: Authorization checks at both connection and tool invocation stages

#### Authorization Flow:
```
Authenticated Request → Extract Roles → Check Permissions → Allow/Deny
                                             ↓
                                      Not Authorized
                                             ↓
                                      403 Forbidden
```

### 4. Tool Manager

The Tool Manager aggregates tools from all managed servers and resolves naming conflicts.

#### Responsibilities:
- **Discovery**: Enumerate tools, prompts, and resources from all managed servers
- **Conflict Detection**: Identify naming collisions across servers
- **Resolution**: Apply configured strategy to resolve conflicts
- **Mapping**: Maintain source server → tool mappings
- **Validation**: Ensure tool schemas are compatible
- **Versioning**: Support multiple versions of the same tool
- **Aliasing**: Dynamic and static tool name aliases

#### Conflict Resolution Strategies:

1. **Prefix**: `{server_name}_{tool_name}`
   ```
   jupyter_notebook_create
   earthdata_search_datasets
   ```

2. **Suffix**: `{tool_name}_{server_name}`
   ```
   notebook_create_jupyter
   search_datasets_earthdata
   ```

3. **Ignore**: Skip conflicting tools (log warning)
   - First registered tool wins
   - Subsequent duplicates are ignored

4. **Error**: Fail composition on conflict
   - Strict mode for explicit conflict resolution
   - Prevents accidental tool shadowing

5. **Override**: Last defined server wins
   - Allows intentional tool replacement
   - Useful for patching or extending tools

6. **Custom**: User-defined naming template
   ```
   template = "{server_name}::{tool_name}"
   result: jupyter::notebook_create
   ```

#### Per-Tool Resolution:
Different strategies can be applied to different tool patterns:
```toml
[[tool_manager.tool_overrides]]
tool_pattern = "notebook_*"
resolution = "prefix"

[[tool_manager.tool_overrides]]
tool_pattern = "search_*"
resolution = "suffix"
```

#### Tool Versioning:
When enabled, multiple versions of the same tool can coexist:
```
notebook_create_v1
notebook_create_v2
```

### 5. Process Manager

The Process Manager handles the lifecycle of Proxied MCP Servers.

#### Responsibilities:
- **Startup**: Launch proxied servers using configured commands
- **Monitoring**: Track process health via heartbeats/health checks
- **Restart**: Automatically restart failed processes based on restart policies
- **Shutdown**: Graceful termination with configurable timeout
- **Logging**: Aggregate stdout/stderr from managed processes
- **Resource Management**: CPU and memory limits per process
- **Stream Management**: Handle stdin/stdout communication for STDIO servers

#### Configuration Options:

**Restart Policies:**
- `never`: No automatic restart
- `on-failure`: Restart only on non-zero exit codes
- `always`: Always restart regardless of exit status

**Health Checks:**
- **Method**: `tool` (invoke specific tool), `ping` (simple connectivity), or `custom`
- **Interval**: Time between health check attempts
- **Timeout**: Maximum time to wait for health check response
- **Action**: Restart process on failed health checks

**Resource Limits:**
- `max_memory_mb`: Maximum memory in megabytes
- `max_cpu_percent`: Maximum CPU usage percentage
- Enforcement via OS-level controls (cgroups on Linux)

**Logging:**
- Capture stdout/stderr from managed processes
- Rotation and retention policies
- Centralized log aggregation

#### Process Lifecycle:
```
Start → Running → Health Check ┬→ Healthy → Continue
                               ├→ Unhealthy → Restart (based on policy)
                               └→ Crashed → Restart (if max_restarts not exceeded)
```

#### Monitoring Capabilities:
- **Real-time status**: Current state of each managed server
- **Resource usage**: CPU, memory, file descriptors
- **Uptime tracking**: Start time, restart count, total uptime
- **Error tracking**: Recent errors and crash logs
- **Performance metrics**: Response times, request counts

### 6. REST API Server

The REST API provides programmatic access to composer functionality.

#### Management Endpoints:

```
GET    /api/v1/servers              List all managed servers
GET    /api/v1/servers/{id}         Get server details
POST   /api/v1/servers/{id}/start   Start a server
POST   /api/v1/servers/{id}/stop    Stop a server
POST   /api/v1/servers/{id}/restart Restart a server
DELETE /api/v1/servers/{id}         Remove a server (stops if running)
GET    /api/v1/servers/{id}/logs    Stream server logs (SSE)
GET    /api/v1/servers/{id}/metrics Get server metrics
```

#### Tool Endpoints:

```
GET    /api/v1/tools                List all available tools
GET    /api/v1/tools/{name}         Get tool schema
POST   /api/v1/tools/{name}/invoke  Invoke a tool
GET    /api/v1/prompts              List all prompts
GET    /api/v1/prompts/{name}       Get prompt details
GET    /api/v1/resources            List all resources
GET    /api/v1/resources/{uri}      Get resource content
```

#### Configuration Endpoints:

```
GET    /api/v1/config               Get current configuration
PUT    /api/v1/config               Update configuration (requires restart)
POST   /api/v1/config/validate      Validate configuration without applying
POST   /api/v1/config/reload        Reload configuration
```

#### Status Endpoints:

```
GET    /api/v1/health               Health check (simple)
GET    /api/v1/health/detailed      Detailed health status
GET    /api/v1/metrics              Prometheus-compatible metrics
GET    /api/v1/composition          Composition summary
GET    /api/v1/version              Version information
```

#### Authentication & Authorization:
All endpoints require authentication when enabled. Role-based permissions control access:
- `admin`: Full access to all endpoints
- `developer`: Read access + tool execution
- `user`: Limited to tool listing and execution

### 7. Web UI

A comprehensive web-based user interface for managing and monitoring the composer.

#### Framework:
- **Primary**: React (with TypeScript)
- **Alternative**: Vue, Svelte (configurable)

#### Deployment Modes:
1. **Embedded**: Served directly by the composer (default)
   - Static files bundled with Python package
   - Accessible at `/ui` path
   - Simplifies deployment

2. **Separate**: Independent web application
   - Communicates via REST API
   - Allows independent scaling
   - Custom hosting options

#### Features:

**1. Server Management**
- View list of all managed servers (embedded + proxied)
- Start/stop/restart servers
- Add/remove/configure servers
- View server details and status
- Real-time status updates

**2. Tool Testing**
- Interactive tool explorer
- Tool schema viewer
- Tool execution interface
- Request/response inspector
- Parameter validation
- Result visualization

**3. Logs Viewing**
- Real-time log streaming
- Filter by server, level, timestamp
- Search and highlight
- Log export (JSON, CSV, text)
- Tail mode for following logs

**4. Metrics Dashboard**
- Real-time metrics visualization
- Tool invocation statistics
- Server health status
- Resource usage graphs (CPU, memory)
- Request rate and latency
- Error rate tracking
- Custom metric queries

**5. Configuration Editor**
- Visual TOML editor with validation
- Configuration diff viewer
- Apply and reload configuration
- Configuration history/versioning
- Import/export configurations

**6. Additional Features**
- User authentication and session management
- Role-based UI elements (show/hide based on permissions)
- Dark/light theme toggle
- Responsive design for mobile access
- WebSocket support for real-time updates
- Notification system for events

## Security Architecture

### Authentication Flow:
```
1. Client connects via STDIO or SSE
2. Client provides credentials (API key, JWT, etc.)
3. Authn middleware validates credentials against configured provider
4. On success: Set authenticated context with user identity and roles
5. On failure: Return 401 Unauthorized and close connection
```

### Authorization Flow:
```
1. After authentication, extract user roles and permissions
2. Client invokes tool with parameters
3. Authz middleware checks:
   - Does user have permission to execute this tool?
   - Has user exceeded rate limits?
   - Is tool execution allowed at this time?
4. If authorized: Execute tool and return result
5. If not authorized: Return 403 Forbidden
```

### Multi-Provider Support:
Authentication providers can be chained with fallback logic:
```
Try API Key → Try JWT → Try OAuth2 → Try mTLS → Fail
```

### Authorization Models:

#### RBAC (Role-Based Access Control):
```toml
[[authorization.roles]]
name = "admin"
permissions = ["*"]

[[authorization.roles]]
name = "developer"
permissions = ["tools:*", "servers:read"]

[[authorization.roles]]
name = "user"
permissions = ["tools:execute:jupyter_*"]
```

#### Permission Format:
```
<resource>:<action>:<specific>
tools:execute:*          # All tools
tools:execute:jupyter_*  # Tools matching pattern
servers:restart:weather-server  # Specific server
```

### Rate Limiting:
Protects against abuse and ensures fair resource allocation:
- Per-user limits
- Per-role limits
- Per-tool limits (optional)
- Token bucket algorithm
- Configurable time windows (per second, minute, hour)

## Managed Server Types

### Embedded Servers

**Definition**: Python packages implementing MCP servers using the Python MCP SDK, loaded in-process.

**Characteristics:**
- Imported as Python modules
- Share same process space
- Direct function calls (no IPC overhead)
- Configured via manual list in `mcp_compose.toml`
- Must be installed in Python environment

**Configuration:**
```toml
[[servers.embedded.servers]]
name = "jupyter-mcp-server"
package = "jupyter_mcp_server"
enabled = true
tool_mappings = { "create" = "jupyter_create" }
```

**Discovery:**
No automatic discovery - servers must be explicitly listed in configuration.

**Initialization:**
```python
import importlib
module = importlib.import_module("jupyter_mcp_server")
server_instance = module.get_mcp_server()  # Standard interface
```

### Proxied STDIO Servers

**Definition**: External MCP servers accessed via standard input/output streams.

**Characteristics:**
- Separate processes
- Communication via stdin/stdout
- Language-agnostic (Node.js, Python, Go, etc.)
- Managed by Process Manager
- Can crash and be restarted

**Configuration:**
```toml
[[servers.proxied.stdio]]
name = "weather-server"
command = ["uvx", "mcp-server-weather"]
env = { WEATHER_API_KEY = "${WEATHER_API_KEY}" }
restart_policy = "on-failure"
health_check_enabled = true
```

**Communication:**
The Process Manager handles:
- Starting process with configured command
- Writing MCP requests to stdin
- Reading MCP responses from stdout
- Error handling from stderr
- Process lifecycle management

### Proxied SSE Servers

**Definition**: Remote MCP servers accessed via SSE (Server-Sent Events) over HTTP.

**Characteristics:**
- Remote processes (can be on different machines)
- HTTP-based communication
- Supports cloud-hosted servers
- Two modes: proxy and translator

**Configuration:**
```toml
[[servers.proxied.sse]]
name = "remote-server"
url = "https://api.example.com/mcp/sse"
auth_token = "${REMOTE_TOKEN}"
mode = "proxy"  # or "translator"
```

**Modes:**

1. **Proxy Mode**: Reverse proxy functionality
   - Forwards requests to remote server as-is
   - Minimal transformation
   - Low latency
   - Suitable when client and remote server use same transport

2. **Translator Mode**: Protocol translation
   - Converts between STDIO ↔ SSE
   - Enables STDIO clients to access SSE servers
   - Enables SSE clients to access STDIO servers
   - Adds slight latency for translation

## Implementation Phases

### Phase 1: Foundation & Core Functionality
**Timeline**: Weeks 1-4

**Deliverables:**
- ✅ Migration from `pyproject.toml` to `mcp_compose.toml`
- ✅ Configuration schema implementation and validation
- ✅ Enhanced Tool Manager with all conflict resolution strategies
- ✅ Process Manager for STDIO proxied servers
  - Process lifecycle management
  - Basic restart policies
  - stdout/stderr capture
- ✅ SSE transport support for composer
- ✅ Basic embedded server loading from manual list

**Success Criteria:**
- Configuration file can be loaded and validated
- Embedded servers can be loaded and tools aggregated
- STDIO proxied servers can be started and managed
- Tool conflicts are resolved per configuration
- Basic SSE transport works for client connections

### Phase 2: Advanced Process Management & Security
**Timeline**: Weeks 5-8

**Deliverables:**
- ✅ Advanced Process Manager features
  - Health checks (tool, ping, custom)
  - Resource limits (CPU, memory)
  - Graceful shutdown
  - Log aggregation
- ✅ SSE proxied server support
  - Proxy mode implementation
  - Connection management
  - Error handling and retries
- ✅ Authentication middleware framework
  - API Key authentication
  - JWT authentication
  - OAuth2/OIDC authentication
  - Mutual TLS authentication
- ✅ Authorization middleware framework
  - RBAC implementation
  - Tool-level permissions
  - Rate limiting

**Success Criteria:**
- Processes are monitored and auto-restarted
- Health checks detect and respond to failures
- Resource limits are enforced
- All authentication methods work
- Authorization properly restricts access
- Rate limiting prevents abuse

### Phase 3: REST API & Monitoring
**Timeline**: Weeks 9-12

**Deliverables:**
- ✅ REST API implementation
  - All management endpoints
  - All tool endpoints
  - All configuration endpoints
  - All status endpoints
- ✅ Monitoring & observability
  - Prometheus metrics
  - Structured logging
  - OpenTelemetry tracing
  - Log aggregation
- ✅ SSE translator mode
  - STDIO ↔ SSE protocol translation
  - Buffering and flow control
- ✅ API documentation (OpenAPI/Swagger)

**Success Criteria:**
- All REST endpoints are functional and tested
- Metrics are collected and exposed
- Logs are properly structured and aggregated
- Distributed tracing works end-to-end
- API documentation is complete and accurate

### Phase 4: Web UI & Polish
**Timeline**: Weeks 13-16

**Deliverables:**
- ✅ Web UI implementation (React)
  - Server management interface
  - Tool testing interface
  - Log viewer
  - Metrics dashboard
  - Configuration editor
- ✅ UI/UX polish
  - Responsive design
  - Dark/light themes
  - Real-time updates (WebSocket)
  - Error handling and notifications
- ✅ Documentation
  - User guide
  - API reference
  - Configuration reference
  - Deployment guide
  - Examples and tutorials
- ✅ Packaging and distribution
  - PyPI package
  - Docker images
  - Helm charts (Kubernetes)

**Success Criteria:**
- UI is functional, intuitive, and polished
- All features are accessible via UI
- Documentation is comprehensive
- Package can be easily installed and deployed
- Example configurations and tutorials are available

### Phase 5: Production Readiness
**Timeline**: Weeks 17-20

**Deliverables:**
- ✅ Performance optimization
  - Connection pooling
  - Caching strategies
  - Request batching
  - Resource optimization
- ✅ Security hardening
  - Security audit
  - Vulnerability scanning
  - Secret management integration
  - Secure defaults
- ✅ High availability features
  - Graceful degradation
  - Circuit breakers
  - Fallback mechanisms
- ✅ Testing
  - Integration tests
  - Load tests
  - Security tests
  - End-to-end tests
- ✅ Operations
  - Deployment automation
  - Monitoring playbooks
  - Incident response procedures
  - Backup and recovery procedures

**Success Criteria:**
- Performance meets targets (latency, throughput)
- No critical security vulnerabilities
- System handles failures gracefully
- Test coverage > 90%
- Operations documentation complete
- Ready for production deployment

## Testing Strategy

### Unit Tests
- Individual component testing
- Mock external dependencies
- High coverage (>90%)

### Integration Tests
- Component interaction testing
- Real embedded/proxied servers
- Configuration scenarios

### End-to-End Tests
- Full workflow testing
- Client ↔ Composer ↔ Servers
- Multiple transport types

### Load Tests
- Concurrent client connections
- High tool invocation rates
- Resource limit validation
- Memory leak detection

### Security Tests
- Authentication bypass attempts
- Authorization escalation attempts
- Rate limit enforcement
- Input validation
- Injection attacks

## Deployment Scenarios

### Standalone Server
```bash
mcp-compose serve --config /etc/mcp-composer/config.toml
```

### Docker Container
```dockerfile
FROM python:3.11-slim
COPY mcp_compose.toml /config/
CMD ["mcp-compose", "serve", "--config", "/config/mcp_compose.toml"]
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-composer
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: composer
        image: datalayer/mcp-composer:latest
        env:
        - name: MCP_CONFIG
          value: /config/mcp_compose.toml
        volumeMounts:
        - name: config
          mountPath: /config
```

### Systemd Service
```ini
[Unit]
Description=MCP Server Composer
After=network.target

[Service]
Type=simple
User=mcp
ExecStart=/usr/local/bin/mcp-compose serve --config /etc/mcp-composer/config.toml
Restart=always

[Install]
WantedBy=multi-user.target
```

## Performance Considerations

### Embedded Servers
- **Pros**: Zero IPC overhead, fast invocation
- **Cons**: Share process resources, Python GIL limitations

### Proxied STDIO Servers
- **Pros**: Process isolation, any language
- **Cons**: IPC overhead, serialization cost

### Proxied SSE Servers
- **Pros**: Remote servers, horizontal scaling
- **Cons**: Network latency, connection management

### Optimization Strategies:
- Connection pooling for SSE servers
- Request batching where possible
- Caching of tool schemas and metadata
- Lazy loading of embedded servers
- Async/await throughout the stack

## Monitoring Metrics

### Tool Metrics:
- `mcp_tool_invocations_total{tool, server, status}`
- `mcp_tool_duration_seconds{tool, server}`
- `mcp_tool_errors_total{tool, server, error_type}`

### Server Metrics:
- `mcp_server_status{server, type}` (0=down, 1=up)
- `mcp_server_restarts_total{server}`
- `mcp_server_uptime_seconds{server}`
- `mcp_server_cpu_usage{server}`
- `mcp_server_memory_bytes{server}`

### Composer Metrics:
- `mcp_composer_active_connections{transport}`
- `mcp_composer_requests_total{endpoint, method, status}`
- `mcp_composer_request_duration_seconds{endpoint, method}`
- `mcp_composer_rate_limit_exceeded_total{user, role}`

## Error Handling

### Error Categories:
1. **Configuration Errors**: Invalid TOML, missing required fields
2. **Discovery Errors**: Cannot import embedded server, invalid package
3. **Process Errors**: STDIO server crash, health check failure
4. **Network Errors**: SSE connection failure, timeout
5. **Authentication Errors**: Invalid credentials, token expired
6. **Authorization Errors**: Insufficient permissions, rate limit exceeded
7. **Tool Errors**: Tool invocation failure, invalid parameters

### Error Responses:
```json
{
  "error": {
    "code": "TOOL_INVOCATION_FAILED",
    "message": "Failed to execute tool: jupyter_notebook_create",
    "details": {
      "server": "jupyter-mcp-server",
      "tool": "notebook_create",
      "error": "Connection timeout"
    },
    "timestamp": "2025-10-13T10:30:00Z"
  }
}
```

### Recovery Strategies:
- Automatic retry with exponential backoff
- Fallback to alternative servers (if available)
- Circuit breaker pattern for failing services
- Graceful degradation (partial functionality)

## Conclusion

The MCP Server Composer provides a robust, secure, and scalable solution for aggregating multiple MCP servers into a unified interface. With comprehensive authentication, authorization, monitoring, and management capabilities, it enables organizations to build complex MCP-based systems with confidence.
