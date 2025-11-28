"""
MCP Compose CLI.

Command-line interface for managing MCP servers.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

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
        
        print(f"Loading configuration from: {config_path}")
        config = load_config(config_path)
        
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
    import uvicorn
    
    # Initialize authenticator if authentication is enabled
    authenticator = None
    if config.authentication.enabled:
        print(f"\n🔐 Authentication enabled")
        print(f"   Provider: {config.authentication.default_provider}")
        
        # Create authenticator based on provider
        provider = config.authentication.default_provider
        
        if provider == AuthProvider.ANACONDA:
            if config.authentication.anaconda:
                domain = config.authentication.anaconda.domain
                print(f"   Domain: {domain}")
                authenticator = create_authenticator(
                    AuthType.ANACONDA,
                    domain=domain
                )
            else:
                print("   ⚠️  Warning: Anaconda auth config missing, using defaults")
                authenticator = create_authenticator(AuthType.ANACONDA)
        elif provider == AuthProvider.API_KEY:
            if config.authentication.api_key:
                authenticator = create_authenticator(
                    AuthType.API_KEY,
                    api_keys={}  # Would load from config
                )
            else:
                print("   ⚠️  Warning: API Key auth config missing")
        else:
            print(f"   ⚠️  Warning: Provider {provider} not yet implemented")
        
        if authenticator:
            set_authenticator(authenticator)
            print(f"   ✓ Authenticator initialized")
        print()
    
    # Create process manager
    process_manager = ProcessManager(auto_restart=False)
    
    # Create composer
    conflict_strategy = ConflictResolution.PREFIX
    if hasattr(config.composer, 'conflict_resolution'):
        # Convert from ConflictResolutionStrategy (config) to ConflictResolution (composer)
        config_strategy = config.composer.conflict_resolution
        conflict_strategy = ConflictResolution(config_strategy.value)
    
    composer = MCPServerComposer(
        composed_server_name=config.composer.name,
        conflict_resolution=conflict_strategy,
        use_process_manager=True,
    )
    composer.process_manager = process_manager
    
    # Create tool proxy for STDIO communication
    tool_proxy = ToolProxy(process_manager, composer)
    
    try:
        # Start process manager
        await process_manager.start()
        
        print(f"\n🚀 MCP Compose: {config.composer.name}")
        print(f"Conflict Resolution: {config.composer.conflict_resolution}")
        print(f"Log Level: {config.composer.log_level}")
        print()
        
        # Add and start all configured servers
        if hasattr(config, 'servers') and hasattr(config.servers, 'proxied') and hasattr(config.servers.proxied, 'stdio'):
            stdio_servers = config.servers.proxied.stdio
            
            if not stdio_servers:
                print("⚠️  No servers configured in mcp_compose.toml")
                print()
                return 1
            
            print(f"Starting {len(stdio_servers)} server(s)...")
            print()
            
            for server_config in stdio_servers:
                if isinstance(server_config, StdioProxiedServerConfig):
                    # command is already a List[str] in the config
                    command = server_config.command
                    
                    print(f"  • {server_config.name}")
                    print(f"    Command: {' '.join(command)}")
                    if server_config.env:
                        print(f"    Environment: {list(server_config.env.keys())}")
                    
                    # Add process
                    process = await process_manager.add_process(
                        name=server_config.name,
                        command=command,
                        env=server_config.env,
                        auto_start=True
                    )
                    
                    # Discover tools from the server
                    await tool_proxy.discover_tools(server_config.name, process)
                    
                    print(f"    Status: ✓ Started")
                    print()
        
        # Handle SSE proxied servers
        if hasattr(config, 'servers') and hasattr(config.servers, 'proxied') and hasattr(config.servers.proxied, 'sse'):
            from .config import SseProxiedServerConfig
            from mcp import ClientSession
            from mcp.client.sse import sse_client
            
            sse_servers = config.servers.proxied.sse
            
            if sse_servers:
                print(f"Connecting to {len(sse_servers)} SSE server(s)...")
                print()
                
                for server_config in sse_servers:
                    if isinstance(server_config, SseProxiedServerConfig):
                        print(f"  • {server_config.name}")
                        print(f"    URL: {server_config.url}")
                        
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
                                print(f"    Tools: {len(tools)} registered")
                                print(f"    Status: ✓ Connected")
                            else:
                                print(f"    Status: ❌ No tools discovered")
                        except Exception as e:
                            # Check if it's just a cleanup error (TaskGroup exception after successful operation)
                            error_str = str(e)
                            if "TaskGroup" in error_str and "sub-exception" in error_str:
                                # This is a cleanup issue that happens after tools are registered
                                # Check if tools were actually registered by looking at composer
                                sse_tools_count = sum(1 for name in composer.source_mapping if composer.source_mapping[name] == server_config.name)
                                if sse_tools_count > 0:
                                    logger.warning(f"SSE server {server_config.name} connected successfully ({sse_tools_count} tools) but had cleanup issues: {e}")
                                    print(f"    Status: ⚠️  Connected ({sse_tools_count} tools, cleanup warning)")
                                else:
                                    logger.error(f"SSE server {server_config.name} failed during tool registration: {e}")
                                    print(f"    Status: ❌ Tool registration failed")
                            else:
                                logger.error(f"Failed to connect to SSE server {server_config.name}: {e}")
                                print(f"    Status: ❌ Connection failed: {e}")
                            # Print detailed traceback for debugging
                            import traceback
                            logger.debug(traceback.format_exc())
                        
                        print()
        
        # Handle HTTP streaming proxied servers
        if hasattr(config, 'servers') and hasattr(config.servers, 'proxied') and hasattr(config.servers.proxied, 'http'):
            from .config import HttpProxiedServerConfig
            from mcp import ClientSession
            from .transport.http_stream import create_http_stream_transport
            
            http_servers = config.servers.proxied.http
            
            if http_servers:
                print(f"Connecting to {len(http_servers)} HTTP streaming server(s)...")
                print()
                
                for server_config in http_servers:
                    if isinstance(server_config, HttpProxiedServerConfig):
                        print(f"  • {server_config.name}")
                        print(f"    URL: {server_config.url}")
                        print(f"    Protocol: {server_config.protocol}")
                        
                        # Try to discover tools from the HTTP server using MCP protocol
                        try:
                            # Connect to HTTP server using custom transport
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
                                
                                print(f"    Tools: {len(tools)} discovered")
                                print(f"    Status: ✓ Connected")
                                
                            await transport.disconnect()
                            
                        except Exception as e:
                            logger.error(f"Failed to connect to HTTP server {server_config.name}: {e}")
                            print(f"    Status: ❌ Connection failed: {e}")
                        
                        print()
        
        print("✓ All servers started successfully!")
        print()
        
        # Handle transport mode
        if transport_mode == "stdio":
            # Run in STDIO mode - read from stdin, write to stdout
            print("=" * 70)
            print("📡 MCP Server Mode: STDIO")
            print("=" * 70)
            print(f"✓ Unified MCP server is ready!")
            print(f"  Total tools: {len(composer.composed_tools)}")
            print()
            
            # List all available tools
            if composer.composed_tools:
                print("🔧 Available Tools:")
                for tool_name in sorted(composer.composed_tools.keys()):
                    tool_def = composer.composed_tools[tool_name]
                    params = []
                    if "inputSchema" in tool_def:
                        schema = tool_def["inputSchema"]
                        if "properties" in schema:
                            params = list(schema["properties"].keys())
                    params_str = f"({', '.join(params)})" if params else "()"
                    print(f"  • {tool_name}{params_str}", file=sys.stderr)
            
            print()
            print("Running in STDIO mode - awaiting JSON-RPC messages on stdin...", file=sys.stderr)
            
            # Run the composed server in STDIO mode
            try:
                composer.composed_server.run(transport="stdio")
            except KeyboardInterrupt:
                print("\n⏹  Shutting down...", file=sys.stderr)
            
            return 0
        
        # HTTP-based transport modes (streamable-http or sse)
        # Create the FastAPI REST API app
        from .api import create_app
        from .api.dependencies import set_composer
        
        # Set the composer instance for dependency injection
        set_composer(composer)
        
        # Create the main FastAPI app with REST API routes
        app = create_app()
        
        if transport_mode == "streamable-http":
            # Get the Streamable HTTP app
            try:
                streamable_app = composer.composed_server.streamable_http_app()
                
                if hasattr(streamable_app, 'routes'):
                    logger.info(f"Streamable HTTP app has {len(streamable_app.routes)} routes")
                    for route in streamable_app.routes:
                        app.routes.append(route)
                    
                    logger.info("Streamable HTTP routes added successfully to main app")
            except Exception as e:
                logger.error(f"Failed to add Streamable HTTP routes: {e}")
                print(f"⚠️  Warning: Streamable HTTP endpoint not available: {e}")
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
                print(f"⚠️  Warning: SSE endpoint not available: {e}")
        
        # Add a /tools endpoint to list all available tools
        from fastapi import APIRouter
        from starlette.responses import JSONResponse
        
        tools_router = APIRouter()
        
        @tools_router.get("/tools")
        async def list_tools():
            """List all available tools with their schemas."""
            tools = []
            for tool_name, tool_def in composer.composed_tools.items():
                tools.append({
                    "name": tool_name,
                    "description": tool_def.get("description", ""),
                    "inputSchema": tool_def.get("inputSchema", {}),
                })
            return JSONResponse({
                "tools": tools,
                "total": len(tools)
            })
        
        # Include the tools router
        app.include_router(tools_router)
        
        print("=" * 70)
        print(f"📡 MCP Server Mode: {transport_mode.upper()}")
        print("=" * 70)
        if transport_mode == "streamable-http":
            print(f"  MCP Endpoint:  http://localhost:{config.composer.port}/mcp")
        else:
            print(f"  SSE Endpoint:  http://localhost:{config.composer.port}/sse (deprecated)")
        print(f"  Tools List:    http://localhost:{config.composer.port}/tools")
        print(f"  REST API:      http://localhost:{config.composer.port}/api/v1")
        print(f"  Health Check:  http://localhost:{config.composer.port}/api/v1/health")
        print()
        print(f"✓ Unified MCP server is now running!")
        print(f"  Total tools: {len(composer.composed_tools)}")
        print()
        
        # List all available tools
        if composer.composed_tools:
            print("🔧 Available Tools:")
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
                print(f"  • {tool_name}{params_str}")
        
        print()
        print("=" * 70)
        print()
        print("Press Ctrl+C to stop all servers...")
        print()
        
        # Run uvicorn in background
        server_config_uvicorn = uvicorn.Config(
            app=app,
            host=args.host,
            port=config.composer.port,
            log_level="info",
        )
        server = uvicorn.Server(server_config_uvicorn)
        
        # Run server
        try:
            await server.serve()
        except KeyboardInterrupt:
            print("\n\n⏹  Shutting down...")
        
        return 0
        
    finally:
        # Clean shutdown
        await process_manager.stop()
        print("✓ All servers stopped")


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
