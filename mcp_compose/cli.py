"""
MCP Compose CLI.

Command-line interface for managing MCP servers.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from .composer import ConflictResolution, MCPServerComposer
from .config_loader import load_config, find_config_file
from .discovery import MCPServerDiscovery
from .exceptions import MCPComposerError
from .process_manager import ProcessManager

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def setup_otel_tracing(service_name: str = "mcp-compose", out=sys.stderr) -> Optional[Any]:
    """
    Set up OpenTelemetry tracing for the mcp-compose server.
    
    Reads configuration from environment variables:
        DATALAYER_LOGFIRE_TOKEN   - Logfire write token (required for tracing)
        DATALAYER_LOGFIRE_PROJECT - Logfire project name (for display)
        DATALAYER_LOGFIRE_URL     - Logfire URL (default: https://logfire-us.pydantic.dev)
    
    Args:
        service_name: Name of the service for tracing
        out: Output stream for status messages (stderr for STDIO mode)
    
    Returns:
        TracerProvider if tracing is enabled, None otherwise
    """
    token = os.environ.get("DATALAYER_LOGFIRE_TOKEN")
    if not token:
        return None
    
    project = os.environ.get("DATALAYER_LOGFIRE_PROJECT", "starter-project")
    url = os.environ.get("DATALAYER_LOGFIRE_URL", "https://logfire-us.pydantic.dev")
    
    try:
        from .otel import setup_otel
        
        print(f"\n📊 OpenTelemetry tracing enabled", file=out)
        print(f"   Endpoint: {url}/v1/traces", file=out)
        
        # Use the core setup_otel function
        provider, tracer = setup_otel(
            service_name=service_name,
            token=token,
            project=project,
            url=url,
            instrument=True,
        )
        
        # Create a startup span
        span = tracer.start_span('mcp-compose.server.startup')
        span.set_attribute("service.name", service_name)
        span.end()
        
        # Flush to send the startup span
        provider.force_flush()
        
        print(f"   Traces: {url}/datalayer/{project}", file=out)
        print(file=out)
        
        return provider
        
    except ImportError:
        logger.debug("OpenTelemetry not available, tracing disabled")
        return None
    except ValueError as e:
        # Token missing - already checked above, shouldn't happen
        logger.debug(f"OTEL setup skipped: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to setup OpenTelemetry: {e}")
        return None


def compose_command(args: argparse.Namespace) -> int:
    """Handle the compose command."""
    try:
        # Create composer
        composer = MCPServerComposer(
            composed_server_name=args.name,
            conflict_resolution=ConflictResolution(args.conflict_resolution),
        )

        # Compose servers
        composed_server = composer.compose_from_pyproject(
            pyproject_path=args.pyproject,
            include_servers=args.include,
            exclude_servers=args.exclude,
        )

        # Get composition summary
        summary = composer.get_composition_summary()

        # Output results
        if args.output_format == "json":
            print(json.dumps(summary, indent=2))
        else:
            print_summary(summary)

        # Save server if requested
        if args.output:
            save_composed_server(composed_server, args.output)
            print(f"Composed server saved to: {args.output}")

        return 0

    except MCPComposerError as e:
        print(f"Composition error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def discover_command(args: argparse.Namespace) -> int:
    """Handle the discover command."""
    try:
        discovery = MCPServerDiscovery()
        discovered = discovery.discover_from_pyproject(args.pyproject)

        if args.output_format == "json":
            # Convert MCPServerInfo objects to dictionaries
            serializable = {}
            for name, info in discovered.items():
                serializable[name] = {
                    "package_name": info.package_name,
                    "version": info.version,
                    "tools": list(info.tools.keys()),
                    "prompts": list(info.prompts.keys()),
                    "resources": list(info.resources.keys()),
                }
            print(json.dumps(serializable, indent=2))
        else:
            print_discovery_results(discovered)

        return 0

    except MCPComposerError as e:
        print(f"Discovery error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def print_summary(summary: dict) -> None:
    """Print composition summary in human-readable format."""
    print(f"Composed Server: {summary['composed_server_name']}")
    print(f"Conflict Resolution: {summary['conflict_resolution_strategy']}")
    print()
    print("Composition Results:")
    print(f"  Tools: {summary['total_tools']}")
    print(f"  Prompts: {summary['total_prompts']}")
    print(f"  Resources: {summary['total_resources']}")
    print(f"  Source Servers: {summary['source_servers']}")
    print(f"  Conflicts Resolved: {summary['conflicts_resolved']}")

    if summary["conflict_details"]:
        print("\nConflict Resolutions:")
        for conflict in summary["conflict_details"]:
            if conflict["type"] in ["prefix", "suffix"]:
                print(
                    f"  {conflict['component_type'].title()}: "
                    f"'{conflict['original_name']}' -> '{conflict['resolved_name']}' "
                    f"(from {conflict['server_name']})"
                )
            elif conflict["type"] == "override":
                print(
                    f"  {conflict['component_type'].title()}: "
                    f"'{conflict['name']}' overridden from {conflict['previous_source']} "
                    f"to {conflict['new_source']}"
                )


def print_discovery_results(discovered: dict) -> None:
    """Print discovery results in human-readable format."""
    if not discovered:
        print("No MCP servers discovered.")
        return

    print(f"Discovered {len(discovered)} MCP servers:")
    print()

    for name, info in discovered.items():
        print(f"Server: {name}")
        print(f"  Package: {info.package_name} (v{info.version})")
        print(f"  Tools: {len(info.tools)}")
        print(f"  Prompts: {len(info.prompts)}")
        print(f"  Resources: {len(info.resources)}")
        
        if info.tools:
            print(f"    Tool names: {', '.join(info.tools.keys())}")
        if info.prompts:
            print(f"    Prompt names: {', '.join(info.prompts.keys())}")
        if info.resources:
            print(f"    Resource names: {', '.join(info.resources.keys())}")
        print()


def save_composed_server(server, output_path: str) -> None:
    """Save the composed server to a file."""
    # This is a placeholder - actual implementation would depend on
    # how FastMCP servers can be serialized/saved
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract tools safely
    tools = []
    try:
        if hasattr(server, "_tool_manager") and hasattr(server._tool_manager, "_tools"):
            tool_dict = server._tool_manager._tools
            if hasattr(tool_dict, "keys"):
                tools = list(tool_dict.keys())
    except (AttributeError, TypeError):
        tools = []
    
    # Extract server name safely
    server_name = "unknown"
    try:
        name = getattr(server, "name", None)
        if name is not None:
            server_name = str(name)
    except (AttributeError, TypeError):
        server_name = "unknown"
    
    # For now, just save the server information
    server_info = {
        "name": server_name,
        "tools": tools,
        "composed_at": "2024-01-01T00:00:00Z",  # Would use actual timestamp
    }
    
    output_file.write_text(json.dumps(server_info, indent=2))


def _load_oauth_overrides_from_config_json(config_path: Optional[str]) -> dict:
    """Load OAuth secrets/endpoints from config.json next to the TOML config."""
    overrides: dict = {}
    if not config_path:
        return overrides
    try:
        config_dir = Path(config_path).resolve().parent
    except Exception:
        return overrides
    json_path = config_dir / "config.json"
    if not json_path.exists():
        return overrides
    try:
        with json_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        logger.warning("Failed to read %s: %s", json_path, exc)
        return overrides
    provider_block = {}
    if isinstance(data, dict):
        if isinstance(data.get("oauth"), dict):
            provider_block = data["oauth"]
        elif isinstance(data.get("github"), dict):
            provider_block = data["github"]
        else:
            provider_block = data
    if not isinstance(provider_block, dict):
        return overrides
    for key in (
        "client_id",
        "client_secret",
        "authorization_endpoint",
        "token_endpoint",
        "userinfo_endpoint",
    ):
        value = provider_block.get(key)
        if value:
            overrides[key] = value
    return overrides


def serve_command(args: argparse.Namespace) -> int:
    """Handle the serve command."""
    try:
        # Find or use specified config file
        if args.config:
            config_path = Path(args.config)
        else:
            config_path = find_config_file()
            if config_path is None:
                print("Error: No configuration file found.", file=sys.stderr)
                print("Create mcp_compose.toml in current directory or use --config", file=sys.stderr)
                return 1
        
        print(f"Loading configuration from: {config_path}", file=sys.stderr)
        config = load_config(config_path)
        args.config_path = str(config_path)
        
        # Run the server
        return asyncio.run(run_server(config, args))
        
    except MCPComposerError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


async def run_server(config, args: argparse.Namespace) -> int:
    """Run the MCP Compose."""
    from .config import StdioProxiedServerConfig, AuthProvider
    from .composer import MCPServerComposer, ConflictResolution
    from .tool_proxy import ToolProxy
    from .auth import create_authenticator, AuthType
    from .api.dependencies import set_authenticator
    
    # Determine transport mode from CLI args or config
    transport_mode = getattr(args, 'transport', None)
    if transport_mode is None:
        # Determine from config
        if config.transport.stdio_enabled and not config.transport.streamable_http_enabled and not config.transport.sse_enabled:
            transport_mode = "stdio"
        elif config.transport.streamable_http_enabled:
            transport_mode = "streamable-http"
        elif config.transport.sse_enabled:
            transport_mode = "sse"
        else:
            transport_mode = "streamable-http"  # Default to streamable-http
    
    # In STDIO mode, all status output MUST go to stderr
    # Only JSON-RPC messages should go to stdout
    out = sys.stderr if transport_mode == "stdio" else sys.stdout
    
    # Setup OpenTelemetry tracing if configured via environment variables
    otel_provider = setup_otel_tracing(service_name=config.composer.name, out=out)
    
    import uvicorn
    
    # Initialize authenticator if authentication is enabled
    authenticator = None
    resolved_oauth_config = None
    if config.authentication.enabled:
        print(f"\n🔐 Authentication enabled", file=out)
        print(f"   Provider: {config.authentication.default_provider}", file=out)
        
        # Create authenticator based on provider
        provider = config.authentication.default_provider
        
        if provider == AuthProvider.ANACONDA:
            if config.authentication.anaconda:
                domain = config.authentication.anaconda.domain
                print(f"   Domain: {domain}", file=out)
                authenticator = create_authenticator(
                    AuthType.ANACONDA,
                    domain=domain
                )
            else:
                print("   ⚠️  Warning: Anaconda auth config missing, using defaults", file=out)
                authenticator = create_authenticator(AuthType.ANACONDA)
        elif provider == AuthProvider.API_KEY:
            if config.authentication.api_key:
                authenticator = create_authenticator(
                    AuthType.API_KEY,
                    api_keys={}  # Would load from config
                )
            else:
                print("   ⚠️  Warning: API Key auth config missing", file=out)
        elif provider == AuthProvider.OAUTH2:
            if config.authentication.oauth2:
                oauth2_config = config.authentication.oauth2
                overrides = _load_oauth_overrides_from_config_json(
                    getattr(args, "config_path", None)
                )
                applied_updates = {}
                for field in (
                    "client_id",
                    "client_secret",
                    "authorization_endpoint",
                    "token_endpoint",
                    "userinfo_endpoint",
                ):
                    current = getattr(oauth2_config, field, None)
                    if current:
                        continue
                    override_value = overrides.get(field)
                    if override_value:
                        applied_updates[field] = override_value
                if applied_updates:
                    oauth2_config = oauth2_config.model_copy(update=applied_updates)
                    config_path_str = getattr(args, "config_path", None)
                    if config_path_str:
                        json_path = Path(config_path_str).resolve().parent / "config.json"
                        print(
                            f"   Loaded OAuth secrets from {json_path}",
                            file=out,
                        )
                print(f"   Provider: {oauth2_config.provider}", file=out)
                if oauth2_config.issuer_url:
                    print(f"   Issuer: {oauth2_config.issuer_url}", file=out)
                if oauth2_config.userinfo_endpoint:
                    print(f"   UserInfo: {oauth2_config.userinfo_endpoint}", file=out)
                
                authenticator = create_authenticator(
                    AuthType.OAUTH2,
                    provider=oauth2_config.provider,
                    issuer_url=oauth2_config.issuer_url,
                    userinfo_endpoint=oauth2_config.userinfo_endpoint,
                    introspection_endpoint=oauth2_config.introspection_endpoint,
                    client_id=oauth2_config.client_id,
                    client_secret=oauth2_config.client_secret,
                    audience=oauth2_config.audience,
                    required_scopes=oauth2_config.required_scopes,
                    user_id_claim=oauth2_config.user_id_claim,
                    redirect_uri=oauth2_config.redirect_uri,
                    scopes=oauth2_config.scopes,
                )
                resolved_oauth_config = oauth2_config
            else:
                print("   ⚠️  Warning: OAuth2 auth config missing", file=out)
        else:
            print(f"   ⚠️  Warning: Provider {provider} not yet implemented", file=out)
        
        if authenticator:
            set_authenticator(authenticator)
            print(f"   ✓ Authenticator initialized", file=out)
        print(file=out)
    
    # Create process manager
    process_manager = ProcessManager(auto_restart=False)
    
    # Create discovery with config directory as project root for embedded server imports
    from .discovery import MCPServerDiscovery
    config_dir = Path(args.config_path).parent
    discovery = MCPServerDiscovery(project_root=config_dir)
    
    # Create composer
    conflict_strategy = ConflictResolution.PREFIX
    if hasattr(config.composer, 'conflict_resolution'):
        # Convert from ConflictResolutionStrategy (config) to ConflictResolution (composer)
        config_strategy = config.composer.conflict_resolution
        conflict_strategy = ConflictResolution(config_strategy.value)
    
    composer = MCPServerComposer(
        composed_server_name=config.composer.name,
        conflict_resolution=conflict_strategy,
        discovery=discovery,
        config=config,
        use_process_manager=True,
    )
    composer.process_manager = process_manager
    
    # Create tool proxy for STDIO communication
    tool_proxy = ToolProxy(process_manager, composer)
    
    try:
        # Start process manager
        await process_manager.start()
        
        print(f"\n🚀 MCP Compose: {config.composer.name}", file=out)
        print(f"Conflict Resolution: {config.composer.conflict_resolution}", file=out)
        print(f"Log Level: {config.composer.log_level}", file=out)
        print(file=out)
        
        # Check if any servers are configured
        has_embedded = (hasattr(config, 'servers') and 
                       hasattr(config.servers, 'embedded') and 
                       hasattr(config.servers.embedded, 'servers') and 
                       config.servers.embedded.servers)
        has_stdio = (hasattr(config, 'servers') and 
                    hasattr(config.servers, 'proxied') and 
                    hasattr(config.servers.proxied, 'stdio') and 
                    config.servers.proxied.stdio)
        
        if not has_embedded and not has_stdio:
            print("⚠️  No servers configured in mcp_compose.toml", file=out)
            print(file=out)
            return 1
        
        # Handle embedded servers using compose_from_config
        if has_embedded:
            print(f"📦 Composing {len(config.servers.embedded.servers)} embedded servers...", file=out)
            await composer.compose_from_config(config)
            print(f"   ✓ Embedded servers composed", file=out)
            print(file=out)
        
        # Add and start all configured STDIO servers
        if has_stdio:
            stdio_servers = config.servers.proxied.stdio
            
            print(f"Starting {len(stdio_servers)} server(s)...", file=out)
            print(file=out)
            
            for server_config in stdio_servers:
                if isinstance(server_config, StdioProxiedServerConfig):
                    # command is already a List[str] in the config
                    command = server_config.command
                    
                    print(f"  • {server_config.name}", file=out)
                    print(f"    Command: {' '.join(command)}", file=out)
                    if server_config.env:
                        print(f"    Environment: {list(server_config.env.keys())}", file=out)
                    
                    # Add process
                    process = await process_manager.add_process(
                        name=server_config.name,
                        command=command,
                        env=server_config.env,
                        auto_start=True
                    )
                    
                    # Discover tools from the server
                    await tool_proxy.discover_tools(server_config.name, process)
                    
                    print(f"    Status: ✓ Started", file=out)
                    print(file=out)
        
        # Handle SSE proxied servers
        if hasattr(config, 'servers') and hasattr(config.servers, 'proxied') and hasattr(config.servers.proxied, 'sse'):
            from .config import SseProxiedServerConfig
            from mcp import ClientSession
            from mcp.client.sse import sse_client
            
            sse_servers = config.servers.proxied.sse
            
            if sse_servers:
                print(f"Connecting to {len(sse_servers)} SSE server(s)...", file=out)
                print(file=out)
                
                for server_config in sse_servers:
                    if isinstance(server_config, SseProxiedServerConfig):
                        print(f"  • {server_config.name}", file=out)
                        print(f"    URL: {server_config.url}", file=out)
                        
                        # Try to discover tools from the SSE server using MCP protocol
                        try:
                            # Connect to SSE server using MCP client
                            async with sse_client(server_config.url) as (read, write):
                                async with ClientSession(read, write) as session:
                                    # Initialize the session
                                    await session.initialize()
                                    
                                    # List tools using MCP protocol
                                    tools_result = await session.list_tools()
                                    tools = tools_result.tools
                                    
                                    # Store the number of tools before registration
                                    tools_discovered = len(tools)
                                    logger.info(f"Discovered {tools_discovered} tools from SSE server {server_config.name}")
                                    
                            # Register tools in composer (moved outside the ClientSession context)
                            # This ensures tools are registered even if there's a cleanup issue
                            if 'tools' in locals() and tools:
                                logger.info(f"Registering {len(tools)} tools from SSE server {server_config.name}")
                                
                                for tool in tools:
                                    tool_name = f"{server_config.name}_{tool.name}"
                                    
                                    # Extract input schema
                                    input_schema = {}
                                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                                        input_schema = tool.inputSchema
                                    
                                    tool_def = {
                                        'name': tool.name,  # Use original name for MCP protocol
                                        'description': tool.description if hasattr(tool, 'description') else '',
                                        'inputSchema': input_schema,
                                    }
                                    
                                    # Create a proxy function for this SSE tool
                                    def make_sse_proxy(sse_url: str, original_tool_name: str):
                                        """Create a proxy function that calls the remote SSE server."""
                                        async def sse_tool_proxy(**kwargs):
                                            """Proxy function for SSE tool."""
                                            from mcp import ClientSession
                                            from mcp.client.sse import sse_client
                                            
                                            # Connect to SSE server and call the tool
                                            async with sse_client(sse_url) as (read, write):
                                                async with ClientSession(read, write) as session:
                                                    await session.initialize()
                                                    result = await session.call_tool(original_tool_name, kwargs)
                                                    # Extract text content from MCP response
                                                    if hasattr(result, 'content') and result.content:
                                                        for content_item in result.content:
                                                            if hasattr(content_item, 'text'):
                                                                return content_item.text
                                                    return str(result)
                                        
                                        sse_tool_proxy.__name__ = tool_name.replace("-", "_")
                                        sse_tool_proxy.__doc__ = tool_def['description']
                                        return sse_tool_proxy
                                    
                                    # Create the proxy function
                                    proxy_func = make_sse_proxy(server_config.url, tool.name)
                                    
                                    # Register with FastMCP using the tool decorator
                                    from mcp.server.fastmcp.tools.base import Tool
                                    tool_obj = Tool.from_function(
                                        proxy_func,
                                        name=tool_name,
                                        description=tool_def['description']
                                    )
                                    
                                    # Override inputSchema with the actual schema from remote tool
                                    if input_schema:
                                        tool_obj.parameters = input_schema
                                    
                                    # Add to composer
                                    composer.composed_tools[tool_name] = tool_def
                                    composer.composed_server._tool_manager._tools[tool_name] = tool_obj
                                    composer.source_mapping[tool_name] = server_config.name
                                
                                logger.info(f"Successfully registered {len(tools)} tools from SSE server {server_config.name}")
                                print(f"    Tools: {len(tools)} registered", file=out)
                                print(f"    Status: ✓ Connected", file=out)
                            else:
                                print(f"    Status: ❌ No tools discovered", file=out)
                        except Exception as e:
                            # Check if it's just a cleanup error (TaskGroup exception after successful operation)
                            error_str = str(e)
                            if "TaskGroup" in error_str and "sub-exception" in error_str:
                                # This is a cleanup issue that happens after tools are registered
                                # Check if tools were actually registered by looking at composer
                                sse_tools_count = sum(1 for name in composer.source_mapping if composer.source_mapping[name] == server_config.name)
                                if sse_tools_count > 0:
                                    logger.warning(f"SSE server {server_config.name} connected successfully ({sse_tools_count} tools) but had cleanup issues: {e}")
                                    print(f"    Status: ⚠️  Connected ({sse_tools_count} tools, cleanup warning)", file=out)
                                else:
                                    logger.error(f"SSE server {server_config.name} failed during tool registration: {e}")
                                    print(f"    Status: ❌ Tool registration failed", file=out)
                            else:
                                logger.error(f"Failed to connect to SSE server {server_config.name}: {e}")
                                print(f"    Status: ❌ Connection failed: {e}", file=out)
                            # Print detailed traceback for debugging
                            import traceback
                            logger.debug(traceback.format_exc())
                        
                        print(file=out)
        
        # Handle HTTP streaming proxied servers
        if hasattr(config, 'servers') and hasattr(config.servers, 'proxied') and hasattr(config.servers.proxied, 'http'):
            from .config import HttpProxiedServerConfig, HttpStreamProtocol
            from mcp import ClientSession
            from .transport.http_stream import create_http_stream_transport
            
            http_servers = config.servers.proxied.http
            
            if http_servers:
                print(f"Connecting to {len(http_servers)} HTTP streaming server(s)...", file=out)
                print(file=out)
                
                for server_config in http_servers:
                    if isinstance(server_config, HttpProxiedServerConfig):
                        print(f"  • {server_config.name}", file=out)
                        print(f"    URL: {server_config.url}", file=out)
                        print(f"    Protocol: {server_config.protocol.value if hasattr(server_config.protocol, 'value') else server_config.protocol}", file=out)
                        
                        # Try to discover tools from the HTTP server using MCP protocol
                        try:
                            # Check if using native MCP Streamable HTTP protocol
                            protocol_value = server_config.protocol.value if hasattr(server_config.protocol, 'value') else str(server_config.protocol)
                            
                            if protocol_value == "streamable-http":
                                # Use native MCP streamablehttp_client
                                from mcp.client.streamable_http import streamablehttp_client
                                
                                # Build headers for authentication
                                headers = {}
                                if server_config.auth_token:
                                    if server_config.auth_type.lower() == "bearer":
                                        headers["Authorization"] = f"Bearer {server_config.auth_token}"
                                    elif server_config.auth_type.lower() == "basic":
                                        headers["Authorization"] = f"Basic {server_config.auth_token}"
                                    else:
                                        headers["Authorization"] = server_config.auth_token
                                
                                async with streamablehttp_client(
                                    url=server_config.url,
                                    headers=headers if headers else None,
                                    timeout=float(server_config.timeout),
                                ) as (read_stream, write_stream, get_session_id):
                                    async with ClientSession(read_stream, write_stream) as session:
                                        # Initialize the session
                                        await session.initialize()
                                        
                                        # List tools using MCP protocol
                                        tools_result = await session.list_tools()
                                        tools = tools_result.tools
                                        
                                        # Register tools in composer
                                        for tool in tools:
                                            tool_name = f"{server_config.name}_{tool.name}"
                                            
                                            # Extract input schema
                                            input_schema = {}
                                            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                                                input_schema = tool.inputSchema
                                            
                                            tool_def = {
                                                'name': tool.name,
                                                'description': tool.description if hasattr(tool, 'description') else '',
                                                'inputSchema': input_schema,
                                            }
                                            
                                            # Create a proxy function for this streamable HTTP tool
                                            def make_streamable_http_proxy(http_config, original_tool_name: str, tool_description: str):
                                                """Create a proxy function that calls the remote streamable HTTP server."""
                                                async def streamable_http_tool_proxy(**kwargs):
                                                    """Proxy function for streamable HTTP tool."""
                                                    from mcp import ClientSession
                                                    from mcp.client.streamable_http import streamablehttp_client
                                                    
                                                    # Build headers for authentication
                                                    hdrs = {}
                                                    if http_config.auth_token:
                                                        if http_config.auth_type.lower() == "bearer":
                                                            hdrs["Authorization"] = f"Bearer {http_config.auth_token}"
                                                        elif http_config.auth_type.lower() == "basic":
                                                            hdrs["Authorization"] = f"Basic {http_config.auth_token}"
                                                        else:
                                                            hdrs["Authorization"] = http_config.auth_token
                                                    
                                                    async with streamablehttp_client(
                                                        url=http_config.url,
                                                        headers=hdrs if hdrs else None,
                                                        timeout=float(http_config.timeout),
                                                    ) as (read_stream, write_stream, get_session_id):
                                                        async with ClientSession(read_stream, write_stream) as session:
                                                            await session.initialize()
                                                            result = await session.call_tool(original_tool_name, kwargs)
                                                            # Extract text content from MCP response
                                                            if hasattr(result, 'content') and result.content:
                                                                for content_item in result.content:
                                                                    if hasattr(content_item, 'text'):
                                                                        return content_item.text
                                                            return str(result)
                                                
                                                streamable_http_tool_proxy.__name__ = tool_name.replace("-", "_")
                                                streamable_http_tool_proxy.__doc__ = tool_description
                                                return streamable_http_tool_proxy
                                            
                                            # Create the proxy function
                                            proxy_func = make_streamable_http_proxy(server_config, tool.name, tool_def['description'])
                                            
                                            # Register with FastMCP using the tool decorator
                                            from mcp.server.fastmcp.tools.base import Tool
                                            tool_obj = Tool.from_function(
                                                proxy_func,
                                                name=tool_name,
                                                description=tool_def['description']
                                            )
                                            
                                            # Override inputSchema with the actual schema from remote tool
                                            if input_schema:
                                                tool_obj.parameters = input_schema
                                            
                                            # Add to composer
                                            composer.composed_tools[tool_name] = tool_def
                                            composer.composed_server._tool_manager._tools[tool_name] = tool_obj
                                            composer.source_mapping[tool_name] = server_config.name
                                        
                                        print(f"    Tools: {len(tools)} discovered", file=out)
                                        print(f"    Status: ✓ Connected", file=out)
                            else:
                                # Use custom HTTP stream transport for other protocols
                                transport = await create_http_stream_transport(
                                    name=server_config.name,
                                    url=server_config.url,
                                    protocol=server_config.protocol,
                                    auth_token=server_config.auth_token,
                                    auth_type=server_config.auth_type,
                                    timeout=server_config.timeout,
                                    retry_interval=server_config.retry_interval,
                                    keep_alive=server_config.keep_alive,
                                    reconnect_on_failure=server_config.reconnect_on_failure,
                                    max_reconnect_attempts=server_config.max_reconnect_attempts,
                                    poll_interval=server_config.poll_interval,
                                )
                                
                                # Create MCP session with HTTP transport
                                async with ClientSession(transport.messages(), transport.send) as session:
                                    # Initialize the session
                                    await session.initialize()
                                    
                                    # List tools using MCP protocol
                                    tools_result = await session.list_tools()
                                    tools = tools_result.tools
                                    
                                    # Register tools in composer
                                    for tool in tools:
                                        tool_name = f"{server_config.name}_{tool.name}"
                                        
                                        # Extract input schema
                                        input_schema = {}
                                        if hasattr(tool, 'inputSchema') and tool.inputSchema:
                                            input_schema = tool.inputSchema
                                        
                                        tool_def = {
                                            'name': tool.name,
                                            'description': tool.description if hasattr(tool, 'description') else '',
                                            'inputSchema': input_schema,
                                        }
                                        
                                        # Create a proxy function for this HTTP tool
                                        def make_http_proxy(http_config, original_tool_name: str):
                                            """Create a proxy function that calls the remote HTTP server."""
                                            async def http_tool_proxy(**kwargs):
                                                """Proxy function for HTTP tool."""
                                                from mcp import ClientSession
                                                from .transport.http_stream import create_http_stream_transport
                                                
                                                # Connect to HTTP server and call the tool
                                                transport = await create_http_stream_transport(
                                                    name=http_config.name,
                                                    url=http_config.url,
                                                    protocol=http_config.protocol,
                                                    auth_token=http_config.auth_token,
                                                    auth_type=http_config.auth_type,
                                                    timeout=http_config.timeout,
                                                )
                                                
                                                try:
                                                    async with ClientSession(transport.messages(), transport.send) as session:
                                                        await session.initialize()
                                                        result = await session.call_tool(original_tool_name, kwargs)
                                                        # Extract text content from MCP response
                                                        if hasattr(result, 'content') and result.content:
                                                            for content_item in result.content:
                                                                if hasattr(content_item, 'text'):
                                                                    return content_item.text
                                                        return str(result)
                                                finally:
                                                    await transport.disconnect()
                                            
                                            http_tool_proxy.__name__ = tool_name.replace("-", "_")
                                            http_tool_proxy.__doc__ = tool_def['description']
                                            return http_tool_proxy
                                        
                                        # Create the proxy function
                                        proxy_func = make_http_proxy(server_config, tool.name)
                                        
                                        # Register with FastMCP using the tool decorator
                                        from mcp.server.fastmcp.tools.base import Tool
                                        tool_obj = Tool.from_function(
                                            proxy_func,
                                            name=tool_name,
                                            description=tool_def['description']
                                        )
                                        
                                        # Override inputSchema with the actual schema from remote tool
                                        if input_schema:
                                            tool_obj.parameters = input_schema
                                        
                                        # Add to composer
                                        composer.composed_tools[tool_name] = tool_def
                                        composer.composed_server._tool_manager._tools[tool_name] = tool_obj
                                        composer.source_mapping[tool_name] = server_config.name
                                    
                                    print(f"    Tools: {len(tools)} discovered", file=out)
                                    print(f"    Status: ✓ Connected", file=out)
                                    
                                await transport.disconnect()
                            
                        except Exception as e:
                            logger.error(f"Failed to connect to HTTP server {server_config.name}: {e}")
                            print(f"    Status: ❌ Connection failed: {e}", file=out)
                            # Print detailed traceback for debugging
                            import traceback
                            logger.debug(traceback.format_exc())
                        
                        print(file=out)
        
        print("✓ All servers started successfully!", file=out)
        print(file=out)
        
        # Handle transport mode
        if transport_mode == "stdio":
            # Run in STDIO mode - read from stdin, write to stdout
            print("=" * 70, file=out)
            print("📡 MCP Server Mode: STDIO", file=out)
            print("=" * 70, file=out)
            print(f"✓ Unified MCP server is ready!", file=out)
            print(f"  Total tools: {len(composer.composed_tools)}", file=out)
            print(file=out)
            
            # List all available tools
            if composer.composed_tools:
                print("🔧 Available Tools:", file=out)
                for tool_name in sorted(composer.composed_tools.keys()):
                    tool_def = composer.composed_tools[tool_name]
                    params = []
                    if "inputSchema" in tool_def:
                        schema = tool_def["inputSchema"]
                        if "properties" in schema:
                            params = list(schema["properties"].keys())
                    params_str = f"({', '.join(params)})" if params else "()"
                    print(f"  • {tool_name}{params_str}", file=out)
            
            print(file=out)
            print("Running in STDIO mode - awaiting JSON-RPC messages on stdin...", file=out)
            
            # Run the composed server in STDIO mode
            # Use run_stdio_async() directly since we're already in an async context
            try:
                await composer.composed_server.run_stdio_async()
            except KeyboardInterrupt:
                print("\n⏹  Shutting down...", file=out)
            
            return 0
        
        # HTTP-based transport modes (streamable-http or sse)
        # Create the FastAPI REST API app
        from .api import create_app
        from .api.dependencies import set_composer, set_config
        from contextlib import asynccontextmanager
        
        # Determine port: CLI arg > UI config > composer config
        server_port = args.port
        if config.ui and config.ui.enabled and config.ui.port:
            server_port = config.ui.port
        if hasattr(args, 'port') and args.port != 8000:  # 8000 is the serve command default
            server_port = args.port
        
        # Set the composer and config instances for dependency injection
        set_composer(composer)
        set_config(config)
        
        # For streamable-http, we need to run the session manager in the lifespan
        session_manager = None
        if transport_mode == "streamable-http":
            # Trigger creation of the streamable HTTP app to initialize session manager
            _ = composer.composed_server.streamable_http_app()
            session_manager = composer.composed_server.session_manager
        
        # Create a custom lifespan that also runs the session manager
        @asynccontextmanager
        async def custom_lifespan(app):
            """Custom lifespan that runs the streamable HTTP session manager"""
            from .api.routes.translators import shutdown_translators
            
            logger.info("Starting MCP Compose API")
            
            if session_manager is not None:
                # Run the session manager for streamable HTTP
                async with session_manager.run():
                    logger.info("Streamable HTTP session manager started")
                    yield
                    logger.info("Streamable HTTP session manager stopping")
            else:
                yield
            
            # Shutdown
            logger.info("Shutting down MCP Compose API")
            await shutdown_translators()
        
        # Create the main FastAPI app with our custom lifespan
        app = create_app(lifespan=custom_lifespan)
        
        if transport_mode == "streamable-http":
            # Get the Streamable HTTP app and add its routes
            try:
                streamable_app = composer.composed_server.streamable_http_app()
                
                # Add the routes from the streamable app to our main app
                if hasattr(streamable_app, 'routes'):
                    logger.info(f"Streamable HTTP app has {len(streamable_app.routes)} routes")
                    for route in streamable_app.routes:
                        app.routes.append(route)
                    
                    logger.info("Streamable HTTP routes added successfully to main app")
            except Exception as e:
                logger.error(f"Failed to add Streamable HTTP routes: {e}")
                print(f"⚠️  Warning: Streamable HTTP endpoint not available: {e}", file=out)
        else:
            # SSE transport (deprecated)
            # Get the FastMCP SSE app and include its routes directly
            try:
                sse_app = composer.composed_server.sse_app()
            
                # Debug: Check if sse_app has routes
                if hasattr(sse_app, 'routes'):
                    logger.info(f"SSE app has {len(sse_app.routes)} routes")
                    for route in sse_app.routes:
                        logger.info(f"  Route: {route}")
                    
                    # Add SSE app routes directly to the main app instead of mounting
                    # This way /sse goes to /sse instead of /sse/sse
                    for route in sse_app.routes:
                        app.routes.append(route)
                    
                    logger.info("SSE routes added successfully to main app")
            except Exception as e:
                logger.error(f"Failed to add SSE routes: {e}")
                print(f"⚠️  Warning: SSE endpoint not available: {e}", file=out)
        
        # Add a /tools endpoint to list all available tools
        from fastapi import APIRouter
        from starlette.responses import JSONResponse
        
        tools_router = APIRouter()
        
        @tools_router.get("/tools")
        async def list_tools():
            """List all available tools with their schemas."""
            tools = []
            for tool_name, tool_def in composer.composed_tools.items():
                # Handle both dict and Tool object
                if hasattr(tool_def, 'model_dump'):
                    # It's a Pydantic model (Tool object)
                    tool_dict = tool_def.model_dump()
                    tools.append({
                        "name": tool_name,
                        "description": tool_dict.get("description", ""),
                        "inputSchema": tool_dict.get("inputSchema", {}),
                    })
                elif isinstance(tool_def, dict):
                    # It's already a dict
                    tools.append({
                        "name": tool_name,
                        "description": tool_def.get("description", ""),
                        "inputSchema": tool_def.get("inputSchema", {}),
                    })
                else:
                    # Fallback: try to access as attributes
                    tools.append({
                        "name": tool_name,
                        "description": getattr(tool_def, 'description', ''),
                        "inputSchema": getattr(tool_def, 'inputSchema', {}),
                    })
            return JSONResponse({
                "tools": tools,
                "total": len(tools)
            })
        
        # Include the tools router
        app.include_router(tools_router)
        
        # Add OAuth routes if OAuth2 authentication is enabled
        if config.authentication and config.authentication.enabled:
            oauth2_config = resolved_oauth_config or config.authentication.oauth2
            if oauth2_config and oauth2_config.client_id and oauth2_config.client_secret:
                from .api.routes.oauth import router as oauth_router, configure_oauth
                
                # Configure OAuth with server details
                # Always use localhost for OAuth callback URLs (GitHub requires exact match)
                oauth_host = "localhost" if args.host == "0.0.0.0" else args.host
                server_url = f"http://{oauth_host}:{server_port}"
                configure_oauth(
                    provider=oauth2_config.provider,
                    client_id=oauth2_config.client_id,
                    client_secret=oauth2_config.client_secret,
                    server_url=server_url,
                    authorization_endpoint=oauth2_config.authorization_endpoint,
                    token_endpoint=oauth2_config.token_endpoint,
                    userinfo_endpoint=oauth2_config.userinfo_endpoint,
                    scopes=oauth2_config.scopes,
                )
                
                # Include OAuth routes
                app.include_router(oauth_router)
                print(f"  OAuth Callback: http://localhost:{server_port}/oauth/callback", file=out)
                print(f"  Authorize:      http://localhost:{server_port}/authorize", file=out)
        
        print("=" * 70, file=out)
        print(f"📡 MCP Server Mode: {transport_mode.upper()}", file=out)
        print("=" * 70, file=out)
        if transport_mode == "streamable-http":
            print(f"  MCP Endpoint:  http://localhost:{server_port}/mcp", file=out)
        else:
            print(f"  SSE Endpoint:  http://localhost:{server_port}/sse (deprecated)", file=out)
        print(f"  Tools List:    http://localhost:{server_port}/tools", file=out)
        print(f"  REST API:      http://localhost:{server_port}/api/v1", file=out)
        print(f"  Health Check:  http://localhost:{server_port}/api/v1/health", file=out)
        print(file=out)
        print(f"✓ Unified MCP server is now running!", file=out)
        print(f"  Total tools: {len(composer.composed_tools)}", file=out)
        print(file=out)
        
        # List all available tools
        if composer.composed_tools:
            print("🔧 Available Tools:", file=out)
            for tool_name in sorted(composer.composed_tools.keys()):
                tool_def = composer.composed_tools[tool_name]
                # Extract parameter names from inputSchema
                params = []
                if "inputSchema" in tool_def:
                    schema = tool_def["inputSchema"]
                    if "properties" in schema:
                        params = list(schema["properties"].keys())
                
                # Format parameters
                params_str = f"({', '.join(params)})" if params else "()"
                print(f"  • {tool_name}{params_str}", file=out)
        
        print(file=out)
        print("=" * 70, file=out)
        print(file=out)
        print("Press Ctrl+C to stop all servers...", file=out)
        print(file=out)
        
        # Run uvicorn in background
        server_config_uvicorn = uvicorn.Config(
            app=app,
            host=args.host,
            port=server_port,
            log_level="info",
        )
        server = uvicorn.Server(server_config_uvicorn)
        
        # Run server
        try:
            await server.serve()
        except KeyboardInterrupt:
            print("\n\n⏹  Shutting down...", file=out)
        
        return 0
        
    finally:
        # Clean shutdown
        await process_manager.stop()
        print("✓ All servers stopped", file=out)
        
        # Flush OTEL traces before exit
        if otel_provider is not None:
            otel_provider.force_flush()
            print("✓ OpenTelemetry traces flushed", file=out)


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="mcp-compose",
        description="Compose multiple MCP servers into a unified server",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Serve command - NEW: Run MCP servers from config
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start MCP servers from configuration file",
    )
    serve_parser.add_argument(
        "-c", "--config",
        type=str,
        help="Path to mcp_compose.toml file (default: auto-detect)",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    serve_parser.add_argument(
        "-t", "--transport",
        type=str,
        choices=["stdio", "sse", "streamable-http"],
        default=None,
        help="Transport mode: stdio (subprocess), sse (deprecated), or streamable-http (recommended HTTP transport). If not specified, uses config file settings.",
    )

    # Compose command
    compose_parser = subparsers.add_parser(
        "compose",
        help="Compose MCP servers from dependencies",
    )
    compose_parser.add_argument(
        "-p", "--pyproject",
        type=str,
        help="Path to pyproject.toml file (default: ./pyproject.toml)",
    )
    compose_parser.add_argument(
        "-n", "--name",
        type=str,
        default="composed-mcp-server",
        help="Name for the composed server (default: composed-mcp-server)",
    )
    compose_parser.add_argument(
        "-c", "--conflict-resolution",
        type=str,
        choices=[cr.value for cr in ConflictResolution],
        default=ConflictResolution.PREFIX.value,
        help="Strategy for resolving naming conflicts (default: prefix)",
    )
    compose_parser.add_argument(
        "--include",
        type=str,
        nargs="*",
        help="Include only specified servers",
    )
    compose_parser.add_argument(
        "--exclude",
        type=str,
        nargs="*",
        help="Exclude specified servers",
    )
    compose_parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file for the composed server",
    )
    compose_parser.add_argument(
        "--output-format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format for results (default: text)",
    )

    # Discover command
    discover_parser = subparsers.add_parser(
        "discover",
        help="Discover MCP servers from dependencies",
    )
    discover_parser.add_argument(
        "-p", "--pyproject",
        type=str,
        help="Path to pyproject.toml file (default: ./pyproject.toml)",
    )
    discover_parser.add_argument(
        "--output-format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format for results (default: text)",
    )

    return parser


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Set up logging
    setup_logging(args.verbose)

    # Handle commands
    if args.command == "serve":
        return serve_command(args)
    elif args.command == "compose":
        return compose_command(args)
    elif args.command == "discover":
        return discover_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
