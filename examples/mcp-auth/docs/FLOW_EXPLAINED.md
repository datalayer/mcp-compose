# Understanding the MCP Authorization Flow

This document provides a detailed, step-by-step explanation of how authentication works in this example.

## Overview

The MCP (Model Context Protocol) Authorization specification defines how clients authenticate with servers using OAuth2. This example demonstrates the complete flow using GitHub as the OAuth provider.

## Key Concepts

### 1. Protected Resource
- The **MCP Server** is a protected resource that requires authentication
- It exposes tools (calculator, greeter) that need authorization to access
- Without a valid token, requests return `401 Unauthorized`

### 2. Authorization Server
- **GitHub** acts as the authorization server
- It authenticates users and issues access tokens
- The MCP server validates tokens with GitHub

### 3. OAuth Client
- The **MCP Client** is the OAuth client
- It requests authorization on behalf of the user
- It manages tokens and makes authenticated requests

## Detailed Flow

### Phase 1: Discovery

#### Step 1.1: Client Makes Unauthenticated Request

```http
GET /tools HTTP/1.1
Host: localhost:8080
```

**What happens:**
- Client tries to access tools without authentication
- Server checks for `Authorization` header
- No header found → return 401

#### Step 1.2: Server Returns 401 with Metadata

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="http://localhost:8080/.well-known/oauth-protected-resource"
Content-Type: application/json

{
  "error": "unauthorized",
  "error_description": "Authentication required",
  "metadata_url": "http://localhost:8080/.well-known/oauth-protected-resource"
}
```

**What happens:**
- Server returns 401 status
- `WWW-Authenticate` header tells client where to find metadata
- This follows RFC 9728 (Protected Resource Metadata)

#### Step 1.3: Client Fetches Protected Resource Metadata

```http
GET /.well-known/oauth-protected-resource HTTP/1.1
Host: localhost:8080
```

**Response:**
```json
{
  "resource": "http://localhost:8080",
  "authorization_servers": ["http://localhost:8080"],
  "bearer_methods_supported": ["header"],
  "resource_documentation": "https://github.com/datalayer/mcp-compose"
}
```

**What happens:**
- Client learns which authorization server(s) protect this resource
- The `authorization_servers` field is critical for next step
- This follows RFC 9728

#### Step 1.4: Client Fetches Authorization Server Metadata

```http
GET /.well-known/oauth-authorization-server HTTP/1.1
Host: localhost:8080
```

**Response:**
```json
{
  "issuer": "http://localhost:8080",
  "authorization_endpoint": "https://github.com/login/oauth/authorize",
  "token_endpoint": "https://github.com/login/oauth/access_token",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code"],
  "code_challenge_methods_supported": ["S256"],
  "token_endpoint_auth_methods_supported": ["client_secret_post"]
}
```

**What happens:**
- Client learns OAuth endpoints (where to authorize, where to get tokens)
- Client learns supported features (PKCE with S256)
- This follows RFC 8414

### Phase 2: Authentication

#### Step 2.1: Generate PKCE Parameters

**Code Verifier:**
```python
# Random 32-byte value, base64url encoded
code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32))
# Example: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
```

**Code Challenge:**
```python
# SHA256 hash of verifier, base64url encoded
digest = hashlib.sha256(code_verifier.encode()).digest()
code_challenge = base64.urlsafe_b64encode(digest)
# Example: "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
```

**Why PKCE?**
- Prevents authorization code interception attacks
- Required by MCP spec for public clients
- Even if attacker steals the code, they can't use it without the verifier

#### Step 2.2: Build Authorization URL

```python
params = {
    "client_id": "Iv1.abc123def456",
    "redirect_uri": "http://localhost:8080/callback",
    "response_type": "code",
    "scope": "user",
    "state": "random_csrf_token_xyz789",
    "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
    "code_challenge_method": "S256",
    "resource": "http://localhost:8080"  # RFC 8707: Resource Indicators
}

url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
```

**Key Parameters:**
- `client_id`: Identifies the OAuth app
- `redirect_uri`: Where GitHub sends user after authorization
- `state`: CSRF protection token
- `code_challenge`: PKCE challenge
- `resource`: Binds token to specific MCP server (RFC 8707)

#### Step 2.3: User Authorizes in Browser

```
Browser → GitHub: GET /login/oauth/authorize?client_id=...&code_challenge=...
```

**What happens:**
1. Client opens browser with authorization URL
2. User sees GitHub authorization page
3. User reviews permissions (read user profile)
4. User clicks "Authorize"
5. GitHub validates request parameters

#### Step 2.4: GitHub Redirects with Authorization Code

```
GitHub → Browser: 302 Redirect to http://localhost:8080/callback?code=abc123&state=xyz789
Browser → Client: GET /callback?code=abc123&state=xyz789
```

**What happens:**
- GitHub generates one-time authorization code
- Redirects browser to callback URL
- Client's callback server receives the code
- Client verifies state parameter matches (CSRF protection)

#### Step 2.5: Exchange Code for Token

```http
POST /login/oauth/access_token HTTP/1.1
Host: github.com
Content-Type: application/x-www-form-urlencoded
Accept: application/json

client_id=Iv1.abc123def456
&client_secret=secret123
&code=abc123
&redirect_uri=http://localhost:8080/callback
&code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
&grant_type=authorization_code
```

**Response:**
```json
{
  "access_token": "gho_abc123def456xyz789",
  "token_type": "bearer",
  "scope": "user"
}
```

**What happens:**
- Client sends authorization code + code verifier to GitHub
- GitHub verifies:
  - Code is valid and not expired
  - SHA256(code_verifier) matches original code_challenge
  - Client credentials are correct
- GitHub issues access token
- Token is bound to the resource (MCP server)

### Phase 3: Authenticated Access

#### Step 3.1: Client Makes Authenticated Request

```http
GET /tools HTTP/1.1
Host: localhost:8080
Authorization: Bearer gho_abc123def456xyz789
```

**What happens:**
- Client includes access token in Authorization header
- This follows OAuth 2.1 requirements

#### Step 3.2: Server Validates Token

```python
def validate_token(token: str) -> Optional[Dict]:
    # Verify token with GitHub
    response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        return response.json()  # User info
    return None  # Invalid token
```

**What happens:**
- Server extracts token from Authorization header
- Server validates token with GitHub API
- If valid, GitHub returns user information
- Server caches validation result

#### Step 3.3: Server Returns Protected Resource

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "tools": [
    {
      "name": "calculator:add",
      "description": "Add two numbers",
      "parameters": {...}
    },
    ...
  ]
}
```

**What happens:**
- Token is valid → server processes request
- Returns list of available tools
- User can now invoke tools

#### Step 3.4: Invoke Tool

```http
POST /tools/calculator:add HTTP/1.1
Host: localhost:8080
Authorization: Bearer gho_abc123def456xyz789
Content-Type: application/json

{
  "a": 5,
  "b": 3
}
```

**Response:**
```json
{
  "result": 8,
  "user": "octocat",
  "authenticated_at": "Octocat GitHub User"
}
```

**What happens:**
- Server validates token again (every request)
- Server executes tool with parameters
- Server includes user context in response

## Security Features

### 1. PKCE (Proof Key for Code Exchange)

**Problem:** Authorization code interception
- Attacker intercepts authorization code
- Attacker tries to exchange it for token

**Solution:** PKCE
- Client generates random verifier
- Client sends SHA256(verifier) as challenge
- Attacker can't compute verifier from challenge (one-way hash)
- Token exchange requires original verifier

### 2. State Parameter

**Problem:** CSRF attacks
- Attacker tricks user into authorizing attacker's request
- Authorization code sent to victim's callback

**Solution:** State parameter
- Client generates random state
- Client includes state in authorization URL
- Client verifies state in callback matches
- Attacker can't predict correct state value

### 3. Resource Parameter (RFC 8707)

**Problem:** Token reuse across services
- Token issued for Service A
- Attacker uses token at Service B
- Service B accepts token (no audience validation)

**Solution:** Resource parameter
- Client specifies target resource in OAuth request
- Token is bound to specific MCP server
- Other services can't accept the token

### 4. Token Validation

**Problem:** Stolen tokens
- Attacker steals access token
- Attacker makes requests to MCP server

**Solution:** Token validation
- Server validates every token with GitHub
- Expired/revoked tokens rejected immediately
- No trust in client-provided tokens

### 5. Bearer Token in Header

**Problem:** Token exposure in URLs
- Tokens in query strings appear in logs
- Tokens cached in browser history

**Solution:** Authorization header
- Token only in Authorization header
- Never in URL or query parameters
- Follows OAuth 2.1 requirements

## Token Lifecycle

```
1. Issue
   GitHub issues token after successful authorization
   Token has limited lifetime (typically 8 hours)

2. Use
   Client includes token in every request
   Server validates token with GitHub

3. Cache
   Server caches validation results
   Reduces API calls to GitHub

4. Expire
   Token expires after lifetime
   Client must re-authenticate

5. Revoke (optional)
   User can revoke token in GitHub settings
   Immediate effect - validation fails
```

## Comparison to Traditional Auth

### Traditional Session-Based Auth
```
1. User submits username/password
2. Server creates session
3. Server returns session cookie
4. Client sends cookie with requests
5. Server validates session
```

**Issues with sessions:**
- Server must maintain session state
- Doesn't scale across services
- Hard to delegate to other services

### OAuth2 with MCP
```
1. User authorizes via OAuth provider
2. Client receives access token
3. Client sends token with requests
4. Server validates token with provider
5. Stateless - no session storage needed
```

**Benefits:**
- Stateless - servers don't store sessions
- Delegated authentication
- Works across multiple services
- User manages access via OAuth provider

## Error Handling

### Invalid Token
```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="..."

{
  "error": "unauthorized",
  "error_description": "Invalid or expired token"
}
```

### Missing Parameters
```http
HTTP/1.1 400 Bad Request

{
  "error": "error",
  "error_description": "Missing parameter: a"
}
```

### Tool Not Found
```http
HTTP/1.1 404 Not Found

{
  "error": "error",
  "error_description": "Tool not found: unknown:tool"
}
```

## References

- **MCP Authorization Spec**: https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
- **OAuth 2.1**: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13
- **RFC 7636 - PKCE**: https://datatracker.ietf.org/doc/html/rfc7636
- **RFC 8707 - Resource Indicators**: https://www.rfc-editor.org/rfc/rfc8707.html
- **RFC 9728 - Protected Resource Metadata**: https://datatracker.ietf.org/doc/html/rfc9728
- **RFC 8414 - Authorization Server Metadata**: https://datatracker.ietf.org/doc/html/rfc8414

## Summary

This flow demonstrates:

1. ✅ **Discovery**: How clients find OAuth endpoints
2. ✅ **PKCE**: How to protect authorization codes
3. ✅ **Resource Binding**: How tokens are bound to servers
4. ✅ **Token Validation**: How servers verify tokens
5. ✅ **Authenticated Access**: How tools are protected

You now understand the complete MCP authorization flow! 🎓
