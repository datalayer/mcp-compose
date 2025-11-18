# Claude Desktop OAuth Limitation for Localhost

## Issue

When configuring Claude Desktop to connect to a local MCP server (`https://localhost:8080/mcp`) with OAuth authentication, Claude Desktop redirects to its own OAuth proxy service:

```
https://claude.ai/api/organizations/{org-id}/mcp/start-auth/{session-id}?redirect_url=claude://...&open_in_browser=1
```

This happens even though the server correctly implements:
- ✅ OAuth metadata discovery endpoints (`/.well-known/oauth-protected-resource`)
- ✅ Proper 401 response with `WWW-Authenticate` header
- ✅ Complete OAuth 2.0 + PKCE flow
- ✅ All required endpoints (`/authorize`, `/token`, `/oauth/callback`)

## Why This Happens

Claude Desktop uses its own OAuth proxy service (`claude.ai/api/...`) to handle OAuth flows. This service:

1. **Acts as an intermediary** between Claude Desktop and the OAuth provider
2. **Works great for public servers** (e.g., `https://api.example.com`)
3. **Cannot reach localhost servers** because Claude's service runs in the cloud

The flow Claude Desktop attempts:
```
Claude Desktop → claude.ai OAuth proxy → https://localhost:8080 (fails - cannot reach localhost)
```

## Workaround for Local Development

For local development with localhost servers, use a pre-generated token instead of OAuth discovery:

### Step 1: Generate a Token

Use the included client to get a GitHub token:

```bash
make client
# Or: python -m mcp_auth_example.client
```

This will:
1. Open your browser for GitHub OAuth
2. Display the token in the browser
3. Automatically copy it to clipboard

### Step 2: Configure Claude Desktop with Token

Edit Claude Desktop's config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`  
**Linux:** `~/.config/Claude/claude_desktop_config.json`

Add the token to headers:

```json
{
  "mcpServers": {
    "github-auth-mcp": {
      "url": "https://localhost:8080/mcp",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer gho_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

### Step 3: Restart Claude Desktop

Completely quit and restart Claude Desktop for changes to take effect.

## When OAuth Discovery Works

OAuth discovery (without pre-configured tokens) works when:

✅ **Server is publicly accessible** (e.g., `https://api.mycompany.com`)  
✅ **Server has valid SSL certificate** (not self-signed)  
✅ **Claude's OAuth proxy can reach the server**  

For production deployment, the OAuth flow will work automatically without manual token configuration.

## Production Deployment

For production, deploy your MCP server to a public URL with proper SSL:

```json
{
  "mcpServers": {
    "github-auth-mcp": {
      "url": "https://mcp.example.com/mcp",
      "transport": "streamable-http"
    }
  }
}
```

Claude Desktop will:
1. Detect the 401 with WWW-Authenticate header
2. Fetch OAuth metadata from `/.well-known/oauth-protected-resource`
3. Use its OAuth proxy to facilitate the flow
4. Successfully connect with the obtained token

## Alternative: Use HTTP (Not Recommended)

You could configure the server to use HTTP instead of HTTPS for local development:

```json
{
  "mcpServers": {
    "github-auth-mcp": {
      "url": "http://localhost:8080/mcp",
      "transport": "streamable-http"
    }
  }
}
```

**However:**
- ⚠️ Claude Desktop may still redirect to its OAuth proxy
- ⚠️ Less secure (no encryption)
- ⚠️ Doesn't match production environment
- ⚠️ Not recommended for development

## Summary

**For localhost development:**
- Use pre-generated tokens in `headers.Authorization`
- Tokens can be obtained via `make client` or `make agent`
- This bypasses Claude Desktop's OAuth proxy

**For production deployment:**
- Use public HTTPS URLs
- OAuth discovery works automatically
- No manual token configuration needed

## Testing

To verify your token works:

```bash
# Test with curl
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -k https://localhost:8080/mcp

# Should return 200 OK and start MCP session
```

## Related Documentation

- [CLAUDE_DESKTOP_SETUP.md](CLAUDE_DESKTOP_SETUP.md) - Complete setup guide
- [SSL.md](SSL.md) - HTTPS setup with mkcert
- [OAUTH_CALLBACK_UPDATE.md](OAUTH_CALLBACK_UPDATE.md) - OAuth flow details
