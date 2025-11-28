# MCP Inspector Setup Guide

This guide explains how to connect MCP Inspector to the authenticated MCP server.

## Overview

MCP Inspector is a browser-based tool for testing and debugging MCP servers. This server implements full OAuth 2.0 support with:

1. **OAuth Authorization Server**: Server acts as its own OAuth provider
   - Issues JWT tokens for MCP access
   - Delegates user authentication to GitHub
   - Implements PKCE for security
   - **Dynamic Client Registration (DCR)** - Clients can register themselves automatically

2. **Discovery Endpoints**: Properly configured metadata
   - `/.well-known/oauth-protected-resource` - Points to our OAuth endpoints
   - `/.well-known/oauth-authorization-server` - Describes OAuth capabilities including DCR
   - WWW-Authenticate header includes `resource_metadata` parameter

3. **OAuth Flow Endpoints**:
   - `/register` - Dynamic Client Registration (RFC 7591)
   - `/authorize` - Starts OAuth flow, redirects to GitHub
   - `/oauth/callback` - Receives GitHub auth, issues authorization code
   - `/token` - Exchanges code for JWT access token

4. **Token Validation**: Dual support
   - JWT tokens (issued by this server) for Inspector and other OAuth clients
   - GitHub tokens (for backward compatibility with client.py/agent.py)

## Architecture

```
MCP Inspector (Browser)
     ↓ 
     ↓ 1. (Optional) POST /register - Dynamic Client Registration
     ↓    Request: {"redirect_uris": ["http://localhost:6274/oauth/callback"], ...}
     ↓    Response: {"client_id": "dcr_abc123...", ...}
     ↓
     ↓ 2. GET /mcp (no token)
     ↓ 401 + WWW-Authenticate (discovery)
     ↓
     ↓ 3. GET /.well-known/oauth-protected-resource
     ↓    Response includes authorization_endpoint, token_endpoint, registration_endpoint
     ↓
     ↓ 4. Opens browser → /authorize
     ↓    Redirects to GitHub
     ↓
     ↓ 5. User signs in to GitHub
     ↓
     ↓ 6. GitHub → /oauth/callback
     ↓    Server validates GitHub user
     ↓    Issues authorization code
     ↓
     ↓ 7. Inspector → POST /token
     ↓    Exchanges authorization code for JWT
     ↓
     ↓ 8. Inspector → GET /mcp + Bearer JWT
     ✅ Connected! MCP tools available
```

## Prerequisites

1. **GitHub OAuth App**: Register an OAuth app at https://github.com/settings/developers
   - Application name: "MCP Auth Example" (or your choice)
   - Homepage URL: `http://localhost:8080` (or `https://localhost:8080` for HTTPS)
   - Authorization callback URL: `http://localhost:8080/oauth/callback`
   - Copy Client ID and Client Secret to `config.json`

2. **Optional: HTTPS**: For production or testing HTTPS
   - Follow [SSL.md](SSL.md) to set up mkcert certificates
   - Inspector works with both HTTP and HTTPS

## Quick Start

### Step 1: Configure GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click "New OAuth App"
3. Fill in:
   - **Application name**: MCP Auth Example
   - **Homepage URL**: `http://localhost:8080`
   - **Authorization callback URL**: `http://localhost:8080/oauth/callback`
4. Click "Register application"
5. Copy the **Client ID**
6. Generate a new **Client Secret** and copy it

### Step 2: Update config.json

Edit `references/oauth/config.json`:

```json
{
  "github": {
    "client_id": "YOUR_GITHUB_CLIENT_ID",
    "client_secret": "YOUR_GITHUB_CLIENT_SECRET"
  },
  "server": {
    "host": "localhost",
    "port": 8080
  }
}
```

### Step 3: Start the Server

```bash
# For HTTP (recommended for local development)
python -m mcp_oauth_example.server

# Or use make
make start
```

Verify the server shows:
```
📋 Server URL: http://localhost:8080
🔗 OAuth Endpoints:
   Dynamic Client Registration: http://localhost:8080/register
   Authorization: http://localhost:8080/authorize
   Token Exchange: http://localhost:8080/token
🔗 OAuth Metadata Endpoints:
   Protected Resource: http://localhost:8080/.well-known/oauth-protected-resource
   Authorization Server: http://localhost:8080/.well-known/oauth-authorization-server
```

### Step 4: Start MCP Inspector

```bash
# Using npm/npx
npx @modelcontextprotocol/inspector

# Or use make
make inspector
```

This will:
1. Start the Inspector on `http://localhost:6274`
2. Open your browser automatically

### Step 5: Connect Inspector to Server

1. In MCP Inspector, enter the server URL:
   ```
   http://localhost:8080/mcp
   ```

2. Click **"Connect"**

3. **Inspector automatically discovers OAuth endpoints** and may optionally register itself via DCR

4. **Browser opens** for GitHub authentication

5. **Sign in to GitHub** and authorize the application

6. You're **redirected back** to Inspector

7. **Inspector exchanges authorization code for JWT token**

8. **Connected!** You can now:
   - View available tools
   - Test tool calls
   - Inspect request/response messages
   - Debug MCP protocol flow

## Dynamic Client Registration (DCR)

The server supports **Dynamic Client Registration** per RFC 7591. Inspector can register itself automatically:

### How It Works

1. Inspector detects `registration_endpoint` in metadata:
   ```json
   {
     "registration_endpoint": "http://localhost:8080/register"
   }
   ```

2. Inspector registers itself:
   ```bash
   POST /register
   {
     "redirect_uris": ["http://localhost:6274/oauth/callback"],
     "client_name": "MCP Inspector"
   }
   ```

3. Server responds with client credentials:
   ```json
   {
     "client_id": "dcr_R7x3mK2pQnB8vYwT9zLcA1fE5hJ6sN4d",
     "redirect_uris": ["http://localhost:6274/oauth/callback"]
   }
   ```

4. Inspector uses `client_id` in OAuth flow

### Manual Registration (Optional)

You can also manually register Inspector:

```bash
curl -X POST http://localhost:8080/register \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uris": ["http://localhost:6274/oauth/callback"],
    "client_name": "MCP Inspector",
    "client_uri": "https://github.com/modelcontextprotocol/inspector"
  }'
```

Response:
```json
{
  "client_id": "dcr_abc123...",
  "client_id_issued_at": 1700000000,
  "redirect_uris": ["http://localhost:6274/oauth/callback"],
  "client_name": "MCP Inspector"
}
```

See [DYNAMIC_CLIENT_REGISTRATION.md](DYNAMIC_CLIENT_REGISTRATION.md) for complete DCR documentation.

## Available MCP Tools

Once connected, Inspector can test these tools:

- **calculator_add** - Add two numbers
- **calculator_multiply** - Multiply two numbers  
- **greeter_hello** - Greet someone
- **greeter_goodbye** - Say goodbye
- **get_server_info** - Get server information

### Testing Tools in Inspector

1. **Select a tool** from the list (e.g., `calculator_add`)
2. **Fill in parameters**:
   ```json
   {
     "a": 15,
     "b": 27
   }
   ```
3. **Click "Call Tool"**
4. **View the result**:
   ```json
   {
     "content": [
       {
         "type": "text",
         "text": "42"
       }
     ]
   }
   ```

## Verification

### Test Server Discovery

```bash
# Test 401 response with WWW-Authenticate header
curl -i http://localhost:8080/mcp

# Expected response:
# HTTP/1.1 401 Unauthorized
# WWW-Authenticate: Bearer realm="mcp", resource_metadata="http://localhost:8080/.well-known/oauth-protected-resource", scope="openid read:mcp write:mcp"
```

### Test Protected Resource Metadata

```bash
curl http://localhost:8080/.well-known/oauth-protected-resource | jq

# Expected response:
# {
#   "issuer": "http://localhost:8080",
#   "authorization_endpoint": "http://localhost:8080/authorize",
#   "token_endpoint": "http://localhost:8080/token",
#   "scopes_supported": ["openid", "read:mcp", "write:mcp"],
#   ...
# }
```

### Test Authorization Server Metadata

```bash
curl http://localhost:8080/.well-known/oauth-authorization-server | jq

# Expected response:
# {
#   "issuer": "http://localhost:8080",
#   "authorization_endpoint": "http://localhost:8080/authorize",
#   "token_endpoint": "http://localhost:8080/token",
#   "registration_endpoint": "http://localhost:8080/register",
#   "code_challenge_methods_supported": ["S256"],
#   ...
# }
```

### Test Dynamic Client Registration

```bash
curl -X POST http://localhost:8080/register \
  -H "Content-Type: application/json" \
  -d '{"redirect_uris": ["http://localhost:9999/callback"], "client_name": "Test"}' | jq

# Expected response:
# {
#   "client_id": "dcr_...",
#   "client_id_issued_at": 1700000000,
#   "redirect_uris": ["http://localhost:9999/callback"],
#   ...
# }
```

### Test DCR Suite

```bash
# Run comprehensive DCR tests
make test-dcr
```

## Troubleshooting

### Inspector Can't Connect

**Check 1: Is the server running?**
```bash
lsof -i :8080
# Should show Python process
```

**Check 2: Test server health**
```bash
curl http://localhost:8080/health
# Should return: {"status": "healthy", ...}
```

**Check 3: Check server logs**

Look for errors in the terminal where `make start` is running.

### OAuth Flow Fails

**Problem:** "Missing code or error in response"

**Solutions:**

1. **Check callback URL**: Ensure GitHub OAuth app has `http://localhost:8080/oauth/callback`
2. **Check server logs**: Look for errors during `/oauth/callback`
3. **Verify GitHub credentials**: Ensure `config.json` has correct client_id and client_secret
4. **Test OAuth manually**: Try the authorization flow in browser

### 401 Unauthorized Error

**Problem:** Inspector shows "Authentication failed"

**Solutions:**

1. **Token expired**: Disconnect and reconnect Inspector
2. **Invalid token**: Check server logs for token validation errors
3. **GitHub token invalid**: Ensure GitHub OAuth app is active

### Connection Timeout

**Problem:** Inspector shows "Connection timeout"

**Solutions:**

1. **Check firewall**: Allow connections to localhost:8080
2. **Server not running**: Start with `make start`
3. **Wrong port**: Verify port 8080 in server config
4. **Check URL**: Ensure using `http://localhost:8080/mcp` (not `https://` unless configured)

### Tools Not Appearing

**Problem:** Connected but no tools show up

**Solutions:**

1. **Check server logs**: Should show "tools/list" request
2. **Refresh Inspector**: Reload the browser page
3. **Check authentication**: Verify Bearer token is being sent
4. **Test with curl**:
   ```bash
   curl -H "Authorization: Bearer YOUR_JWT" http://localhost:8080/mcp
   ```

### CORS Errors

**Problem:** Browser console shows CORS errors

**Solution:** Server already has CORS enabled for all origins. If you still see errors:
1. Check that server is running
2. Clear browser cache
3. Try incognito/private mode

## Security Best Practices

### Development

✅ Use HTTP for local development (simpler setup)  
✅ Use short-lived tokens (default: 1 hour)  
✅ Never commit tokens to version control  
✅ Use `.env` files for sensitive data (added to `.gitignore`)  
✅ Test with DCR to ensure proper client registration  

### Production

❌ Never use HTTP in production  
✅ Use HTTPS with proper CA-signed certificates (Let's Encrypt)  
✅ Implement token refresh flow  
✅ Use secure token storage  
✅ Implement rate limiting (especially on `/register`)  
✅ Add comprehensive logging and monitoring  
✅ Use database for client registry (not in-memory)  
✅ Implement client secret rotation  

## Testing Flows

### Test OAuth Flow End-to-End

1. **Start server**: `make start`
2. **Start Inspector**: `make inspector`
3. **Connect**: Enter `http://localhost:8080/mcp`, click Connect
4. **Authenticate**: Sign in to GitHub when browser opens
5. **Verify**: Check that tools appear in Inspector

### Test Tool Calls

1. **Select tool**: `calculator_add`
2. **Set parameters**: `{"a": 15, "b": 27}`
3. **Call**: Click "Call Tool"
4. **Verify**: Result should be `42`

### Test Error Handling

1. **Invalid parameters**: Try calling `calculator_add` with `{"a": "not a number"}`
2. **Missing parameters**: Try calling without parameters
3. **Unknown tool**: Try calling a non-existent tool

## Implementation Details

### OAuth Flow

1. **Discovery**: Inspector fetches `/.well-known/oauth-protected-resource`
2. **Registration (Optional)**: Inspector registers via `/register` if DCR is supported
3. **Authorization**: User redirected to `/authorize` → GitHub → `/oauth/callback`
4. **Token Exchange**: Inspector exchanges code at `/token` for JWT
5. **MCP Access**: Inspector uses JWT to access `/mcp` endpoint

### Token Format

JWT tokens issued by the server contain:
```json
{
  "sub": "github_username",
  "iss": "http://localhost:8080",
  "iat": 1700000000,
  "exp": 1700003600,
  "scope": "read:mcp write:mcp"
}
```

### Client Registry

Registered clients are stored in-memory (development) or database (production):
```python
{
  "dcr_abc123...": {
    "client_id": "dcr_abc123...",
    "client_name": "MCP Inspector",
    "redirect_uris": ["http://localhost:6274/oauth/callback"],
    "client_id_issued_at": 1700000000
  }
}
```

## Additional Clients

### Python Agent (Automated OAuth)

```bash
make agent
```

The agent:
- Runs a local callback server on port 8888
- Opens browser for GitHub OAuth
- Automatically captures token
- No manual copy/paste needed!

### Python Client (Direct MCP)

```bash
make client
```

The client:
- Performs OAuth flow
- Lists all available tools
- Calls each tool with example parameters
- Shows results

## Additional Resources

- **MCP Specification**: https://modelcontextprotocol.io/
- **MCP Authorization**: https://modelcontextprotocol.io/docs/specification/authentication
- **MCP Inspector**: https://github.com/modelcontextprotocol/inspector
- **RFC 7591** (Dynamic Client Registration): https://www.rfc-editor.org/rfc/rfc7591
- **RFC 9728** (Protected Resource Metadata): https://www.rfc-editor.org/rfc/rfc9728
- **RFC 8414** (OAuth Server Metadata): https://www.rfc-editor.org/rfc/rfc8414
- **RFC 7636** (PKCE): https://www.rfc-editor.org/rfc/rfc7636
- **GitHub OAuth**: https://docs.github.com/en/developers/apps/building-oauth-apps

## Related Documentation

- [DYNAMIC_CLIENT_REGISTRATION.md](DYNAMIC_CLIENT_REGISTRATION.md) - Complete DCR documentation
- [OAUTH_FLOW.md](../OAUTH_FLOW.md) - Detailed OAuth flow documentation
- [SSL.md](SSL.md) - HTTPS setup with mkcert (optional)
- [README.md](../README.md) - MCP Auth example overview

## Support

For issues or questions:
- Check server logs for error messages
- Review Inspector browser console for client-side errors
- Test with `curl` to isolate server vs client issues
- Open an issue at https://github.com/datalayer/mcp-compose/issues
