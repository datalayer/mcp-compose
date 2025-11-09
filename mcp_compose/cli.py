"""
MCP Server Composer CLI.

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
    """Run the MCP server composer."""
    from .config import StdioProxiedServerConfig
    from .composer import MCPServerComposer, ConflictResolution
    from .tool_proxy import ToolProxy
    import uvicorn
    
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
        
        print(f"\n🚀 MCP Server Composer: {config.composer.name}")
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
        
        print("✓ All servers started successfully!")
        print()
        
        # Get the FastMCP app with SSE endpoint
        base_app = composer.composed_server.sse_app()
        
        # Add a /tools endpoint to list all available tools
        # sse_app() returns a Starlette app, so we need to use Starlette routing
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        
        async def list_tools(request):
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
        
        # Add the tools route to the existing app
        base_app.routes.append(Route("/tools", list_tools))
        app = base_app
        
        print("=" * 70)
        print("📡 MCP Server Endpoints")
        print("=" * 70)
        print(f"  SSE Endpoint:  http://localhost:{config.composer.port}/sse")
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
