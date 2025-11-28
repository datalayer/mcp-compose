# Testing the MCP Server with OAuth2

This guide shows how to test the MCP server with curl commands.

## Prerequisites

1. Server must be running:
   ```bash
   python mcp_auth_example/server.py
   ```

2. You need a valid GitHub OAuth token (get one by running the client first)

## Testing Endpoints

### 1. Public Endpoints (No Authentication Required)

#### Root Endpoint
```bash
curl -s http://localhost:8080/ | python -m json.tool
```

Expected response:
```json
{
    "name": "MCP Server with GitHub OAuth2",
    "version": "1.0.0",
    "authentication": "GitHub OAuth2",
    "transport": "HTTP with SSE",
    "mcp_endpoints": {
        "sse": "http://localhost:8080/sse"
    },
    "oauth_metadata": {
        "protected_resource": "http://localhost:8080/.well-known/oauth-protected-resource",
        "authorization_server": "http://localhost:8080/.well-known/oauth-authorization-server"
    },
    "documentation": "https://github.com/datalayer/mcp-compose/tree/main/examples/mcp-auth"
}
```

#### Health Check
```bash
curl -s http://localhost:8080/health | python -m json.tool
```

Expected response:
```json
{
    "status": "healthy",
    "authentication": "required",
    "oauth_provider": "GitHub"
}
```

#### OAuth Protected Resource Metadata (RFC 9728)
```bash
curl -s http://localhost:8080/.well-known/oauth-protected-resource | python -m json.tool
```

Expected response:
```json
{
    "resource": "http://localhost:8080",
    "authorization_servers": ["http://localhost:8080"],
    "bearer_methods_supported": ["header"],
    "resource_documentation": "https://github.com/datalayer/mcp-compose/tree/main/examples/mcp-auth"
}
```

#### OAuth Authorization Server Metadata (RFC 8414)
```bash
curl -s http://localhost:8080/.well-known/oauth-authorization-server | python -m json.tool
```

Expected response:
```json
{
    "issuer": "http://localhost:8080",
    "authorization_endpoint": "https://github.com/login/oauth/authorize",
    "token_endpoint": "https://github.com/login/oauth/access_token",
    "response_types_supported": ["code"],
    "grant_types_supported": ["authorization_code"],
    "code_challenge_methods_supported": ["S256"],
    "token_endpoint_auth_methods_supported": ["client_secret_post"],
    "service_documentation": "https://docs.github.com/en/developers/apps/building-oauth-apps"
}
```

### 2. Protected Endpoints (Authentication Required)

#### SSE Endpoint - Without Authentication (Should Fail)
```bash
curl -i http://localhost:8080/sse
```

Expected response:
```
HTTP/1.1 401 Unauthorized
date: Wed, 29 Oct 2025 21:46:29 GMT
server: uvicorn
www-authenticate: Bearer realm="http://localhost:8080/.well-known/oauth-protected-resource"
content-length: 35
content-type: application/json

{"error":"Missing Authorization header"}
```

#### SSE Endpoint - With Authentication (Should Work)
```bash
# Replace YOUR_GITHUB_TOKEN with your actual token
curl -i -H "Authorization: Bearer YOUR_GITHUB_TOKEN" http://localhost:8080/sse
```

Expected response: SSE stream starting with MCP protocol handshake

#### Testing Authentication Rejection
```bash
# With invalid token
curl -i -H "Authorization: Bearer invalid_token" http://localhost:8080/sse
```

Expected response:
```
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer realm="http://localhost:8080/.well-known/oauth-protected-resource"
content-type: application/json

{"error":"Invalid or expired token"}
```

## Getting a GitHub Token for Testing

### Method 1: Run the Client
```bash
python mcp_auth_example/client.py
```
Follow the OAuth flow and the client will display your token.

### Method 2: Create a GitHub Personal Access Token
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `read:user`
4. Copy the generated token

## Testing MCP Protocol

The MCP protocol works over Server-Sent Events (SSE). To properly test tool invocation:

1. Use the Python client:
   ```bash
   python mcp_auth_example/client.py
```2. Or use an MCP-compatible client library that supports SSE transport with Bearer authentication

## Troubleshooting

### Port Already in Use
```bash
# Find and kill the process
lsof -i :8080
kill -9 <PID>
```

### Token Validation Failing
- Ensure your GitHub token has `read:user` scope
- Check if the token has expired
- Verify network connectivity to api.github.com

### SSE Connection Issues
- Ensure the Authorization header is properly formatted: `Bearer <token>`
- Check server logs for detailed error messages
- Verify the token is valid by testing with GitHub API directly:
  ```bash
  curl -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/user
  ```
