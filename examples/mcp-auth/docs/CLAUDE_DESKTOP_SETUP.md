# Claude Desktop Setup Guide

This guide explains how to connect Claude Desktop to the authenticated MCP server.

## ✅ Fixed: OAuth Flow for Claude Desktop

**Status:** The server now implements the correct OAuth flow that Claude Desktop expects:

1. **Self-issued JWT tokens**: Server acts as its own OAuth authorization server
2. **GitHub authentication**: User authenticates via GitHub, server issues JWT
3. **Standard OAuth 2.0 + PKCE**: Fully compliant with Claude Desktop requirements

## How It Works

```
┌─────────────┐           ┌──────────────┐           ┌─────────────┐
│   Claude    │──(1)──────│  MCP Server  │──(3)──────│   GitHub    │
│   Desktop   │   /mcp    │              │  GitHub   │    OAuth    │
└─────────────┘           └──────────────┘   OAuth   └─────────────┘
       │                          │                          │
       │  401 + discovery         │                          │
       │←─────(2)─────────────────│                          │
       │                          │                          │
       │  /authorize              │                          │
       │─────(4)──────────────────│                          │
       │                          │                          │
       │  redirect to GitHub      │                          │
       │←─────(5)─────────────────│                          │
       │                                                      │
       │  User authenticates                                 │
       │─────────────────(6)──────────────────────────────────▶
       │                                                      │
       │  GitHub callback with code                          │
       │◀─────────────────(7)─────────────────────────────────│
       │                          │                          │
       │  /oauth/callback         │                          │
       │─────(8)──────────────────│                          │
       │                          │  Exchange GH code        │
       │                          │─────(9)──────────────────▶
       │                          │                          │
       │                          │  GH user info            │
       │                          │◀────(10)─────────────────│
       │  auth code               │                          │
       │◀────(11)─────────────────│                          │
       │                          │                          │
       │  /token (exchange code)  │                          │
       │─────(12)─────────────────▶                          │
       │                          │                          │
       │  access_token (JWT)      │                          │
       │◀────(13)─────────────────│                          │
       │                          │                          │
       │  /mcp + Bearer JWT       │                          │
       │─────(14)─────────────────▶                          │
       │                          │                          │
       │  MCP tools/resources     │                          │
       │◀────(15)─────────────────│                          │
```

## Prerequisites

1. **HTTPS is Required**: Claude Desktop only connects to HTTPS endpoints
   - Follow [SSL.md](SSL.md) to set up mkcert certificates
   - Server must be running with `https://localhost:8080`

2. **GitHub OAuth App**: Register an OAuth app at https://github.com/settings/developers
   - Application name: "MCP Auth Example" (or your choice)
   - Homepage URL: `https://localhost:8080`
   - Authorization callback URL: `https://localhost:8080/oauth/callback`
   - Copy Client ID and Client Secret to `config.json`

## Quick Start (OAuth Flow)

### Step 1: Configure GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click "New OAuth App"
3. Fill in:
   - **Application name**: MCP Auth Example
   - **Homepage URL**: `https://localhost:8080`
   - **Authorization callback URL**: `https://localhost:8080/oauth/callback`
4. Click "Register application"
5. Copy the **Client ID**
6. Generate a new **Client Secret** and copy it

### Step 2: Update config.json

Edit `examples/mcp-auth/config.json`:

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

### Step 3: Start the Server with HTTPS

```bash
# Generate certificates (one-time setup)
cd examples/mcp-auth
mkcert localhost 127.0.0.1 ::1

# Start server
python -m mcp_auth_example.server
```

Verify the server shows:
```
🔒 HTTPS enabled with certificates
📋 Server URL: https://localhost:8080
� OAuth Metadata Endpoints:
   Protected Resource: https://localhost:8080/.well-known/oauth-protected-resource
   Authorization Server: https://localhost:8080/.well-known/oauth-authorization-server
```

### Step 4: Configure Claude Desktop

**IMPORTANT:** Claude Desktop's OAuth flow for local servers may redirect to Claude's OAuth proxy service.
For local development, you have two options:

#### Option A: Use Pre-generated Token (Recommended for Local Development)

1. Get a token using the client:
```bash
make client
# Or: python -m mcp_auth_example.client
```

2. Copy the GitHub token displayed in the browser

3. Configure Claude Desktop with the token:

**macOS:**
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```bash
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
~/.config/Claude/claude_desktop_config.json
```

Add configuration:

```json
{
  "mcpServers": {
    "github-auth-mcp": {
      "url": "https://localhost:8080/mcp",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer YOUR_GITHUB_TOKEN_HERE"
      }
    }
  }
}
```

Replace `YOUR_GITHUB_TOKEN_HERE` with the token from step 2.

#### Option B: Try OAuth Discovery (May Not Work for Localhost)

```json
{
  "mcpServers": {
    "github-auth-mcp": {
      "url": "https://localhost:8080/mcp",
      "transport": "streamable-http"
    }
  }
}
```

**Note:** Claude Desktop may redirect to `claude.ai/api/organizations/.../mcp/start-auth/...` which cannot reach localhost servers. If this happens, use Option A instead.

### Step 5: Connect in Claude Desktop

1. Open Claude Desktop
2. Go to Settings → Developer → MCP Servers
3. You should see "github-auth-mcp" listed
4. Click "Connect"
5. **Browser opens automatically** for GitHub authentication
6. Sign in to GitHub and authorize the application
7. You're redirected back - Claude Desktop is now connected!

### Step 6: Verify Connection

In Claude Desktop chat:

```
You: What is 15 + 27?
Claude: [Uses calculator_add tool] The answer is 42.

You: Say hello to Alice
Claude: [Uses greeter_hello tool] Hello, Alice! Welcome to the authenticated MCP server!
```

## Verification

### Test Server Discovery

Claude Desktop will perform OAuth discovery when connecting:

```bash
# Test 401 response with WWW-Authenticate header
curl -i https://localhost:8080/mcp

# Expected response:
# HTTP/1.1 401 Unauthorized
# WWW-Authenticate: Bearer realm="mcp", resource_metadata="https://localhost:8080/.well-known/oauth-protected-resource", scope="read:all write:all"
```

### Test Protected Resource Metadata

```bash
curl https://localhost:8080/.well-known/oauth-protected-resource

# Expected response:
# {
#   "resource": "https://localhost:8080",
#   "authorization_servers": ["https://localhost:8080"],
#   "bearer_methods_supported": ["header"],
#   "scopes_supported": ["read:all", "write:all"],
#   "resource_documentation": "..."
# }
```

### Test Authorization Server Metadata

```bash
curl https://localhost:8080/.well-known/oauth-authorization-server

# Expected response:
# {
#   "issuer": "https://localhost:8080",
#   "authorization_endpoint": "https://github.com/login/oauth/authorize",
#   "token_endpoint": "https://github.com/login/oauth/access_token",
#   "code_challenge_methods_supported": ["S256"],
#   ...
# }
```

### Test Authenticated Connection

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://localhost:8080/mcp

# Should return 200 OK and establish MCP connection
```

## Claude Desktop OAuth Flow (Advanced)

For a more seamless experience, Claude Desktop can perform the OAuth flow automatically if configured correctly.

### Requirements

The current implementation **proxies to GitHub OAuth**, which means:

✅ OAuth discovery metadata is exposed (`.well-known` endpoints)  
✅ WWW-Authenticate header includes `resource_metadata` parameter  
✅ Authorization endpoints point to GitHub  
⚠️ Client credentials must be configured in Claude Desktop settings  

### Configuration with OAuth Client Credentials

```json
{
  "mcpServers": {
    "github-auth-mcp": {
      "url": "https://localhost:8080/mcp",
      "transport": "streamable-http",
      "oauth": {
        "client_id": "YOUR_GITHUB_OAUTH_APP_CLIENT_ID",
        "client_secret": "YOUR_GITHUB_OAUTH_APP_CLIENT_SECRET",
        "scopes": ["user"]
      }
    }
  }
}
```

**Note:** This requires:
1. A GitHub OAuth App registered at https://github.com/settings/developers
2. Callback URL configured: `claude://oauth-callback` (or Claude's redirect URI)
3. Client ID and Secret from your OAuth app

### Interactive OAuth Flow

When Claude Desktop connects:

1. **Discovery**: Fetches `/.well-known/oauth-protected-resource`
2. **Authorization**: Redirects user to GitHub authorization page
3. **Callback**: Receives authorization code
4. **Token Exchange**: Exchanges code for access token
5. **Connection**: Connects to `/mcp` with Bearer token

## Available MCP Tools

Once connected, Claude Desktop can use these tools:

- **calculator_add** - Add two numbers
- **calculator_multiply** - Multiply two numbers  
- **greeter_hello** - Greet someone
- **greeter_goodbye** - Say goodbye
- **get_server_info** - Get server information

### Example Usage in Claude Desktop

```
User: What is 15 plus 27?
Claude: [Uses calculator_add(a=15, b=27)] 
        The answer is 42.

User: Say hello to Alice
Claude: [Uses greeter_hello(name="Alice")]
        Hello, Alice! Welcome to the authenticated MCP server!
```

## Troubleshooting

### Claude Desktop Can't Connect

**Check 1: Is HTTPS enabled?**
```bash
curl https://localhost:8080/health
# Should NOT show certificate errors
```

**Check 2: Is the server running?**
```bash
lsof -i :8080
# Should show Python process
```

**Check 3: Is the token valid?**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.github.com/user
# Should return your GitHub user info
```

**Check 4: Check Claude Desktop logs**

**macOS:**
```bash
tail -f ~/Library/Logs/Claude/claude.log
```

**Windows:**
```bash
type %LOCALAPPDATA%\Claude\logs\claude.log
```

**Linux:**
```bash
tail -f ~/.config/Claude/logs/claude.log
```

### 401 Unauthorized Error

**Problem:** Claude Desktop shows "Authentication failed"

**Solutions:**

1. **Token expired**: Get a new token using `make client`
2. **Invalid token format**: Ensure `Bearer ` prefix is NOT in config (added automatically)
3. **Wrong token**: Use token from GitHub, not a random string
4. **Token scope**: Ensure token has `user` scope

### Connection Timeout

**Problem:** Claude Desktop shows "Connection timeout"

**Solutions:**

1. **Check firewall**: Allow connections to localhost:8080
2. **Check HTTPS**: Verify certificates are trusted
3. **Server not running**: Start with `make server`
4. **Wrong port**: Verify port 8080 in both server and config

### Tools Not Appearing

**Problem:** MCP server connected but no tools show up

**Solutions:**

1. **Check server logs**: Should show "tools/list" request
2. **Restart Claude**: Completely quit and reopen
3. **Clear cache**: Remove `claude_desktop_config.json`, restart, re-add
4. **Check permissions**: Token must have required scopes

### Certificate Errors

**Problem:** "Certificate not trusted" or "SSL error"

**Solution:** Follow [SSL.md](SSL.md) to properly install mkcert CA:
```bash
mkcert -install
mkcert localhost 127.0.0.1 ::1
```

## Security Best Practices

### Development

✅ Use mkcert for local HTTPS  
✅ Use short-lived tokens (refresh regularly)  
✅ Never commit tokens to version control  
✅ Use `.env` files for sensitive data (added to `.gitignore`)  

### Production

❌ Never use mkcert certificates in production  
✅ Use proper CA-signed certificates (Let's Encrypt)  
✅ Implement token refresh flow  
✅ Use secure token storage (OS keychain)  
✅ Implement rate limiting  
✅ Add comprehensive logging and monitoring  

## Implementation Checklist (for MCP Server Developers)

This server implements all Claude Desktop requirements:

- [x] **HTTPS endpoint** - Uses mkcert for local development
- [x] **401 with WWW-Authenticate** - Returns proper discovery header
- [x] **resource_metadata parameter** - Points to `.well-known/oauth-protected-resource`
- [x] **scope parameter** - Declares `read:all write:all` scopes
- [x] **Protected Resource Metadata** - RFC 9728 compliant
- [x] **Authorization Server Metadata** - RFC 8414 compliant
- [x] **OAuth 2.0 + PKCE** - GitHub OAuth with PKCE support
- [x] **Bearer token validation** - Validates with GitHub API
- [x] **MCP over HTTP Streaming** - NDJSON transport
- [x] **Tool discovery** - Exposes tools via MCP protocol

## Additional Resources

- **MCP Specification**: https://modelcontextprotocol.io/
- **MCP Authorization**: https://modelcontextprotocol.io/docs/specification/authentication
- **Claude Desktop MCP**: https://docs.anthropic.com/claude/docs/mcp
- **RFC 9728** (Protected Resource Metadata): https://www.rfc-editor.org/rfc/rfc9728
- **RFC 8414** (OAuth Server Metadata): https://www.rfc-editor.org/rfc/rfc8414
- **GitHub OAuth**: https://docs.github.com/en/developers/apps/building-oauth-apps

## Support

For issues or questions:
- Check [troubleshooting.md](docs/troubleshooting.md)
- Review server logs
- Open an issue at https://github.com/datalayer/mcp-compose/issues
