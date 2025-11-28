# HTTPS/SSL Setup for MCP Server

## Why HTTPS is Required

### Claude Desktop Requirement

**Claude Desktop requires HTTPS connections** when connecting to MCP servers. This is a security requirement that cannot be bypassed:

- Claude Desktop will **refuse to connect** to `http://` URLs
- Only `https://` URLs are accepted for MCP server connections
- This applies even to `localhost` connections
- Self-signed certificates are **not trusted** by default

### Security Benefits

HTTPS provides essential security features:
- **Encryption**: All communication between Claude Desktop and the MCP server is encrypted
- **Authentication**: Certificates verify the server's identity
- **Integrity**: Prevents man-in-the-middle attacks and tampering

## Solution: mkcert for Local Development

For local development, **mkcert** is the recommended solution. It creates locally-trusted SSL certificates that work seamlessly with Claude Desktop and browsers.

### Why mkcert?

✅ **Trusted by System**: Installs a local Certificate Authority (CA) in your system's trust store  
✅ **Works with Claude Desktop**: Certificates are automatically trusted  
✅ **Works with Browsers**: Chrome, Firefox, Safari, Edge all trust these certificates  
✅ **Zero Configuration**: No certificate warnings or security bypasses needed  
✅ **Free and Open Source**: No cost, widely used by developers  
✅ **Simple to Use**: Just two commands to get HTTPS working  

### Alternative Solutions (Not Recommended)

| Solution | Pros | Cons |
|----------|------|------|
| **Self-signed certificates** | Free, quick to generate | ❌ Not trusted by default<br>❌ Requires manual trust configuration<br>❌ Security warnings in browsers |
| **ngrok/tunneling** | Real domain with valid cert | ❌ Requires internet connection<br>❌ External service dependency<br>❌ Potential latency |
| **Production certificates** | Fully trusted everywhere | ❌ Requires public domain<br>❌ Complex setup for localhost<br>❌ Unnecessary for development |

## Installation and Setup

### Step 1: Install mkcert

**Linux:**
```bash
# Download latest mkcert
curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
chmod +x mkcert-v*-linux-amd64
sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert

# Verify installation
mkcert --version
```

**macOS:**
```bash
brew install mkcert
brew install nss  # For Firefox support
```

**Windows:**
```powershell
# Using Chocolatey
choco install mkcert

# Or download from: https://github.com/FiloSottile/mkcert/releases
```

### Step 2: Install Local CA

This installs mkcert's certificate authority in your system's trust store:

```bash
mkcert -install
```

Output:
```
Created a new local CA 💥
The local CA is now installed in the system trust store! ⚡️
The local CA is now installed in the Firefox and/or Chrome/Chromium trust store! 🦊
```

### Step 3: Generate Certificates

Navigate to your project directory and generate certificates:

```bash
cd /path/to/mcp-compose/examples/mcp-oauth
mkcert localhost 127.0.0.1 ::1
```

This creates two files:
- `localhost+2.pem` - SSL certificate
- `localhost+2-key.pem` - Private key

Output:
```
Created a new certificate valid for the following names 📜
 - "localhost"
 - "127.0.0.1"
 - "::1"

The certificate is at "./localhost+2.pem" and the key at "./localhost+2-key.pem" ✅

It will expire on 18 February 2028 🗓
```

### Step 4: Start the Server

The MCP server automatically detects the certificates and enables HTTPS:

```bash
make server
# Or: python -m mcp_oauth_example.server
```

You should see:
```
🔒 HTTPS enabled with certificates:
   Certificate: /path/to/localhost+2.pem
   Key: /path/to/localhost+2-key.pem

======================================================================
🔐 MCP Server with GitHub OAuth2 Authentication
======================================================================

📋 Server Information:
   Server URL: https://localhost:8080
   MCP Transport: HTTP Streaming (NDJSON)
   Authentication: GitHub OAuth2
```

## Using with Claude Desktop

### Configure MCP Server in Claude Desktop

Edit your Claude Desktop configuration file:

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

### Configuration Example

```json
{
  "mcpServers": {
    "github-auth-mcp": {
      "url": "https://localhost:8080/mcp",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer YOUR_GITHUB_TOKEN"
      }
    }
  }
}
```

**Important:** Replace `YOUR_GITHUB_TOKEN` with a valid OAuth token obtained through the authentication flow.

## Verification

### Test HTTPS Connection

```bash
# Should return 401 (authentication required)
curl -k https://localhost:8080/mcp

# With authentication
curl -H "Authorization: Bearer YOUR_TOKEN" https://localhost:8080/mcp
```

### Test in Browser

Visit: `https://localhost:8080/`

You should see:
- ✅ No certificate warnings
- ✅ Valid HTTPS padlock icon
- ✅ Server information page loads

### Test with Claude Desktop

1. Start the MCP server: `make server`
2. Configure Claude Desktop (see above)
3. Restart Claude Desktop
4. Claude should connect without errors
5. MCP tools should appear in Claude's interface

## Troubleshooting

### Certificate Not Trusted

**Problem:** Browser shows security warning despite using mkcert

**Solution:**
```bash
# Reinstall the local CA
mkcert -uninstall
mkcert -install

# Regenerate certificates
rm localhost+2*.pem
mkcert localhost 127.0.0.1 ::1

# Restart browser/Claude Desktop
```

### Server Not Using HTTPS

**Problem:** Server starts with HTTP instead of HTTPS

**Solution:**
```bash
# Check certificates exist
ls -la localhost+2*.pem

# Should show both files:
# -rw------- 1 user user 1598 Nov 18 10:30 localhost+2-key.pem
# -rw-r--r-- 1 user user 1468 Nov 18 10:30 localhost+2.pem

# If missing, regenerate:
mkcert localhost 127.0.0.1 ::1
```

### Claude Desktop Can't Connect

**Problem:** Claude Desktop shows connection error

**Checklist:**
1. ✅ Server is running: `curl https://localhost:8080/`
2. ✅ HTTPS is enabled: Look for "🔒 HTTPS enabled" in server logs
3. ✅ Token is valid: Test with curl using Bearer token
4. ✅ Config file syntax is correct: Validate JSON
5. ✅ Port is correct: Default is 8080
6. ✅ Restart Claude Desktop after config changes

### Permission Denied on Linux

**Problem:** `mkcert -install` fails with permission error

**Solution:**
```bash
# Run with sudo for system trust store installation
sudo mkcert -install

# Verify
mkcert -CAROOT
```

## Certificate Management

### View Certificate Information

```bash
# View certificate details
openssl x509 -in localhost+2.pem -text -noout

# Check expiration date
openssl x509 -in localhost+2.pem -noout -dates
```

### Renew Certificates

Certificates expire after 825 days (just over 2 years). To renew:

```bash
# Remove old certificates
rm localhost+2*.pem

# Generate new ones
mkcert localhost 127.0.0.1 ::1

# Restart server
make server
```

### Remove mkcert CA (Uninstall)

```bash
# Remove local CA from system trust store
mkcert -uninstall

# Remove certificate files
rm localhost+2*.pem

# Optional: Remove mkcert binary
sudo rm /usr/local/bin/mkcert  # Linux
brew uninstall mkcert           # macOS
```

## Security Considerations

### Development Only

⚠️ **mkcert is for local development only**

- Never use mkcert certificates in production
- The CA private key is stored locally without encryption
- Anyone with access to your CA can create trusted certificates for your machine

### Production Deployment

For production environments:
- Use **Let's Encrypt** for free, automated SSL certificates
- Use **AWS Certificate Manager** for AWS deployments
- Use **Caddy** for automatic HTTPS with built-in certificate management
- Use proper domain names (not localhost)

### Token Security

- Never commit certificates to version control
- Add `*.pem` to `.gitignore`
- Rotate OAuth tokens regularly
- Use environment variables for sensitive data in production

## Additional Resources

- **mkcert GitHub**: https://github.com/FiloSottile/mkcert
- **Let's Encrypt**: https://letsencrypt.org/ (for production)
- **SSL/TLS Best Practices**: https://wiki.mozilla.org/Security/Server_Side_TLS
- **MCP Specification**: https://modelcontextprotocol.io/
- **Claude Desktop MCP Setup**: https://docs.anthropic.com/claude/docs/mcp

## Summary

1. **Install mkcert**: One-time setup per machine
2. **Generate certificates**: `mkcert localhost 127.0.0.1 ::1`
3. **Start server**: Automatically uses HTTPS if certificates exist
4. **Configure Claude Desktop**: Use `https://localhost:8080/mcp`
5. **Enjoy secure local development** with zero certificate warnings! 🎉
