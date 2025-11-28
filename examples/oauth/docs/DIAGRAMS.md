# Visual Diagrams

This file contains ASCII art diagrams to help visualize the authentication flow.

## Complete OAuth2 Flow with MCP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: DISCOVERY                                   │
└─────────────────────────────────────────────────────────────────────────────┘

   Client                        MCP Server                      GitHub
     │                                │                             │
     │  1. GET /tools                 │                             │
     ├───────────────────────────────>│                             │
     │  (no Authorization header)     │                             │
     │                                │                             │
     │  2. 401 Unauthorized           │                             │
     │  WWW-Authenticate: Bearer      │                             │
     │<───────────────────────────────┤                             │
     │                                │                             │
     │  3. GET /.well-known/          │                             │
     │     oauth-protected-resource   │                             │
     ├───────────────────────────────>│                             │
     │                                │                             │
     │  4. Protected Resource         │                             │
     │     Metadata (RFC 9728)        │                             │
     │<───────────────────────────────┤                             │
     │  {                             │                             │
     │    "authorization_servers": [  │                             │
     │      "http://localhost:8080"   │                             │
     │    ]                           │                             │
     │  }                             │                             │
     │                                │                             │
     │  5. GET /.well-known/          │                             │
     │     oauth-authorization-server │                             │
     ├───────────────────────────────>│                             │
     │                                │                             │
     │  6. Auth Server Metadata       │                             │
     │     (RFC 8414)                 │                             │
     │<───────────────────────────────┤                             │
     │  {                             │                             │
     │    "authorization_endpoint":   │                             │
     │      "https://github.com/...", │                             │
     │    "token_endpoint":           │                             │
     │      "https://github.com/..."  │                             │
     │  }                             │                             │
     │                                │                             │


┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 2: AUTHENTICATION                                 │
└─────────────────────────────────────────────────────────────────────────────┘

   Client                        MCP Server                      GitHub
     │                                │                             │
     │  7. Generate PKCE              │                             │
     │     code_verifier = random()   │                             │
     │     code_challenge = SHA256()  │                             │
     │                                │                             │
     │  8. Open Browser               │                             │
     │     Authorization URL          │                             │
     │     + code_challenge           │                             │
     │     + resource parameter       │                             │
     ├─────────────────────────────────────────────────────────────>│
     │                                │                             │
     │  9. User Authorizes                                          │
     │<─────────────────────────────────────────────────────────────┤
     │                                │                             │
     │  10. Redirect with code        │                             │
     │<─────────────────────────────────────────────────────────────┤
     │                                │                             │
     │  11. POST /oauth/token         │                             │
     │      + authorization_code      │                             │
     │      + code_verifier           │                             │
     ├─────────────────────────────────────────────────────────────>│
     │                                │                             │
     │  12. Verify PKCE               │                             │
     │      SHA256(verifier) ==       │                             │
     │      challenge?                │                             │
     │                                │                             │
     │  13. Access Token              │                             │
     │<─────────────────────────────────────────────────────────────┤
     │  {                             │                             │
     │    "access_token": "gho_...",  │                             │
     │    "token_type": "bearer"      │                             │
     │  }                             │                             │
     │                                │                             │


┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 3: AUTHENTICATED ACCESS                            │
└─────────────────────────────────────────────────────────────────────────────┘

   Client                        MCP Server                      GitHub
     │                                │                             │
     │  14. GET /tools                │                             │
     │      Authorization: Bearer ... │                             │
     ├───────────────────────────────>│                             │
     │                                │                             │
     │                                │  15. Validate Token         │
     │                                │  GET /user                  │
     │                                │  Authorization: Bearer ...  │
     │                                ├────────────────────────────>│
     │                                │                             │
     │                                │  16. User Info              │
     │                                │<────────────────────────────┤
     │                                │  {                          │
     │                                │    "login": "octocat",      │
     │                                │    "id": 123,               │
     │                                │    ...                      │
     │                                │  }                          │
     │                                │                             │
     │  17. List of Tools             │                             │
     │<───────────────────────────────┤                             │
     │  {                             │                             │
     │    "tools": [                  │                             │
     │      {"name": "calculator:add"},                             │
     │      {"name": "greeter:hello"} │                             │
     │    ]                           │                             │
     │  }                             │                             │
     │                                │                             │
     │  18. POST /tools/calculator:add│                             │
     │      Authorization: Bearer ... │                             │
     │      {"a": 5, "b": 3}          │                             │
     ├───────────────────────────────>│                             │
     │                                │                             │
     │                                │  19. Validate Token         │
     │                                │  (cached from step 15)      │
     │                                │                             │
     │  20. Tool Result               │                             │
     │<───────────────────────────────┤                             │
     │  {                             │                             │
     │    "result": 8,                │                             │
     │    "user": "octocat"           │                             │
     │  }                             │                             │
     │                                │                             │
```

## PKCE (Proof Key for Code Exchange) Detail

```
┌───────────────────────────────────────────────────────────────────┐
│                  Without PKCE (Vulnerable)                        │
└───────────────────────────────────────────────────────────────────┘

Client                    Attacker                     GitHub
  │                          │                            │
  │ 1. Request auth code     │                            │
  ├──────────────────────────────────────────────────────>│
  │                          │                            │
  │ 2. Redirect with code    │                            │
  │<──────────────────────────────────────────────────────┤
  │   http://app?code=ABC    │                            │
  │                          │                            │
  │        *** Attacker intercepts code ABC ***           │
  │                          │                            │
  │                          │ 3. Exchange code for token │
  │                          ├───────────────────────────>│
  │                          │    code=ABC                │
  │                          │                            │
  │                          │ 4. Access token            │
  │                          │<───────────────────────────┤
  │                          │                            │
  │                          │ ❌ Attacker has access!    │


┌───────────────────────────────────────────────────────────────────┐
│                   With PKCE (Protected)                           │
└───────────────────────────────────────────────────────────────────┘

Client                    Attacker                     GitHub
  │                          │                            │
  │ 1. Generate verifier     │                            │
  │    verifier = random()   │                            │
  │    challenge = SHA256(v) │                            │
  │                          │                            │
  │ 2. Request auth code     │                            │
  │    + challenge           │                            │
  ├──────────────────────────────────────────────────────>│
  │                          │                            │
  │                          │    Store: code=ABC,        │
  │                          │           challenge=XYZ    │
  │                          │                            │
  │ 3. Redirect with code    │                            │
  │<──────────────────────────────────────────────────────┤
  │   http://app?code=ABC    │                            │
  │                          │                            │
  │        *** Attacker intercepts code ABC ***           │
  │                          │                            │
  │                          │ 4. Exchange code           │
  │                          │    code=ABC                │
  │                          │    verifier=???            │
  │                          ├───────────────────────────>│
  │                          │                            │
  │                          │    Verify:                 │
  │                          │    SHA256(verifier) ==     │
  │                          │    stored challenge?       │
  │                          │    ❌ NO! Reject!          │
  │                          │                            │
  │                          │ 5. Error: invalid verifier │
  │                          │<───────────────────────────┤
  │                          │                            │
  │ 6. Exchange code         │                            │
  │    code=ABC              │                            │
  │    verifier=original     │                            │
  ├──────────────────────────────────────────────────────>│
  │                          │                            │
  │                          │    Verify:                 │
  │                          │    SHA256(verifier) ==     │
  │                          │    stored challenge?       │
  │                          │    ✅ YES!                 │
  │                          │                            │
  │ 7. Access token          │                            │
  │<──────────────────────────────────────────────────────┤
  │                          │                            │
  │ ✅ Legitimate client has access                       │
```

## Token Validation Flow

```
┌───────────────────────────────────────────────────────────────────┐
│              Every Request Validates Token                        │
└───────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │   Request   │
                              │  with Token │
                              └──────┬──────┘
                                     │
                                     v
                        ┌────────────────────────┐
                        │  Extract Token from    │
                        │  Authorization Header  │
                        └────────────┬───────────┘
                                     │
                                     v
                          ┌──────────────────┐
                          │  Check Cache     │
                          │  for Token?      │
                          └────┬─────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                  Found              Not Found
                    │                     │
                    v                     v
          ┌─────────────────┐   ┌──────────────────┐
          │  Return Cached  │   │  Call GitHub API │
          │   User Info     │   │  /user endpoint  │
          └────────┬────────┘   └────────┬─────────┘
                   │                     │
                   │           ┌─────────┴──────────┐
                   │           │                    │
                   │       Success                Error
                   │           │                    │
                   │           v                    v
                   │  ┌─────────────────┐  ┌────────────┐
                   │  │  Cache User Info│  │  Return    │
                   │  │  & Return       │  │  401 Error │
                   │  └────────┬────────┘  └────────────┘
                   │           │
                   └───────────┴──────────┐
                                          │
                                          v
                              ┌───────────────────┐
                              │  Process Request  │
                              │  with User Context│
                              └───────────────────┘
```

## Token Binding with Resource Parameter

```
┌───────────────────────────────────────────────────────────────────┐
│          Without Resource Parameter (Vulnerable)                  │
└───────────────────────────────────────────────────────────────────┘

    Token issued for ANY service
    ↓
    ┌─────────────────────────┐
    │  Access Token           │
    │  {                      │
    │    "scope": "user",     │
    │    "aud": null          │  ← No audience!
    │  }                      │
    └─────────────────────────┘
    ↓
    Token can be used at:
    • MCP Server A ✓
    • MCP Server B ✓  ← Unintended!
    • Any other service ✓  ← Security issue!


┌───────────────────────────────────────────────────────────────────┐
│            With Resource Parameter (Protected)                    │
└───────────────────────────────────────────────────────────────────┘

    Authorization Request includes:
    resource=http://localhost:8080
    ↓
    ┌─────────────────────────────────┐
    │  Access Token                   │
    │  {                              │
    │    "scope": "user",             │
    │    "aud": "http://localhost:8080" │  ← Bound to server!
    │  }                              │
    └─────────────────────────────────┘
    ↓
    Token validation:
    • MCP Server (localhost:8080) ✓  ← Matches audience
    • Other MCP Server ✗  ← Rejected!
    • Other services ✗  ← Rejected!
```

## Request Headers Comparison

```
┌───────────────────────────────────────────────────────────────────┐
│                  Unauthenticated Request                          │
└───────────────────────────────────────────────────────────────────┘

GET /tools HTTP/1.1
Host: localhost:8080
User-Agent: Python/3.x
Accept: application/json

                            ↓

HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="http://localhost:8080/.well-known/oauth-protected-resource"
Content-Type: application/json

{
  "error": "unauthorized",
  "error_description": "Authentication required"
}


┌───────────────────────────────────────────────────────────────────┐
│                   Authenticated Request                           │
└───────────────────────────────────────────────────────────────────┘

GET /tools HTTP/1.1
Host: localhost:8080
User-Agent: Python/3.x
Accept: application/json
Authorization: Bearer gho_abc123def456xyz789  ← Token included!

                            ↓

HTTP/1.1 200 OK
Content-Type: application/json

{
  "tools": [
    {"name": "calculator:add", "description": "Add two numbers"},
    {"name": "greeter:hello", "description": "Greet someone"}
  ]
}
```

## Architecture Components

```
┌────────────────────────────────────────────────────────────────────┐
│                         System Architecture                        │
└────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │                         MCP Client                              │
  │                   (mcp_oauth_example/client.py)                       │
  │  ┌──────────────────────────────────────────────────────────┐  │
  │  │  OAuth2 Flow Manager                                      │  │
  │  │  • Metadata discovery                                     │  │
  │  │  • PKCE generation                                        │  │
  │  │  • Browser automation                                     │  │
  │  │  • Token management                                       │  │
  │  └──────────────────────────────────────────────────────────┘  │
  │  ┌──────────────────────────────────────────────────────────┐  │
  │  │  HTTP Client                                              │  │
  │  │  • Request builder                                        │  │
  │  │  • Token injection                                        │  │
  │  │  • Response parser                                        │  │
  │  └──────────────────────────────────────────────────────────┘  │
  └────────────────────────┬───────────────────────────────────────┘
                           │
                           │ HTTPS (Bearer Token)
                           │
  ┌────────────────────────┴───────────────────────────────────────┐
  │                        MCP Server                              │
  │                   (mcp_oauth_example/server.py)                      │
  │  ┌──────────────────────────────────────────────────────────┐  │
  │  │  HTTP Request Handler                                     │  │
  │  │  • Route management                                       │  │
  │  │  • Metadata endpoints                                     │  │
  │  │  • Error handling                                         │  │
  │  └──────────────────────────────────────────────────────────┘  │
  │  ┌──────────────────────────────────────────────────────────┐  │
  │  │  Token Validator                                          │  │
  │  │  • Extract token from header                             │  │
  │  │  • Validate with GitHub                                  │  │
  │  │  • Cache validation results                              │  │
  │  └──────────────────────────────────────────────────────────┘  │
  │  ┌──────────────────────────────────────────────────────────┐  │
  │  │  MCP Tools                                                │  │
  │  │  • calculator:add                                        │  │
  │  │  • calculator:multiply                                   │  │
  │  │  • greeter:hello                                         │  │
  │  │  • greeter:goodbye                                       │  │
  │  └──────────────────────────────────────────────────────────┘  │
  └────────────────────────┬───────────────────────────────────────┘
                           │
                           │ HTTPS (Token Validation)
                           │
  ┌────────────────────────┴───────────────────────────────────────┐
  │                    GitHub OAuth Server                         │
  │                   (api.github.com)                             │
  │  • Authorization endpoint                                      │
  │  • Token endpoint                                              │
  │  • User API (/user)                                            │
  │  • Token validation                                            │
  └────────────────────────────────────────────────────────────────┘
```

## Key Takeaways

1. **Discovery First**: Client discovers OAuth endpoints before authentication
2. **PKCE Always**: Use PKCE to protect authorization codes
3. **Resource Binding**: Bind tokens to specific servers
4. **Validate Every Request**: Never trust client-provided tokens
5. **Use Headers**: Always use Authorization header, never URL parameters
6. **Stateless**: Server doesn't store sessions, validates with GitHub
7. **User Context**: Server knows who is making requests

## Learn More

- Read the full README.md for detailed explanations
- Check FLOW_EXPLAINED.md for step-by-step breakdown
- Follow QUICKSTART.md to get running in 5 minutes
