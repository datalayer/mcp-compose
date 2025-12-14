<!--
  ~ Copyright (c) 2023-2024 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

[![Become a Sponsor](https://img.shields.io/static/v1?label=Become%20a%20Sponsor&message=%E2%9D%A4&logo=GitHub&style=flat&color=1ABC9C)](https://github.com/sponsors/datalayer)

# UI Example

This example demonstrates how to run MCP Compose with the Web UI enabled on port 9456.

## Features

- **Calculator MCP Server** - Basic math operations (add, subtract, multiply, divide)
- **Echo MCP Server** - Text manipulation tools (ping, echo, reverse, uppercase, lowercase, count_words)
- **Web UI** - React-based management interface on port 9456
- **Authentication** - Basic username/password authentication

## Configuration

The example includes:
- STDIO transport for local MCP servers
- Basic authentication with username/password
- Web UI on port 9456
- REST API on port 9456

## Prerequisites

```bash
# Install MCP Compose
pip install -e ../../

# Build the UI (from the ui directory)
cd ../../ui
npm install
npm run build
cd -
```

## Running the Example

```bash
# Start the composed server with UI
mcp-compose --config mcp_compose.toml
```

The service will start on port 9456:
- **Web UI**: http://localhost:9456/ui
- **API Docs**: http://localhost:9456/docs
- **API**: http://localhost:9456/api/v1

## Login Credentials

- **Username**: `admin`
- **Password**: `demo123`

## Testing

Once started, you can:

1. **Access the Web UI**: Navigate to http://localhost:9456/ui and login with the credentials above
2. **View servers**: See the Calculator and Echo servers in the dashboard
3. **Test tools**: Use the Tools page to invoke calculator or echo tools
4. **Monitor logs**: Check the Logs page to see server activity
5. **View metrics**: Monitor system metrics on the Metrics page

## Available Tools

### Calculator Server
- `calculator_add` - Add two numbers
- `calculator_subtract` - Subtract two numbers
- `calculator_multiply` - Multiply two numbers
- `calculator_divide` - Divide two numbers

### Echo Server
- `echo_ping` - Ping the server
- `echo_echo` - Echo back text
- `echo_reverse` - Reverse text
- `echo_uppercase` - Convert to uppercase
- `echo_lowercase` - Convert to lowercase
- `echo_count_words` - Count words in text

## Customization

You can modify `mcp_compose.toml` to:
- Change the UI port (default: 9456)
- Update authentication credentials
- Enable/disable features
- Add more MCP servers

## Troubleshooting

### UI not accessible
- Ensure the UI has been built: `cd ../../ui && npm run build`
- Check that port 9456 is not in use
- Verify the UI is enabled in the configuration

### Login fails
- Check the username and password in `mcp_compose.toml`
- Ensure authentication is enabled
- Check browser console for errors

### Servers not starting
- Verify Python is in your PATH
- Check that `mcp1.py` and `mcp2.py` are executable
- Review logs for error messages
