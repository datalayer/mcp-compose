# Setting Up GitHub OAuth App

This guide shows you how to create a GitHub OAuth application to use with the MCP authentication example.

## Prerequisites

- A GitHub account
- 5 minutes of your time

## Step-by-Step Instructions

### 1. Navigate to GitHub Developer Settings

Go to: **https://github.com/settings/developers**

Or manually:
1. Click your profile picture (top-right)
2. Settings → Developer settings → OAuth Apps

### 2. Create New OAuth App

Click the **"New OAuth App"** button.

### 3. Fill in Application Details

| Field | Value | Notes |
|-------|-------|-------|
| **Application name** | `MCP Auth Example` | Or any name you prefer |
| **Homepage URL** | `http://localhost:8080` | Your server's base URL |
| **Authorization callback URL** | `http://localhost:8081/callback` | Client callback listener (port 8081) |
| **Application description** | *(optional)* | Brief description of your app |

### 4. Register the Application

Click **"Register application"**.

### 5. Get Your Credentials

1. Copy the **Client ID** (visible immediately)
2. Click **"Generate a new client secret"**
3. Copy the **Client Secret** (shown only once!)

⚠️ **Important**: Save your client secret immediately - GitHub will only show it once.

### 6. Configure Your Application

Edit `config.json` in the example directory:

```json
{
  "github": {
    "client_id": "Iv1.abc123def456",
    "client_secret": "...."
  },
  "server": {
    "host": "localhost",
    "port": 8080
  }
}
```

Replace `client_id` and `client_secret` with your actual values.

## Security Best Practices

- ✅ **Never commit** `config.json` to version control
- ✅ Use `.gitignore` to exclude sensitive files (already configured)
- ✅ Regenerate secrets if accidentally exposed
- ✅ Use different OAuth apps for development and production
- ✅ Restrict callback URLs in production environments

## Troubleshooting

### "redirect_uri_mismatch" Error

**Cause**: The callback URL doesn't match your OAuth app settings.

**Solution**: 
1. Go to your OAuth app settings on GitHub
2. Verify the callback URL is exactly: `http://localhost:8081/callback`
3. Note: The client runs its own callback listener on port 8081 (server uses 8080)
4. No trailing slashes, correct port, correct protocol (http vs https)

### "Bad verification code" Error

**Cause**: Authorization code expired or already used.

**Solution**: Restart the authentication flow (codes expire quickly).

### "Invalid client" Error

**Cause**: Wrong client_id or client_secret in config.json.

**Solution**: Double-check credentials from GitHub OAuth app settings.

## Production Deployment

When deploying to production:

1. Create a **separate** OAuth app for production
2. Use your production domain in Homepage URL and Callback URL
   - Example: `https://yourdomain.com` and `https://yourdomain.com/callback`
3. Use HTTPS (required for production)
4. Store secrets in environment variables or secret management system
5. Never use localhost URLs in production OAuth apps

## Additional Resources

- [GitHub OAuth Apps Documentation](https://docs.github.com/en/developers/apps/building-oauth-apps)
- [OAuth 2.1 Specification](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13)
- [MCP Authorization Specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)

## Next Steps

Once you have your OAuth app configured:

1. Return to the [QUICKSTART.md](QUICKSTART.md) to run the example
2. Read [FLOW_EXPLAINED.md](FLOW_EXPLAINED.md) to understand the authentication process
3. Explore [IMPLEMENTATION.md](IMPLEMENTATION.md) for technical details
