"""
OpenTelemetry instrumentation for mcp-compose.

This module provides automatic tracing for mcp-compose operations,
including tool discovery, tool calls, and server composition.

Simple usage with Logfire (recommended):
    from mcp_compose import setup_otel, instrument_mcp_compose
    
    # Setup OTEL and instrument mcp-compose in one call
    provider = setup_otel(service_name="my-app")
    
    # Or setup and instrument separately
    provider = setup_otel(service_name="my-app", instrument=False)
    instrument_mcp_compose(tracer_provider=provider)

Environment variables for Logfire:
    DATALAYER_LOGFIRE_TOKEN   - Logfire write token (required)
    DATALAYER_LOGFIRE_PROJECT - Project name (default: starter-project)
    DATALAYER_LOGFIRE_URL     - Logfire URL (default: https://logfire-us.pydantic.dev)

Usage with plain OpenTelemetry:
    from opentelemetry import trace
    from mcp_compose import instrument_mcp_compose
    
    tracer_provider = trace.get_tracer_provider()
    instrument_mcp_compose(tracer_provider=tracer_provider)
"""

from __future__ import annotations

import functools
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, TypeVar

try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, Status, StatusCode, Tracer
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore
    Span = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore
    Tracer = None  # type: ignore

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Global state to track instrumentation
_instrumented = False
_tracer_provider: Optional[Any] = None


def setup_otel(
    service_name: str = "mcp-compose",
    service_version: str = "1.0.0",
    *,
    token: Optional[str] = None,
    project: Optional[str] = None,
    url: Optional[str] = None,
    instrument: bool = True,
) -> Tuple[Any, Any]:
    """
    Setup OpenTelemetry tracing for mcp-compose with Logfire.
    
    This is the recommended way to enable tracing. It configures the
    TracerProvider, OTLP exporter, and optionally instruments mcp-compose.
    
    Args:
        service_name: Name of the service for tracing (default: "mcp-compose")
        service_version: Version of the service (default: "1.0.0")
        token: Logfire write token. If not provided, reads from DATALAYER_LOGFIRE_TOKEN env var.
        project: Logfire project name. If not provided, reads from DATALAYER_LOGFIRE_PROJECT env var.
        url: Logfire URL. If not provided, reads from DATALAYER_LOGFIRE_URL env var.
        instrument: Whether to instrument mcp-compose classes (default: True)
    
    Returns:
        Tuple of (TracerProvider, Tracer) for creating custom spans.
    
    Raises:
        ImportError: If OpenTelemetry packages are not installed.
        ValueError: If no token is provided and DATALAYER_LOGFIRE_TOKEN is not set.
    
    Example:
        from mcp_compose import setup_otel
        
        # Basic usage - reads config from environment variables
        provider, tracer = setup_otel(service_name="my-mcp-app")
        
        # Create custom spans
        with tracer.start_as_current_span("my-operation") as span:
            span.set_attribute("key", "value")
            # ... do work ...
        
        # Flush on shutdown
        provider.force_flush()
    """
    global _tracer_provider
    
    if not OTEL_AVAILABLE:
        raise ImportError(
            "OpenTelemetry is required for tracing. "
            "Install it with: pip install mcp-compose[otel]"
        )
    
    # Read configuration from environment variables if not provided
    token = token or os.environ.get("DATALAYER_LOGFIRE_TOKEN")
    project = project or os.environ.get("DATALAYER_LOGFIRE_PROJECT", "starter-project")
    url = url or os.environ.get("DATALAYER_LOGFIRE_URL", "https://logfire-us.pydantic.dev")
    
    if not token:
        raise ValueError(
            "Logfire token is required. Either pass token= parameter or set "
            "DATALAYER_LOGFIRE_TOKEN environment variable.\n"
            "Get a write token from: https://logfire-us.pydantic.dev/datalayer/{project}/settings/write-tokens"
        )
    
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    
    # Configure exporter with endpoint and token
    exporter = OTLPSpanExporter(
        endpoint=f'{url}/v1/traces',
        headers={'Authorization': token},
    )
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
    })
    
    # Setup tracer provider
    span_processor = BatchSpanProcessor(exporter)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(span_processor)
    
    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    
    # Instrument mcp-compose if requested
    if instrument:
        instrument_mcp_compose(tracer_provider=provider)
    
    # Get tracer for the service
    tracer = provider.get_tracer(service_name)
    
    logger.info(f"OpenTelemetry configured for {service_name}")
    logger.info(f"Traces: {url}/datalayer/{project}")
    
    return provider, tracer


def get_tracer(name: str = "mcp-compose") -> Optional[Any]:
    """
    Get a tracer from the configured provider.
    
    Args:
        name: Name for the tracer (default: "mcp-compose")
    
    Returns:
        Tracer instance, or None if OTEL is not configured.
    """
    if _tracer_provider is not None:
        return _tracer_provider.get_tracer(name)
    if OTEL_AVAILABLE:
        return trace.get_tracer(name)
    return None


def instrument_mcp_compose(
    logfire_instance: Any = None,
    *,
    tracer_provider: Optional[TracerProvider] = None,
    capture_tool_arguments: bool = True,
    capture_tool_results: bool = True,
) -> None:
    """
    Instrument mcp-compose for OpenTelemetry tracing.
    
    Args:
        logfire_instance: Optional Logfire instance to use for tracing.
            If provided, uses Logfire's tracer provider.
        tracer_provider: Optional OpenTelemetry TracerProvider.
            If not provided, uses the global tracer provider.
        capture_tool_arguments: Whether to capture tool call arguments as span attributes.
        capture_tool_results: Whether to capture tool call results as span attributes.
    
    Example with Logfire:
        import logfire
        from mcp_compose.otel import instrument_mcp_compose
        
        logfire.configure()
        instrument_mcp_compose(logfire)
    
    Example with OpenTelemetry:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from mcp_compose.otel import instrument_mcp_compose
        
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        instrument_mcp_compose(tracer_provider=provider)
    """
    global _instrumented
    
    if not OTEL_AVAILABLE:
        raise ImportError(
            "OpenTelemetry is required for instrumentation. "
            "Install it with: pip install mcp_compose[otel]"
        )
    
    if _instrumented:
        logger.warning("mcp-compose is already instrumented")
        return
    
    # Get tracer provider
    if logfire_instance is not None:
        # Use Logfire's tracer provider - try different API versions
        if hasattr(logfire_instance, 'config') and hasattr(logfire_instance.config, 'get_tracer_provider'):
            tracer_provider = logfire_instance.config.get_tracer_provider()
        else:
            # Logfire configures the global tracer provider, so use that
            tracer_provider = trace.get_tracer_provider()
    elif tracer_provider is None:
        # Use global tracer provider
        tracer_provider = trace.get_tracer_provider()
    
    tracer = tracer_provider.get_tracer("mcp_compose", "0.1.0")
    
    # Instrument the various components
    _instrument_tool_proxy(tracer, capture_tool_arguments, capture_tool_results)
    _instrument_composer(tracer)
    _instrument_tool_manager(tracer)
    _instrument_process_manager(tracer)
    
    _instrumented = True
    logger.info("mcp-compose instrumentation enabled")


def uninstrument_mcp_compose() -> None:
    """Remove mcp-compose instrumentation."""
    global _instrumented
    # Note: Full uninstrumentation would require storing original methods
    # For now, just reset the flag
    _instrumented = False
    logger.info("mcp-compose instrumentation disabled")


def _instrument_tool_proxy(
    tracer: Any,
    capture_arguments: bool,
    capture_results: bool,
) -> None:
    """Instrument ToolProxy for tracing tool discovery and calls."""
    try:
        from .tool_proxy import ToolProxy
    except ImportError:
        logger.debug("ToolProxy not available, skipping instrumentation")
        return
    
    # Instrument discover_tools
    original_discover_tools = ToolProxy.discover_tools
    
    @functools.wraps(original_discover_tools)
    async def traced_discover_tools(self: Any, server_name: str, process: Any) -> None:
        with tracer.start_as_current_span(
            f"mcp.discover_tools {server_name}",
            kind=trace.SpanKind.CLIENT,
        ) as span:
            span.set_attribute("mcp.server.name", server_name)
            span.set_attribute("mcp.operation", "discover_tools")
            span.set_attribute("rpc.system", "jsonrpc")
            
            try:
                result = await original_discover_tools(self, server_name, process)
                
                # Record discovered tools count
                if hasattr(self, 'server_tools') and server_name in self.server_tools:
                    tools_count = len(self.server_tools[server_name])
                    span.set_attribute("mcp.tools.discovered_count", tools_count)
                
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    ToolProxy.discover_tools = traced_discover_tools
    
    # Instrument _send_request
    original_send_request = ToolProxy._send_request
    
    @functools.wraps(original_send_request)
    async def traced_send_request(self: Any, process: Any, request: dict) -> Any:
        method = request.get("method", "unknown")
        span_name = f"mcp.request {method}"
        
        with tracer.start_as_current_span(
            span_name,
            kind=trace.SpanKind.CLIENT,
        ) as span:
            span.set_attribute("rpc.system", "jsonrpc")
            span.set_attribute("rpc.method", method)
            span.set_attribute("rpc.jsonrpc.version", "2.0")
            
            if capture_arguments:
                # Capture tool call arguments
                if method == "tools/call":
                    params = request.get("params", {})
                    tool_name = params.get("name", "unknown")
                    span.set_attribute("mcp.tool.name", tool_name)
                    
                    arguments = params.get("arguments", {})
                    if arguments:
                        try:
                            span.set_attribute("mcp.tool.arguments", json.dumps(arguments))
                        except (TypeError, ValueError):
                            span.set_attribute("mcp.tool.arguments", str(arguments))
            
            try:
                response = await original_send_request(self, process, request)
                
                if response:
                    if "error" in response:
                        error = response["error"]
                        span.set_status(Status(StatusCode.ERROR, str(error)))
                        span.set_attribute("rpc.jsonrpc.error_code", error.get("code", -1))
                        span.set_attribute("rpc.jsonrpc.error_message", error.get("message", ""))
                    else:
                        span.set_status(Status(StatusCode.OK))
                        
                        if capture_results and "result" in response:
                            result = response["result"]
                            try:
                                # Truncate large results
                                result_str = json.dumps(result)
                                if len(result_str) > 4096:
                                    result_str = result_str[:4096] + "...(truncated)"
                                span.set_attribute("mcp.response.result", result_str)
                            except (TypeError, ValueError):
                                span.set_attribute("mcp.response.result", str(result)[:4096])
                
                return response
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    ToolProxy._send_request = traced_send_request


def _instrument_composer(tracer: Any) -> None:
    """Instrument MCPServerComposer for tracing composition operations."""
    try:
        from .composer import MCPServerComposer
    except ImportError:
        logger.debug("MCPServerComposer not available, skipping instrumentation")
        return
    
    # Instrument compose_from_pyproject
    if hasattr(MCPServerComposer, 'compose_from_pyproject'):
        original_compose_from_pyproject = MCPServerComposer.compose_from_pyproject
        
        @functools.wraps(original_compose_from_pyproject)
        def traced_compose_from_pyproject(self: Any, *args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(
                "mcp.compose_from_pyproject",
                kind=trace.SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.operation", "compose_from_pyproject")
                span.set_attribute("mcp.composed_server.name", self.composed_server_name)
                
                try:
                    result = original_compose_from_pyproject(self, *args, **kwargs)
                    
                    # Record composition stats
                    span.set_attribute("mcp.tools.count", len(self.composed_tools))
                    span.set_attribute("mcp.prompts.count", len(self.composed_prompts))
                    span.set_attribute("mcp.resources.count", len(self.composed_resources))
                    span.set_attribute("mcp.conflicts.resolved", len(self.conflicts_resolved))
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        MCPServerComposer.compose_from_pyproject = traced_compose_from_pyproject
    
    # Instrument compose_from_discovery
    if hasattr(MCPServerComposer, 'compose_from_discovery'):
        original_compose_from_discovery = MCPServerComposer.compose_from_discovery
        
        @functools.wraps(original_compose_from_discovery)
        async def traced_compose_from_discovery(self: Any, *args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(
                "mcp.compose_from_discovery",
                kind=trace.SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.operation", "compose_from_discovery")
                span.set_attribute("mcp.composed_server.name", self.composed_server_name)
                
                try:
                    result = await original_compose_from_discovery(self, *args, **kwargs)
                    
                    # Record composition stats
                    span.set_attribute("mcp.tools.count", len(self.composed_tools))
                    span.set_attribute("mcp.prompts.count", len(self.composed_prompts))
                    span.set_attribute("mcp.conflicts.resolved", len(self.conflicts_resolved))
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        MCPServerComposer.compose_from_discovery = traced_compose_from_discovery


def _instrument_tool_manager(tracer: Any) -> None:
    """Instrument ToolManager for tracing tool registration and resolution."""
    try:
        from .tool_manager import ToolManager
    except ImportError:
        logger.debug("ToolManager not available, skipping instrumentation")
        return
    
    # Instrument register_tools
    original_register_tools = ToolManager.register_tools
    
    @functools.wraps(original_register_tools)
    def traced_register_tools(
        self: Any,
        server_name: str,
        tools: dict,
        server_version: Optional[str] = None,
    ) -> dict:
        with tracer.start_as_current_span(
            f"mcp.register_tools {server_name}",
            kind=trace.SpanKind.INTERNAL,
        ) as span:
            span.set_attribute("mcp.operation", "register_tools")
            span.set_attribute("mcp.server.name", server_name)
            span.set_attribute("mcp.tools.input_count", len(tools))
            
            if server_version:
                span.set_attribute("mcp.server.version", server_version)
            
            try:
                result = original_register_tools(self, server_name, tools, server_version)
                
                span.set_attribute("mcp.tools.registered_count", len(result))
                span.set_attribute("mcp.conflicts.count", len(self.conflicts_resolved))
                
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    ToolManager.register_tools = traced_register_tools


def _instrument_process_manager(tracer: Any) -> None:
    """Instrument ProcessManager for tracing process lifecycle."""
    try:
        from .process_manager import ProcessManager
    except ImportError:
        logger.debug("ProcessManager not available, skipping instrumentation")
        return
    
    # Instrument start_process
    if hasattr(ProcessManager, 'start_process'):
        original_start_process = ProcessManager.start_process
        
        @functools.wraps(original_start_process)
        async def traced_start_process(self: Any, name: str, *args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(
                f"mcp.start_process {name}",
                kind=trace.SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.operation", "start_process")
                span.set_attribute("mcp.process.name", name)
                
                try:
                    result = await original_start_process(self, name, *args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        ProcessManager.start_process = traced_start_process
    
    # Instrument stop_process
    if hasattr(ProcessManager, 'stop_process'):
        original_stop_process = ProcessManager.stop_process
        
        @functools.wraps(original_stop_process)
        async def traced_stop_process(self: Any, name: str, *args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(
                f"mcp.stop_process {name}",
                kind=trace.SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.operation", "stop_process")
                span.set_attribute("mcp.process.name", name)
                
                try:
                    result = await original_stop_process(self, name, *args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        ProcessManager.stop_process = traced_stop_process


# ============================================================================
# Server-side instrumentation utilities
# ============================================================================

def get_server_tracer(service_name: str = "mcp-compose") -> Any:
    """
    Get a tracer for server-side tracing.
    
    This is used by the mcp-compose server to trace incoming requests.
    
    Args:
        service_name: Name of the service for tracing.
        
    Returns:
        OpenTelemetry Tracer instance, or None if OTEL is not available.
    """
    if not OTEL_AVAILABLE:
        return None
    
    return trace.get_tracer(service_name, "0.1.0")


def create_traced_tool_proxy(
    tracer: Any,
    original_func: Callable[..., Any],
    tool_name: str,
    server_name: str,
    capture_arguments: bool = True,
    capture_results: bool = True,
) -> Callable[..., Any]:
    """
    Wrap a tool proxy function with OpenTelemetry tracing.
    
    Use this in the mcp-compose server to trace incoming tool calls.
    
    Args:
        tracer: OpenTelemetry Tracer instance.
        original_func: The original tool proxy function.
        tool_name: Name of the tool being proxied.
        server_name: Name of the upstream MCP server.
        capture_arguments: Whether to capture call arguments.
        capture_results: Whether to capture call results.
        
    Returns:
        Traced version of the function.
    
    Example:
        tracer = get_server_tracer()
        if tracer:
            proxy_func = create_traced_tool_proxy(
                tracer, proxy_func, tool_name, server_name
            )
    """
    if tracer is None:
        return original_func
    
    @functools.wraps(original_func)
    async def traced_proxy(*args: Any, **kwargs: Any) -> Any:
        with tracer.start_as_current_span(
            f"mcp.server.tool_call {tool_name}",
            kind=trace.SpanKind.SERVER,
        ) as span:
            span.set_attribute("mcp.tool.name", tool_name)
            span.set_attribute("mcp.server.name", server_name)
            span.set_attribute("mcp.operation", "tool_call")
            span.set_attribute("rpc.system", "jsonrpc")
            span.set_attribute("rpc.method", "tools/call")
            
            if capture_arguments and kwargs:
                try:
                    span.set_attribute("mcp.tool.arguments", json.dumps(kwargs, default=str)[:1000])
                except Exception:
                    pass
            
            try:
                result = await original_func(*args, **kwargs)
                
                if capture_results and result is not None:
                    try:
                        result_str = str(result)[:1000]
                        span.set_attribute("mcp.tool.result_preview", result_str)
                    except Exception:
                        pass
                
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    return traced_proxy


def trace_server_startup(tracer: Any, service_name: str, config_info: dict[str, Any]) -> Any:
    """
    Create a span for server startup.
    
    Args:
        tracer: OpenTelemetry Tracer instance.
        service_name: Name of the service.
        config_info: Configuration information to record.
        
    Returns:
        Context manager for the span.
    """
    if tracer is None:
        import contextlib
        return contextlib.nullcontext()
    
    span = tracer.start_span(
        f"mcp.server.startup {service_name}",
        kind=trace.SpanKind.INTERNAL,
    )
    span.set_attribute("mcp.server.name", service_name)
    span.set_attribute("mcp.operation", "server_startup")
    
    for key, value in config_info.items():
        try:
            span.set_attribute(f"mcp.server.config.{key}", str(value))
        except Exception:
            pass
    
    return span
