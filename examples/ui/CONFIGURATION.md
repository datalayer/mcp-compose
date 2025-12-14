# MCP Compose UI Configuration Guide

This document explains the configuration settings in `mcp_compose.toml` for running MCP Compose with the Web UI.

## Configuration Sections

### Composer Settings

```toml
[composer]
name = "demo-composer"
conflict_resolution = "prefix"
log_level = "INFO"
```

- `name`: Identifier for the composed server
- `conflict_resolution`: How to handle tool name conflicts (`prefix`, `suffix`, `ignore`, `error`, `override`)
- `log_level`: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

### Transport Configuration

```toml
[transport]
stdio_enabled = true
streamable_http_enabled = false
sse_enabled = false
```

- `stdio_enabled`: Enable STDIO transport for local subprocess servers
- `streamable_http_enabled`: Enable HTTP streaming transport
- `sse_enabled`: Enable Server-Sent Events transport (deprecated)

### Authentication

```toml
[authentication]
enabled = true
providers = ["basic"]
default_provider = "basic"

[authentication.basic]
username = "admin"
password = "demo123"
```

**Security Notes:**
- Change the default password in production
- Use environment variables for credentials:
  ```toml
  username = "${MCP_USERNAME}"
  password = "${MCP_PASSWORD}"
  ```
- Consider using stronger authentication methods (JWT, OAuth2) for production

### UI Configuration

```toml
[ui]
enabled = true
framework = "react"
mode = "embedded"
path = "/ui"
port = 9456
```

- `enabled`: Enable/disable the Web UI
- `framework`: UI framework (currently supports `react`)
- `mode`: 
  - `embedded`: UI served on the same port as API
  - `separate`: UI served on a separate port (specified by `port`)
- `path`: URL path where UI is accessible
- `port`: Port for UI (default: 9456)

### API Configuration

```toml
[api]
enabled = true
path_prefix = "/api/v1"
host = "0.0.0.0"
port = 9456
cors_enabled = true
cors_origins = ["*"]
docs_enabled = true
```

- `enabled`: Enable REST API
- `path_prefix`: API path prefix
- `host`: Bind address (`0.0.0.0` for all interfaces)
- `port`: API port (should match UI port for embedded mode)
- `cors_enabled`: Enable Cross-Origin Resource Sharing
- `cors_origins`: Allowed CORS origins (`["*"]` allows all)
- `docs_enabled`: Enable Swagger/OpenAPI documentation

### Server Configuration

```toml
[[servers.proxied.stdio]]
name = "calculator"
command = ["python", "mcp1.py"]
restart_policy = "never"

[[servers.proxied.stdio]]
name = "echo"
command = ["python", "mcp2.py"]
restart_policy = "never"
```

Each server section defines:
- `name`: Server identifier
- `command`: Command to start the server
- `restart_policy`: `never`, `on-failure`, or `always`

## Environment Variables

Set these before starting:

```bash
export MCP_USERNAME=admin
export MCP_PASSWORD=your-secure-password
```

Then reference in config:

```toml
[authentication.basic]
username = "${MCP_USERNAME}"
password = "${MCP_PASSWORD}"
```

## Port Configuration

The UI and API ports should match when using `embedded` mode:

```toml
[ui]
port = 9456

[api]
port = 9456
```

For `separate` mode, use different ports:

```toml
[ui]
mode = "separate"
port = 9456

[api]
port = 8080
```

## Access URLs

With default configuration (port 9456):

- **Web UI**: http://localhost:9456/ui
- **API Documentation**: http://localhost:9456/docs
- **API Base**: http://localhost:9456/api/v1
- **Health Check**: http://localhost:9456/api/v1/health

## Advanced Configuration

### Adding More Servers

```toml
[[servers.proxied.stdio]]
name = "my-server"
command = ["python", "my_mcp_server.py"]
restart_policy = "on-failure"
max_restarts = 3
restart_delay = 5
health_check_enabled = true
```

### Configuring CORS

For production, limit CORS origins:

```toml
[api]
cors_origins = [
    "https://example.com",
    "https://app.example.com"
]
```

### Enabling Features

Control which UI features are available:

```toml
[ui]
features = [
    "server_management",
    "tool_testing",
    "logs_viewing",
    "metrics_dashboard",
    "configuration_editor"
]
```

## Troubleshooting

### Port Already in Use

If port 9456 is in use, change to another port:

```toml
[ui]
port = 9457

[api]
port = 9457
```

### Authentication Issues

1. Verify credentials in config
2. Check browser console for errors
3. Clear browser localStorage
4. Ensure authentication is enabled

### UI Not Loading

1. Check that UI artifacts are built: `cd ../../ui && npm run build`
2. Verify `ui.enabled = true`
3. Check logs for errors
4. Ensure static files are in `ui/dist/`

## Production Recommendations

1. **Use environment variables for secrets**
2. **Enable HTTPS** (use a reverse proxy like nginx)
3. **Restrict CORS origins**
4. **Use stronger authentication** (JWT or OAuth2)
5. **Set appropriate log levels**
6. **Monitor metrics and logs**
7. **Configure health checks for servers**

## Complete Example

See `mcp_compose.toml` in this directory for a complete working example.
