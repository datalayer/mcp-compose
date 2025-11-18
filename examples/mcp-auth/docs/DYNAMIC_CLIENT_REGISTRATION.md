# Dynamic Client Registration (DCR)

## Overview

The MCP Auth server now supports **Dynamic Client Registration (DCR)** per RFC 7591. This allows OAuth clients to register themselves dynamically without requiring pre-configured client credentials.

## Benefits

### Before DCR
- ❌ Clients needed pre-shared `client_id` (e.g., "mcp-client", "claude-desktop")
- ❌ Server had to maintain a hardcoded list of known clients
- ❌ Each new client required server configuration changes
- ❌ Redirect URIs had to be configured in advance

### With DCR
- ✅ Clients register themselves on-the-fly
- ✅ No pre-configuration needed
- ✅ Server generates unique `client_id` for each registration
- ✅ Clients specify their own redirect URIs
- ✅ Perfect for dynamic clients like MCP Inspector

## How It Works

```
┌─────────────────┐
│   MCP Client    │
│  (e.g. Inspector)│
└────────┬─────────┘
         │
         │ 1. POST /register
         │    {
         │      "redirect_uris": ["http://localhost:6274/oauth/callback"],
         │      "client_name": "MCP Inspector"
         │    }
         ↓
┌──────────────────────────┐
│    MCP Server            │
│    (Authorization Server)│
└────────┬─────────────────┘
         │
         │ 2. Generates client_id
         │    Stores client metadata
         │
         ↓
         │ 3. Returns registration
         │    {
         │      "client_id": "dcr_abc123...",
         │      "redirect_uris": [...],
         │      ...
         │    }
         ↓
┌─────────────────┐
│   MCP Client    │
│  (Now Registered)│
└────────┬─────────┘
         │
         │ 4. Use client_id in OAuth flow
         │    GET /authorize?client_id=dcr_abc123...
         ↓
    [Normal OAuth Flow]
```

## Registration Endpoint

### POST /register

Registers a new OAuth client dynamically.

**Request:**

```bash
curl -X POST http://localhost:8080/register \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uris": ["http://localhost:6274/oauth/callback"],
    "client_name": "MCP Inspector",
    "client_uri": "https://github.com/modelcontextprotocol/inspector",
    "grant_types": ["authorization_code"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none"
  }'
```

**Request Body Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `redirect_uris` | array | **Yes** | List of valid redirect URIs |
| `client_name` | string | No | Human-readable client name |
| `client_uri` | string | No | URL of client's homepage |
| `logo_uri` | string | No | URL of client's logo |
| `scope` | string | No | Space-separated scopes (default: "openid read:mcp write:mcp") |
| `grant_types` | array | No | OAuth grant types (default: ["authorization_code"]) |
| `response_types` | array | No | OAuth response types (default: ["code"]) |
| `token_endpoint_auth_method` | string | No | Auth method (default: "none") |

**Response (201 Created):**

```json
{
  "client_id": "dcr_R7x3mK2pQnB8vYwT9zLcA1fE5hJ6sN4d",
  "client_id_issued_at": 1700000000,
  "redirect_uris": ["http://localhost:6274/oauth/callback"],
  "grant_types": ["authorization_code"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none",
  "client_name": "MCP Inspector",
  "client_uri": "https://github.com/modelcontextprotocol/inspector",
  "scope": "openid read:mcp write:mcp"
}
```

**Error Responses:**

```json
// Missing redirect_uris
{
  "error": "invalid_redirect_uri",
  "error_description": "redirect_uris is required and must be a non-empty array"
}

// Invalid JSON
{
  "error": "invalid_request",
  "error_description": "Invalid JSON in request body"
}

// Server error
{
  "error": "server_error",
  "error_description": "Internal server error during client registration"
}
```

## Client ID Format

DCR generates client IDs with the prefix `dcr_` followed by a cryptographically secure random string:

```
dcr_R7x3mK2pQnB8vYwT9zLcA1fE5hJ6sN4d
└─┬─┘└──────────────┬───────────────────┘
  │                  │
Prefix          Random token (32 bytes, URL-safe base64)
```

## Authorization Flow with DCR

### 1. Client Registration

```bash
# Step 1: Register the client
curl -X POST http://localhost:8080/register \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uris": ["http://localhost:9000/callback"],
    "client_name": "My MCP Client"
  }'

# Response:
# {
#   "client_id": "dcr_abc123...",
#   ...
# }
```

### 2. Authorization Request

```bash
# Step 2: Start OAuth flow with the registered client_id
GET /authorize?client_id=dcr_abc123...&redirect_uri=http://localhost:9000/callback&response_type=code&state=xyz&code_challenge=...&code_challenge_method=S256
```

### 3. Redirect URI Validation

The server validates that the `redirect_uri` in the authorization request matches one of the URIs registered during client registration.

```python
if redirect_uri not in client_metadata["redirect_uris"]:
    return error("invalid_request", "redirect_uri not registered for this client")
```

### 4. Complete OAuth Flow

After validation, the normal OAuth flow proceeds:

1. User authenticates with GitHub
2. Server issues authorization code
3. Client exchanges code for JWT token
4. Client uses JWT to access MCP endpoints

## Security Considerations

### Public Clients (token_endpoint_auth_method: "none")

- **No client_secret required** - Suitable for browser-based clients like MCP Inspector
- **PKCE required** - Code challenge prevents authorization code interception
- **Redirect URI validation** - Server strictly validates redirect URIs

### Confidential Clients (token_endpoint_auth_method: "client_secret_post")

- **client_secret issued** - Server generates a secret during registration
- **Secret required at /token** - Client must authenticate when exchanging code
- **More secure** - Suitable for server-side applications

### Production Security

**Current Implementation (Development)**:
- ✅ In-memory client registry (fast but non-persistent)
- ✅ Strict redirect URI validation
- ✅ PKCE support for public clients
- ⚠️ No rate limiting on /register
- ⚠️ No client authentication for registration endpoint

**Production Recommendations**:
- 🔒 Database-backed client registry (persistent storage)
- 🔒 Rate limiting on /register endpoint (prevent abuse)
- 🔒 Optional: Require authentication for registration (e.g., initial access token)
- 🔒 Client secret rotation support
- 🔒 Audit logging for all registrations
- 🔒 Client metadata validation (URL schemes, etc.)
- 🔒 Automatic cleanup of unused clients

## Examples

### MCP Inspector Registration

```bash
# MCP Inspector can register itself
curl -X POST http://localhost:8080/register \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uris": ["http://localhost:6274/oauth/callback"],
    "client_name": "MCP Inspector",
    "client_uri": "https://github.com/modelcontextprotocol/inspector",
    "token_endpoint_auth_method": "none"
  }'
```

### Python Client

```python
import requests

# Register the client
response = requests.post(
    "http://localhost:8080/register",
    json={
        "redirect_uris": ["http://localhost:8888/callback"],
        "client_name": "Python MCP Client",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none"
    }
)

registration = response.json()
client_id = registration["client_id"]

print(f"Registered client: {client_id}")

# Now use client_id in OAuth flow
auth_url = (
    f"http://localhost:8080/authorize"
    f"?client_id={client_id}"
    f"&redirect_uri=http://localhost:8888/callback"
    f"&response_type=code"
    f"&state=xyz"
    f"&code_challenge={code_challenge}"
    f"&code_challenge_method=S256"
)
```

### JavaScript Client

```javascript
// Register the client
const response = await fetch('http://localhost:8080/register', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    redirect_uris: ['http://localhost:3000/callback'],
    client_name: 'Web MCP Client',
    client_uri: 'https://example.com',
    token_endpoint_auth_method: 'none'
  })
});

const registration = await response.json();
const clientId = registration.client_id;

console.log('Registered client:', clientId);

// Use in OAuth flow
const authUrl = new URL('http://localhost:8080/authorize');
authUrl.searchParams.set('client_id', clientId);
authUrl.searchParams.set('redirect_uri', 'http://localhost:3000/callback');
authUrl.searchParams.set('response_type', 'code');
authUrl.searchParams.set('state', 'xyz');
authUrl.searchParams.set('code_challenge', codeChallenge);
authUrl.searchParams.set('code_challenge_method', 'S256');

window.location.href = authUrl.toString();
```

## Discovery

The authorization server metadata advertises DCR support:

```bash
curl http://localhost:8080/.well-known/oauth-authorization-server

# Response includes:
{
  "issuer": "http://localhost:8080",
  "authorization_endpoint": "http://localhost:8080/authorize",
  "token_endpoint": "http://localhost:8080/token",
  "registration_endpoint": "http://localhost:8080/register",
  ...
}
```

Clients can discover the registration endpoint automatically by fetching the authorization server metadata.

## Backward Compatibility

DCR is **fully backward compatible**:

- ✅ **Pre-configured clients still work** - Clients like "claude-desktop" or "mcp-client" work as before
- ✅ **Optional registration** - Registration is only validated if client_id exists in registry
- ✅ **Public client support** - Clients without pre-shared credentials work with or without DCR
- ✅ **Legacy agent/client** - agent.py and client.py continue to work with their existing flows

### Example: Pre-configured Client (Still Works)

```bash
# This still works without registration
GET /authorize?client_id=claude-desktop&redirect_uri=claude://oauth-callback&...
```

### Example: Dynamically Registered Client (New)

```bash
# 1. Register first
POST /register
Response: {"client_id": "dcr_abc123..."}

# 2. Then use in OAuth flow
GET /authorize?client_id=dcr_abc123...&redirect_uri=http://localhost:9000/callback&...
```

## Testing

### Test Registration

```bash
# Register a test client
curl -X POST http://localhost:8080/register \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uris": ["http://localhost:9999/callback"],
    "client_name": "Test Client"
  }' | jq

# Expected output:
# {
#   "client_id": "dcr_...",
#   "client_id_issued_at": 1700000000,
#   "redirect_uris": ["http://localhost:9999/callback"],
#   ...
# }
```

### Test Authorization with Registered Client

```bash
# Extract client_id from registration response
CLIENT_ID="dcr_..."

# Start OAuth flow
curl "http://localhost:8080/authorize?client_id=$CLIENT_ID&redirect_uri=http://localhost:9999/callback&response_type=code&state=test123&code_challenge=CHALLENGE&code_challenge_method=S256"

# Should redirect to GitHub for authentication
```

### Test Invalid Redirect URI

```bash
# Register with one URI
curl -X POST http://localhost:8080/register \
  -H "Content-Type: application/json" \
  -d '{"redirect_uris": ["http://localhost:9999/callback"], "client_name": "Test"}'

# Try to use different URI (should fail)
curl "http://localhost:8080/authorize?client_id=dcr_...&redirect_uri=http://evil.com/callback&..."

# Expected error:
# {
#   "error": "invalid_request",
#   "error_description": "redirect_uri not registered for this client. Registered URIs: http://localhost:9999/callback"
# }
```

## FAQ

### Q: Do I need to use DCR?

**A:** No, it's optional. Pre-configured clients still work. DCR is useful for dynamic clients that don't have pre-shared credentials.

### Q: Can I register the same redirect_uri multiple times?

**A:** Yes, each registration creates a new client_id. This is useful for testing or having multiple instances.

### Q: Is client_secret required?

**A:** Only if you specify `token_endpoint_auth_method` as something other than "none". For public clients (browser-based), use "none" and rely on PKCE.

### Q: How do I update client metadata?

**A:** Currently not supported. In production, implement PUT /register/{client_id} per RFC 7592 (Dynamic Client Registration Management).

### Q: How long do registrations last?

**A:** Currently, registrations are stored in memory and persist until server restart. In production, use a database for persistent storage.

### Q: Can I revoke a client registration?

**A:** Currently not supported. In production, implement DELETE /register/{client_id} per RFC 7592.

## References

- **RFC 7591**: OAuth 2.0 Dynamic Client Registration Protocol
- **RFC 7592**: OAuth 2.0 Dynamic Client Registration Management Protocol
- **RFC 7636**: Proof Key for Code Exchange (PKCE)
- **RFC 6749**: The OAuth 2.0 Authorization Framework

## Related Documentation

- [OAUTH_FLOW.md](../OAUTH_FLOW.md) - Complete OAuth flow documentation
- [CLAUDE_DESKTOP_SETUP.md](CLAUDE_DESKTOP_SETUP.md) - Claude Desktop setup guide
- [README.md](../README.md) - MCP Auth example overview
