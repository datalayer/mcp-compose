# MCP Server with GitHub OAuth - Implementation Notes

## Key Changes

The server has been updated to use the **official MCP Python SDK** (FastMCP) instead of implementing a custom protocol handler. This makes it a proper MCP server that follows the official specification.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Application                       │
│                      (mcp_auth_example/client.py)                     │
│                                                                  │
│  1. OAuth2 Flow (GitHub authentication)                         │
│  2. MCP SDK Client (mcp.client.sse)                            │
│  3. SSE Transport with Bearer token                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ HTTPS + Bearer Token
                            │
┌───────────────────────────┴─────────────────────────────────────┐
│                      FastAPI Application                         │
│                      (mcp_auth_example/server.py)                     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         Authentication Middleware                          │ │
│  │  • Extract Bearer token from Authorization header          │ │
│  │  • Validate token with GitHub API                          │ │
│  │  • Cache validation results                                │ │
│  │  • Return 401 if invalid                                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                            ↓                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              FastMCP Server                                 │ │
│  │         (mcp.server.fastmcp.FastMCP)                       │ │
│  │                                                             │ │
│  │  Tools decorated with @mcp.tool():                         │ │
│  │  • calculator_add(a, b) → int                              │ │
│  │  • calculator_multiply(a, b) → int                         │ │
│  │  • greeter_hello(name) → str                               │ │
│  │  • greeter_goodbye(name) → str                             │ │
│  │  • get_server_info() → Dict                                │ │
│  └────────────────────────────────────────────────────────────┘ │
│                            ↓                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │           MCP Protocol Handlers                             │ │
│  │  • /sse - Server-Sent Events endpoint                      │ │
│  │  • /messages - MCP messages endpoint                       │ │
│  │  • Both require authentication                             │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Server (mcp_auth_example/server.py)

**Built with:**
- `FastMCP` from `mcp.server.fastmcp` - Official MCP SDK
- `FastAPI` - HTTP/SSE transport layer
- `uvicorn` - ASGI server

**Features:**
- Tools defined using `@mcp.tool()` decorator
- Automatic parameter validation via type hints
- Built-in MCP protocol handling (SSE transport)
- OAuth2 authentication middleware
- Token validation with GitHub API
- Protected Resource Metadata (RFC 9728)
- Authorization Server Metadata (RFC 8414)

**Authentication Flow:**
1. Client connects to `/sse` endpoint with Bearer token
2. Middleware extracts and validates token
3. Token verified with GitHub API
4. User info cached for performance
5. Request forwarded to FastMCP handler
6. Tools executed with user context available

### 2. Client (mcp_auth_example/client.py)

**Built with:**
- `mcp.ClientSession` - Official MCP client
- `mcp.client.sse.sse_client` - SSE transport
- `requests` - OAuth2 flow and HTTP calls

**Features:**
- Complete OAuth2 discovery flow
- PKCE implementation (RFC 7636)
- Browser-based authentication
- MCP protocol communication via SSE
- Proper tool invocation using MCP SDK
- Fallback HTTP methods for testing

**Tool Invocation:**
```python
# Using MCP SDK (proper way)
async with sse_client(url=f"{server_url}/sse", headers=headers) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("calculator_add", {"a": 5, "b": 3})
```

## MCP Protocol Details

### Transport: HTTP with SSE

The server uses **Server-Sent Events (SSE)** for MCP communication:
- Client connects to `/sse` endpoint
- Server streams MCP messages
- Client sends messages to `/messages` endpoint
- All communication authenticated via Bearer token

### Message Flow

```
1. Client → Server: GET /sse (with Bearer token)
   Server validates token, opens SSE connection

2. Client → Server: POST /messages {"method": "tools/list"}
   Server processes request, returns tools

3. Client → Server: POST /messages {"method": "tools/call", "params": {...}}
   Server invokes tool, returns result

4. Server → Client: SSE stream with responses
```

### Tool Definition

Tools are defined using the FastMCP decorator:

```python
@mcp.tool()
def calculator_add(a: int, b: int) -> int:
    """
    Add two numbers
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        Sum of a and b
    """
    return a + b
```

FastMCP automatically:
- Generates tool schema from type hints
- Validates parameters
- Handles serialization/deserialization
- Provides error handling

## OAuth2 Integration

### How Authentication Works

1. **Discovery**: Client discovers OAuth endpoints from server metadata
2. **Authorization**: User authenticates with GitHub in browser
3. **Token Exchange**: Client exchanges auth code for access token
4. **MCP Connection**: Client includes token in every request
5. **Validation**: Server validates token before processing

### Token in MCP Requests

All MCP requests include the Bearer token:

```python
headers = {"Authorization": f"Bearer {access_token}"}

# For SSE endpoint
async with sse_client(url=f"{server_url}/sse", headers=headers) as (read, write):
    # MCP communication here
```

### Middleware Implementation

```python
async def verify_token(authorization: Optional[str]) -> Dict[str, Any]:
    """Verify OAuth token from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    
    token = authorization[7:]
    user_info = token_validator.validate_token(token)
    
    if not user_info:
        raise HTTPException(status_code=401)
    
    return user_info

@app.get("/sse")
async def handle_sse(request: Request, authorization: Optional[str] = Header(None)):
    """SSE endpoint - requires authentication"""
    user_info = await verify_token(authorization)
    request.state.user = user_info
    return await mcp.sse_handler(request)
```

## Benefits of Using MCP SDK

### Before (Custom Implementation)
- ❌ Manual protocol handling
- ❌ Custom message format
- ❌ Custom serialization
- ❌ Manual error handling
- ❌ No standard compliance

### After (MCP SDK)
- ✅ Standard MCP protocol
- ✅ Automatic schema generation
- ✅ Built-in validation
- ✅ Standard error handling
- ✅ Follows MCP specification
- ✅ Interoperable with other MCP clients
- ✅ SSE transport built-in
- ✅ Type-safe tool definitions

## Running the Example

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Installs:
- `mcp` - Official MCP SDK
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `requests` - HTTP client
- `sse-starlette` - SSE support

### 2. Configure OAuth

Create `config.json` with GitHub OAuth credentials:
```json
{
  "github": {
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET"
  },
  "server": {
    "host": "localhost",
    "port": 8080
  }
}
```

### 3. Run Server

```bash
python -m mcp_auth_example server
# Or using make:
make server
```

Server starts on http://localhost:8080 with:
- OAuth metadata endpoints
- MCP SSE endpoint at `/sse`
- MCP messages endpoint at `/messages`
- All tools protected by authentication

### 4. Run Client

```bash
python -m mcp_auth_example client
# Or using make:
make client
```

Client performs:
1. OAuth discovery
2. GitHub authentication (browser opens)
3. Token exchange
4. MCP connection via SSE
5. Tool listing
6. Tool invocation

## Testing

### Unit Tests

```bash
python -m pytest tests/test_auth.py
# Or run directly:
python tests/test_auth.py
# Or using make:
make test
```

Tests:
- Unauthenticated requests return 401
- Metadata endpoints are accessible
- MCP endpoints require authentication

### Manual Testing

```bash
# Check server info
curl http://localhost:8080/

# Check OAuth metadata
curl http://localhost:8080/.well-known/oauth-protected-resource
curl http://localhost:8080/.well-known/oauth-authorization-server

# Try unauthenticated access (should fail)
curl http://localhost:8080/sse
curl http://localhost:8080/tools
```

## Security Features

1. **PKCE** - Protects authorization code
2. **State Parameter** - CSRF protection
3. **Resource Parameter** - Token audience binding
4. **Token Validation** - Every request verified
5. **Bearer Token** - Never in URL
6. **Middleware** - Centralized auth logic
7. **Token Caching** - Efficient validation

## Comparison: Custom vs MCP SDK

| Aspect | Custom (_old/auth_server.py) | MCP SDK (mcp_auth_example/server.py) |
|--------|------------------------------|----------------------------------|
| Protocol | Custom HTTP/JSON | Standard MCP |
| Transport | HTTP POST | HTTP SSE |
| Tool Definition | Manual classes | `@mcp.tool()` decorator |
| Validation | Manual | Automatic via types |
| Schema | Manual generation | Auto-generated |
| Errors | Manual handling | Standard MCP errors |
| Interop | Limited | Works with any MCP client |
| Maintenance | High | Low (SDK handles it) |

## Next Steps

1. **Add More Tools**: Use `@mcp.tool()` decorator
2. **Add Resources**: Use `@mcp.resource()` for data
3. **Add Prompts**: Use `@mcp.prompt()` for templates
4. **Fine-grained Auth**: Check permissions per tool
5. **Token Refresh**: Implement refresh token flow
6. **Rate Limiting**: Add per-user rate limits
7. **Logging**: Track tool usage per user

## References

- **MCP Specification**: https://modelcontextprotocol.io/
- **MCP Python SDK**: https://github.com/modelcontextprotocol/python-sdk
- **FastMCP Documentation**: https://github.com/jlowin/fastmcp
- **OAuth 2.1**: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13
- **MCP Authorization**: https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization

## Summary

The refactored implementation:
- ✅ Uses official MCP Python SDK (FastMCP)
- ✅ Implements proper MCP protocol (SSE transport)
- ✅ Maintains OAuth2 authentication
- ✅ Follows MCP Authorization specification
- ✅ Provides type-safe tool definitions
- ✅ Enables interoperability with MCP ecosystem
- ✅ Simplifies maintenance and extension

This is now a **production-ready** example of an authenticated MCP server! 🎉
