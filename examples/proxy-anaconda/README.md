<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# Anaconda Authentication MCP Servers Example

This example demonstrates how to use MCP Compose with **Anaconda authentication at the composer level**.

## 🎯 Overview

This configuration launches two simple Python MCP servers behind an authenticated MCP Compose:

1. **Calculator Server** (`mcp1.py`) - Math operations (add, subtract, multiply, divide)
2. **Echo Server** (`mcp2.py`) - String operations (ping, echo, reverse, uppercase, lowercase, count_words)

Both servers:
- Run in **proxy mode** via STDIO transport
- Are managed by the MCP Compose
- Are accessed through the **composer's authentication layer**

## 🔐 Authentication Architecture

```
┌─────────────┐
│   Client    │
│  (Agent)    │
└──────┬──────┘
       │ HTTP/SSE + Anaconda Auth
       ▼
┌─────────────────────────────┐
│    MCP Compose              │
│  ┌─────────────────────┐    │
│  │ Authentication      │    │ ← Anaconda auth here
│  │ Middleware          │    │
│  └─────────┬───────────┘    │
│            │                 │
│  ┌─────────┴───────────┐    │
│  │  Tool Manager       │    │
│  └─────────┬───────────┘    │
└────────────┼─────────────────┘
             │ STDIO (no auth)
       ┌─────┴─────┐
       ▼           ▼
┌────────────┐ ┌────────────┐
│ Calculator │ │   Echo     │
│   Server   │ │   Server   │
└────────────┘ └────────────┘
```

**Key Point**: Authentication happens at the **MCP Compose level**, not in the individual servers. The servers are simple STDIO processes without authentication logic.

## 📋 Features

- **Two Simple Servers**: Calculator and Echo servers with basic tools
- **Anaconda Authentication**: Secure authentication via anaconda-auth
- **Pure Python**: Minimal dependencies (FastMCP + anaconda-auth)
- **Configuration-Based**: Define servers in `mcp_compose.toml`
- **Process Management**: Composer manages server lifecycles
- **STDIO Transport**: Standard input/output for MCP communication
- **Environment Variables**: Secure token passing via environment
- **Easy Management**: Simple make commands to control everything

## 🔑 Prerequisites

### 1. Anaconda Account (For Clients)

Clients connecting to this MCP Compose will need:
- An Anaconda.com account (sign up at https://anaconda.cloud/)
- A valid Anaconda access token or API key

### 2. No Server Prerequisites

The MCP Compose **does not require** an `ANACONDA_API_KEY` to start.
It validates bearer tokens provided by clients in their requests.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
make install
```

This will install:
- `mcp-compose` (the orchestrator)
- `fastmcp` (for the demo MCP servers)
- `anaconda-auth` (for token validation)

### 2. Start the Composer

```bash
make start
```

**No Anaconda credentials required to start the server!** The composer will:
- Read configuration from `mcp_compose.toml`
- Start both Calculator and Echo MCP servers as child processes
- Listen on port 8080 for client connections
- Validate bearer tokens from incoming client requests using `anaconda-auth`

You'll see output like:
```
🔐 Authentication enabled
   Provider: anaconda
   Domain: anaconda.com
   ✓ Authenticator initialized
```

### 3. Connect with a Client

Clients must provide an Anaconda bearer token in requests:

```python
from pydantic_ai.mcp import MCPServerSSE
from anaconda_auth.token import TokenInfo

# Get your access token
token = TokenInfo(domain="anaconda.com", api_key="your-api-key").get_access_token()

# Connect to MCP Compose with authentication
mcp_server = MCPServerSSE(
    url="http://localhost:8080/sse",
    headers={"Authorization": f"Bearer {token}"}
)
```

**Token Validation Flow:**
1. Client sends request with `Authorization: Bearer <token>`
2. Composer extracts bearer token
3. Composer validates: `TokenInfo(domain="anaconda.com", api_key=token).get_access_token()`
4. If valid, request is proxied to backend servers
5. If invalid, request is rejected with 401 Unauthorized

### 4. Use the AI Agent (Coming Soon)

> **🚧 Work in Progress**: The agent integration requires the unified SSE endpoint to be implemented in the serve command. The agent.py file is ready and demonstrates the intended usage pattern.

```bash
# Install pydantic-ai
make install-agent

# Run the agent (requires SSE endpoint - coming soon!)
make agent
```

The agent is designed to:
- Connect to the MCP Compose via SSE
- Access tools from both Calculator and Echo servers through a unified interface
- Provide an interactive CLI powered by Anthropic Claude

Example interactions (once SSE endpoint is available):
- "What is 15 plus 27?"
- "Multiply 8 by 9"
- "Reverse the text 'hello world'"
- "Convert 'Hello World' to uppercase"
- "Count the words in 'The quick brown fox jumps'"

### 5. Stop the Composer

Press `Ctrl+C` in the terminal where the composer is running.

## 🔧 How Authentication Works

### Authentication Flow

1. **Client Authenticates with Anaconda**: Client obtains access token from Anaconda
2. **Client Request**: Client sends request with `Authorization: Bearer <token>` header
3. **Composer Validates**: Authentication middleware validates token using `anaconda_auth`
4. **Token Validation**: 
   ```python
   from anaconda_auth.token import TokenInfo
   access_token = TokenInfo(domain="anaconda.com", api_key=token).get_access_token()
   ```
5. **Proxy Request**: If valid, composer proxies request to backend servers
6. **Response**: Composer returns server response to authenticated client

### Key Points

- **No server-side API key needed**: Composer doesn't need `ANACONDA_API_KEY` to start
- **Bearer token validation**: Each client request is validated independently
- **Stateless**: No session storage, each request must include the token
- **Backend servers unaware**: STDIO servers don't handle authentication

### Implementation Snippet

The validation logic needed in the composer:

```python
from anaconda_auth.token import TokenInfo

def validate_bearer_token(bearer_token: str) -> bool:
    """
    Validate Anaconda bearer token.
    
    Args:
        bearer_token: Token from Authorization header (without 'Bearer ' prefix)
    
    Returns:
        True if token is valid, False otherwise
    """
    try:
        # Validate token with Anaconda
        token_info = TokenInfo(
            domain="anaconda.com",
            api_key=bearer_token
        )
        access_token = token_info.get_access_token()
        return access_token is not None
    except Exception:
        return False

# In request handler:
# auth_header = request.headers.get("Authorization")
# if auth_header and auth_header.startswith("Bearer "):
#     token = auth_header[7:]  # Remove "Bearer " prefix
#     if not validate_bearer_token(token):
#         raise HTTPException(status_code=401, detail="Invalid token")
```

## 📖 Testing the Servers

Once running, you can test the authenticated servers (when SSE endpoint is available):

### Calculator Operations

```bash
# Add numbers
curl -X POST http://localhost:8080/api/v1/tools/calculator:add/invoke \
  -H "Content-Type: application/json" \
  -d '{"a": 15, "b": 27}'

# Multiply numbers
curl -X POST http://localhost:8080/api/v1/tools/calculator:multiply/invoke \
  -H "Content-Type: application/json" \
  -d '{"a": 8, "b": 9}'
```

### Echo Operations

```bash
# Reverse text
curl -X POST http://localhost:8080/api/v1/tools/echo:reverse/invoke \
  -H "Content-Type: application/json" \
  -d '{"text": "hello world"}'

# Convert to uppercase
curl -X POST http://localhost:8080/api/v1/tools/echo:uppercase/invoke \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World"}'
```

## 🔧 Configuration

The configuration file `mcp_compose.toml` defines:

```toml
[composer]
name = "anaconda-composer"
conflict_resolution = "prefix"
log_level = "INFO"

# ============================================================================
# Authentication Configuration
# ============================================================================
[authentication]
enabled = true
providers = ["anaconda"]
default_provider = "anaconda"

[authentication.anaconda]
domain = "anaconda.com"  # Use "your-company.anaconda.com" for enterprise

# ============================================================================
# Backend MCP Servers (No auth - accessed via composer only)
# ============================================================================
[[servers.proxied.stdio]]
name = "calculator"
command = ["python", "mcp1.py"]
restart_policy = "never"

[[servers.proxied.stdio]]
name = "echo"
command = ["python", "mcp2.py"]
restart_policy = "never"
```

### Key Configuration Points

1. **Authentication at Composer Level**: 
   - `authentication.enabled = true` enables the auth middleware
   - `authentication.providers = ["anaconda"]` uses Anaconda authentication
   
2. **Backend Servers**: 
   - No authentication configuration needed
   - Servers are simple STDIO processes
   - Only accessible through the authenticated composer

3. **Environment Variables**:
   - `ANACONDA_API_KEY` - Your Anaconda API key (required)

### Custom Domain (Enterprise)

For enterprise Anaconda deployments:

```toml
[authentication.anaconda]
domain = "your-company.anaconda.com"
```

## 🛠️ Makefile Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make install` | Install dependencies (including anaconda-auth) |
| `make login` | Authenticate with Anaconda (interactive browser login) |
| `make install-agent` | Install pydantic-ai for agent support |
| `make start` | Start composer (requires authentication) |
| `make agent` | Run AI agent (coming soon) |
| `make stop` | Stop composer |
| `make clean` | Clean up temporary files |

## 🔧 Available Tools

### Calculator Server Tools (`mcp1.py`)

- `calculator:add(a, b)` - Add two numbers
- `calculator:subtract(a, b)` - Subtract b from a
- `calculator:multiply(a, b)` - Multiply two numbers
- `calculator:divide(a, b)` - Divide a by b (with zero check)

### Echo Server Tools (`mcp2.py`)

- `echo:ping()` - Returns 'pong'
- `echo:echo(message)` - Echo back a message
- `echo:reverse(text)` - Reverse a string
- `echo:uppercase(text)` - Convert to uppercase
- `echo:lowercase(text)` - Convert to lowercase
- `echo:count_words(text)` - Count words in text

All tools require Anaconda authentication to access.

## 🐛 Troubleshooting

### Authentication Issues

**Problem**: `anaconda-auth` not installed
```bash
# Solution:
pip install anaconda-auth
# Or re-run:
make install
```

**Problem**: Login fails in browser
```bash
# Solution:
# 1. Check internet connection
# 2. Make sure you have a valid Anaconda account
# 3. Try clearing browser cookies for anaconda.com
# 4. Check if you can access https://anaconda.com/app
```

**Problem**: API key doesn't work
```bash
# Solution:
# 1. Verify key is correct (no extra spaces)
# 2. Check key hasn't expired
# 3. Regenerate key in Anaconda settings
# 4. Make sure environment variable is set:
echo $ANACONDA_API_KEY
```

### Server Issues

**Problem**: Server won't start
```bash
# No authentication needed to start!
# Just run:
make start

# Check if port 8080 is available:
lsof -i :8080

# If occupied, kill the process or change port in config
```

**Problem**: Configuration validation errors
```bash
# The authentication config is commented out (not yet implemented)
# Server should start without errors
# Check mcp_compose.toml for syntax issues
```

## 🔒 Security Notes

### Authentication Security

✅ **This example uses Anaconda authentication for server access**

Security features:
- **Token-based authentication**: Uses Anaconda access tokens
- **Secure token storage**: Tokens managed by anaconda-auth library
- **Environment variables**: API keys passed securely via environment
- **No hardcoded credentials**: All sensitive data in environment or secure storage

### Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** for API keys
3. **Rotate keys regularly** in Anaconda settings
4. **Use different keys** for different environments (dev, staging, prod)
5. **Enable MCP Compose authentication** in production (see mcp-auth example)
6. **Use HTTPS** in production deployments
7. **Monitor access logs** for suspicious activity

### For Production

This example demonstrates Anaconda auth for the MCP servers themselves. For production, you should also:

1. **Enable MCP Compose authentication** - Protect the composer endpoints
2. **Use RBAC** - Role-based access control for different users
3. **Add rate limiting** - Prevent abuse
4. **Enable CORS properly** - Only trusted origins
5. **Use HTTPS** - Encrypt all traffic
6. **Add audit logging** - Track who accessed what

See the [mcp-auth example](../mcp-auth/) for OAuth2 authentication at the composer level.

## ✅ Implementation Status

### What's Working
- ✅ Backend MCP servers (calculator, echo)
- ✅ MCP Compose configuration structure
- ✅ Authentication framework in mcp-compose
- ✅ **Anaconda Authenticator**: Implemented in `mcp_compose/auth_anaconda.py`
- ✅ **Token validation**: Integration with `anaconda_auth.token.TokenInfo`
- ✅ **Configuration loading**: Parse `[authentication.anaconda]` from TOML
- ✅ **Middleware integration**: Applied to SSE/HTTP endpoints via FastAPI dependencies

### Implementation Details

The Anaconda authentication has been fully implemented:

1. **AnacondaAuthenticator Class** (`mcp_compose/auth_anaconda.py`):
   - Validates bearer tokens using `anaconda_auth.token.TokenInfo`
   - Supports custom domains for enterprise deployments
   - Extracts user information from tokens

2. **Configuration Support** (`mcp_compose/config.py`):
   - Added `AuthProvider.ANACONDA` enum value
   - Added `AnacondaAuthConfig` model with domain configuration
   - Validates Anaconda auth configuration when enabled

3. **API Integration** (`mcp_compose/api/dependencies.py`):
   - Bearer token extraction from Authorization header
   - Automatic authentication using configured authenticator
   - Anonymous access when authentication is disabled

4. **CLI Integration** (`mcp_compose/cli.py`):
   - Initializes authenticator from configuration
   - Displays authentication status on startup

## 📚 Learn More

- **[User Guide](../../docs/USER_GUIDE.md)** - Complete feature documentation
- **[API Reference](../../docs/API_REFERENCE.md)** - REST API documentation  
- **[Deployment Guide](../../docs/DEPLOYMENT.md)** - Production deployment
- **[Architecture](../../docs/ARCHITECTURE.md)** - System design
- **[MCP Auth Example](../mcp-auth/)** - OAuth2 authentication implementation

## 🤝 Contributing

Found an issue or want to improve this example? Please open an issue or PR!

This example demonstrates the **configuration and architecture** for Anaconda authentication. 
The actual `AnacondaAuthenticator` implementation needs to be added to the mcp-compose codebase.

## 📄 License

BSD 3-Clause License - see [LICENSE](../../LICENSE)

---

**Made with ❤️ by [Datalayer](https://datalayer.ai)**
