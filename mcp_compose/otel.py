"""
OpenTelemetry instrumentation for mcp-compose.

This module provides automatic tracing and metrics for mcp-compose operations,
following the Logfire instrumentation pattern (external monkey-patching).

The instrumentation is **non-intrusive** - it patches classes from outside
without modifying the core mcp-compose code.

Simple usage with Logfire (recommended):
    from mcp_compose import setup_otel, instrument_mcp_compose
    
    # Setup OTEL and instrument mcp-compose in one call
    provider, tracer = setup_otel(service_name="my-app")
    
    # Or setup and instrument separately
    provider, tracer = setup_otel(service_name="my-app", instrument=False)
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

Instrumented operations:
    - Tool discovery from child MCP servers
    - Tool calls (with arguments and results capture)
    - JSON-RPC requests/responses
    - Process lifecycle (start, stop, restart)
    - Server composition
    - HTTP transport operations
    - SSE connections
"""

from __future__ import annotations

import functools
import json
import logging
import os
import sys
import time
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, TypeVar

try:
from opentelemetry import context
    from opentelemetry import trace
    from opentelemetry.trace import Span, SpanKind, Status, StatusCode, Tracer
    from opentelemetry.semconv.trace import SpanAttributes
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore
    Span = None  # type: ignore
    SpanKind = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore
    Tracer = None  # type: ignore
    SpanAttributes = None  # type: ignore

# Optional metrics support
try:
    from opentelemetry import metrics
    from opentelemetry.metrics import Counter, Histogram, UpDownCounter
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    metrics = None  # type: ignore
    Counter = None  # type: ignore
    Histogram = None  # type: ignore
    UpDownCounter = None  # type: ignore

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Global state to track instrumentation
_instrumented = False
_tracer_provider: Optional[Any] = None
_meter_provider: Optional[Any] = None

# Store original methods for uninstrumentation
_original_methods: dict[str, Any] = {}


def setup_otel(
    service_name: str = "mcp-compose",
    service_version: str = "1.0.0",
    *,
    token: Optional[str] = None,
    project: Optional[str] = None,
    url: Optional[str] = None,
    instrument: bool = True,
    enable_metrics: bool = True,
) -> Tuple[Any, Any]:
    """
    Setup OpenTelemetry tracing and metrics for mcp-compose with Logfire.
    
    This is the recommended way to enable observability. It configures the
    TracerProvider, MeterProvider, OTLP exporters, and optionally instruments mcp-compose.
    
    Args:
        service_name: Name of the service for tracing (default: "mcp-compose")
        service_version: Version of the service (default: "1.0.0")
        token: Logfire write token. If not provided, reads from DATALAYER_LOGFIRE_TOKEN env var.
        project: Logfire project name. If not provided, reads from DATALAYER_LOGFIRE_PROJECT env var.
        url: Logfire URL. If not provided, reads from DATALAYER_LOGFIRE_URL env var.
        instrument: Whether to instrument mcp-compose classes (default: True)
        enable_metrics: Whether to enable metrics collection (default: True)
    
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
    global _tracer_provider, _meter_provider
    
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
    
    # Configure trace exporter with endpoint and token
    trace_exporter = OTLPSpanExporter(
        endpoint=f'{url}/v1/traces',
        headers={'Authorization': token},
    )
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
    })
    
    # Setup tracer provider
    span_processor = BatchSpanProcessor(trace_exporter)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(span_processor)
    
    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    
    # Setup metrics if available and enabled
    if enable_metrics and METRICS_AVAILABLE:
        try:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            
            metric_exporter = OTLPMetricExporter(
                endpoint=f'{url}/v1/metrics',
                headers={'Authorization': token},
            )
            
            metric_reader = PeriodicExportingMetricReader(
                metric_exporter,
                export_interval_millis=60000,  # Export every 60 seconds
            )
            
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
            metrics.set_meter_provider(meter_provider)
            _meter_provider = meter_provider
            
            logger.info("OpenTelemetry metrics enabled")
        except ImportError:
            logger.warning("Metrics exporter not available, metrics disabled")
    
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


def get_meter(name: str = "mcp-compose") -> Optional[Any]:
    """
    Get a meter from the configured provider.
    
    Args:
        name: Name for the meter (default: "mcp-compose")
    
    Returns:
        Meter instance, or None if metrics are not configured.
    """
    if _meter_provider is not None:
        return _meter_provider.get_meter(name)
    if METRICS_AVAILABLE:
        return metrics.get_meter(name)
    return None


# ============================================================================
# Metrics definitions
# ============================================================================

class MCPComposeMetrics:
    """Container for mcp-compose metrics instruments."""
    
    def __init__(self, meter: Any):
        """Initialize metrics instruments."""
        # Tool metrics
        self.tool_calls_total = meter.create_counter(
            name="mcp_compose.tool_calls_total",
            description="Total number of tool calls",
            unit="1",
        )
        
        self.tool_call_duration = meter.create_histogram(
            name="mcp_compose.tool_call_duration_seconds",
            description="Duration of tool calls in seconds",
            unit="s",
        )
        
        self.tool_call_errors = meter.create_counter(
            name="mcp_compose.tool_call_errors_total",
            description="Total number of tool call errors",
            unit="1",
        )
        
        # Process metrics
        self.active_processes = meter.create_up_down_counter(
            name="mcp_compose.active_processes",
            description="Number of active MCP server processes",
            unit="1",
        )
        
        self.process_restarts = meter.create_counter(
            name="mcp_compose.process_restarts_total",
            description="Total number of process restarts",
            unit="1",
        )
        
        # Request metrics
        self.jsonrpc_requests_total = meter.create_counter(
            name="mcp_compose.jsonrpc_requests_total",
            description="Total number of JSON-RPC requests",
            unit="1",
        )
        
        self.jsonrpc_request_duration = meter.create_histogram(
            name="mcp_compose.jsonrpc_request_duration_seconds",
            description="Duration of JSON-RPC requests in seconds",
            unit="s",
        )
        
        self.jsonrpc_errors_total = meter.create_counter(
            name="mcp_compose.jsonrpc_errors_total",
            description="Total number of JSON-RPC errors",
            unit="1",
        )
        
        # Discovery metrics
        self.tools_discovered = meter.create_counter(
            name="mcp_compose.tools_discovered_total",
            description="Total number of tools discovered",
            unit="1",
        )
        
        self.servers_connected = meter.create_up_down_counter(
            name="mcp_compose.servers_connected",
            description="Number of connected MCP servers",
            unit="1",
        )
        
        # HTTP/Transport metrics
        self.http_requests_total = meter.create_counter(
            name="mcp_compose.http_requests_total",
            description="Total number of HTTP requests",
            unit="1",
        )
        
        self.http_request_duration = meter.create_histogram(
            name="mcp_compose.http_request_duration_seconds",
            description="Duration of HTTP requests in seconds",
            unit="s",
        )


# Global metrics instance
_metrics: Optional[MCPComposeMetrics] = None


def instrument_mcp_compose(
    logfire_instance: Any = None,
    *,
    tracer_provider: Optional["TracerProvider"] = None,
    meter_provider: Optional["MeterProvider"] = None,
    capture_tool_arguments: bool = True,
    capture_tool_results: bool = True,
    capture_headers: bool = False,
    capture_request_body: bool = False,
    capture_response_body: bool = False,
) -> None:
    """
    Instrument mcp-compose for OpenTelemetry tracing and metrics.
    
    This follows the Logfire pattern of external monkey-patching - the core
    mcp-compose code is not modified, instrumentation happens from outside.
    
    Args:
        logfire_instance: Optional Logfire instance to use for tracing.
            If provided, uses Logfire's tracer provider.
        tracer_provider: Optional OpenTelemetry TracerProvider.
            If not provided, uses the global tracer provider.
        meter_provider: Optional OpenTelemetry MeterProvider.
            If not provided, uses the global meter provider.
        capture_tool_arguments: Whether to capture tool call arguments as span attributes.
        capture_tool_results: Whether to capture tool call results as span attributes.
        capture_headers: Whether to capture HTTP headers.
        capture_request_body: Whether to capture HTTP request bodies.
        capture_response_body: Whether to capture HTTP response bodies.
    
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
    global _instrumented, _metrics
    
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
        if hasattr(logfire_instance, 'config') and hasattr(logfire_instance.config, 'get_meter_provider'):
            meter_provider = logfire_instance.config.get_meter_provider()
        if tracer_provider is None:
            # Logfire configures the global tracer provider, so use that
            tracer_provider = trace.get_tracer_provider()
    elif tracer_provider is None:
        # Use global tracer provider
        tracer_provider = trace.get_tracer_provider()
    
    if meter_provider is None and METRICS_AVAILABLE:
        meter_provider = _meter_provider or metrics.get_meter_provider()
    
    tracer = tracer_provider.get_tracer("mcp_compose", "0.1.0")
    
    # Initialize metrics if available
    if meter_provider is not None and METRICS_AVAILABLE:
        meter = meter_provider.get_meter("mcp_compose", "0.1.0")
        _metrics = MCPComposeMetrics(meter)
        logger.info("mcp-compose metrics enabled")
    
    # Create config for capture settings
    capture_config = {
        "tool_arguments": capture_tool_arguments,
        "tool_results": capture_tool_results,
        "headers": capture_headers,
        "request_body": capture_request_body,
        "response_body": capture_response_body,
    }
    
    # Instrument the various components
    _instrument_tool_proxy(tracer, capture_config)
    _instrument_composer(tracer)
    _instrument_tool_manager(tracer)
    _instrument_process_manager(tracer)
    _instrument_process(tracer)
    _instrument_transport(tracer, capture_config)
    _instrument_fastmcp(tracer, capture_config)
    
    _instrumented = True
    logger.info("mcp-compose instrumentation enabled")


def uninstrument_mcp_compose() -> None:
    """Remove mcp-compose instrumentation and restore original methods."""
    global _instrumented, _metrics
    
    # Restore original methods
    for key, original in _original_methods.items():
        parts = key.rsplit(".", 1)
        if len(parts) == 2:
            module_path, method_name = parts
            try:
                # Get the class/module
                module = None
                if module_path == "ToolProxy":
                    from .tool_proxy import ToolProxy
                    module = ToolProxy
                elif module_path == "MCPServerComposer":
                    from .composer import MCPServerComposer
                    module = MCPServerComposer
                elif module_path == "ToolManager":
                    from .tool_manager import ToolManager
                    module = ToolManager
                elif module_path == "ProcessManager":
                    from .process_manager import ProcessManager
                    module = ProcessManager
                elif module_path == "Process":
                    from .process import Process
                    module = Process
                elif module_path == "HttpStreamTransport":
                    from .transport.http_stream import HttpStreamTransport
                    module = HttpStreamTransport
                elif module_path == "FastMCPToolManager":
                    from mcp.server.fastmcp.tools import ToolManager as FastMCPToolManager
                    module = FastMCPToolManager
                elif module_path == "FastMCP":
                    from mcp.server.fastmcp import FastMCP
                    module = FastMCP
                elif module_path == "MCPServer":
                    from mcp.server.fastmcp.server import MCPServer
                    module = MCPServer
                elif module_path == "LowLevelServer":
                    from mcp.server.lowlevel.server import Server as LowLevelServer
                    module = LowLevelServer
                elif module_path == "LowLevelServer.run":
                    from mcp.server.lowlevel.server import Server as LowLevelServer
                    module = LowLevelServer
                    method_name = "run"
                elif module_path == "LowLevelServer._handle_request":
                    from mcp.server.lowlevel.server import Server as LowLevelServer
                    module = LowLevelServer
                    method_name = "_handle_request"
                
                elif module_path == "FastMCP.run_stdio_async":
                    from mcp.server.fastmcp import FastMCP
                    module = FastMCP
                    method_name = "run_stdio_async"

                if module is not None:
                    setattr(module, method_name, original)
            except Exception as e:
                logger.debug(f"Failed to restore {key}: {e}")
    
    _original_methods.clear()
    _metrics = None
    _instrumented = False
    logger.info("mcp-compose instrumentation disabled")


def _instrument_tool_proxy(
    tracer: Any,
    capture_config: dict,
) -> None:
    """Instrument ToolProxy for tracing tool discovery and calls."""
    try:
        from .tool_proxy import ToolProxy
    except ImportError:
        logger.debug("ToolProxy not available, skipping instrumentation")
        return
    
    capture_arguments = capture_config.get("tool_arguments", True)
    capture_results = capture_config.get("tool_results", True)
    
    # Store original methods
    _original_methods["ToolProxy.discover_tools"] = ToolProxy.discover_tools
    _original_methods["ToolProxy._send_request"] = ToolProxy._send_request
    
    # Instrument discover_tools
    original_discover_tools = ToolProxy.discover_tools
    
    @functools.wraps(original_discover_tools)
    async def traced_discover_tools(self: Any, server_name: str, process: Any) -> None:
        start_time = time.time()
        
        with tracer.start_as_current_span(
            f"mcp.discover_tools",
            kind=SpanKind.CLIENT,
        ) as span:
            span.set_attribute("mcp.server.name", server_name)
            span.set_attribute("mcp.operation", "discover_tools")
            span.set_attribute("rpc.system", "jsonrpc")
            
            try:
                result = await original_discover_tools(self, server_name, process)
                
                # Record discovered tools count
                tools_count = 0
                if hasattr(self, 'server_tools') and server_name in self.server_tools:
                    tools_count = len(self.server_tools[server_name])
                    span.set_attribute("mcp.tools.discovered_count", tools_count)
                
                # Record metrics
                if _metrics is not None:
                    _metrics.tools_discovered.add(tools_count, {"server": server_name})
                    _metrics.servers_connected.add(1, {"server": server_name})
                
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                duration = time.time() - start_time
                span.set_attribute("mcp.duration_seconds", duration)
    
    ToolProxy.discover_tools = traced_discover_tools
    
    # Instrument _send_request with comprehensive tracing
    original_send_request = ToolProxy._send_request
    
    @functools.wraps(original_send_request)
    async def traced_send_request(self: Any, process: Any, request: dict) -> Any:
        method = request.get("method", "unknown")
        request_id = request.get("id", "notification")
        span_name = f"mcp.request: {method}"
        start_time = time.time()
        
        with tracer.start_as_current_span(
            span_name,
            kind=SpanKind.CLIENT,
        ) as span:
            # JSON-RPC semantic conventions
            span.set_attribute("rpc.system", "jsonrpc")
            span.set_attribute("rpc.method", method)
            span.set_attribute("rpc.jsonrpc.version", "2.0")
            span.set_attribute("rpc.jsonrpc.request_id", str(request_id))
            
            # Capture tool-specific attributes
            if capture_arguments and method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name", "unknown")
                span.set_attribute("mcp.tool.name", tool_name)
                span_name = f"mcp.tool.call: {tool_name}"
                span.update_name(span_name)
                
                arguments = params.get("arguments", {})
                if arguments:
                    try:
                        args_str = json.dumps(arguments)
                        if len(args_str) > 4096:
                            args_str = args_str[:4096] + "...(truncated)"
                        span.set_attribute("mcp.tool.arguments", args_str)
                    except (TypeError, ValueError):
                        span.set_attribute("mcp.tool.arguments", str(arguments)[:4096])
            
            # Record request metrics
            if _metrics is not None:
                _metrics.jsonrpc_requests_total.add(1, {"method": method})
            
            try:
                response = await original_send_request(self, process, request)
                duration = time.time() - start_time
                
                span.set_attribute("mcp.duration_seconds", duration)
                
                if response:
                    if "error" in response:
                        error = response["error"]
                        error_code = error.get("code", -1)
                        error_message = error.get("message", "")
                        
                        span.set_status(Status(StatusCode.ERROR, error_message))
                        span.set_attribute("rpc.jsonrpc.error_code", error_code)
                        span.set_attribute("rpc.jsonrpc.error_message", error_message)
                        
                        # Record error metrics
                        if _metrics is not None:
                            _metrics.jsonrpc_errors_total.add(1, {
                                "method": method,
                                "error_code": str(error_code),
                            })
                            if method == "tools/call":
                                tool_name = request.get("params", {}).get("name", "unknown")
                                _metrics.tool_call_errors.add(1, {"tool": tool_name})
                    else:
                        span.set_status(Status(StatusCode.OK))
                        
                        if capture_results and "result" in response:
                            result = response["result"]
                            try:
                                result_str = json.dumps(result)
                                if len(result_str) > 4096:
                                    result_str = result_str[:4096] + "...(truncated)"
                                span.set_attribute("mcp.response.result", result_str)
                            except (TypeError, ValueError):
                                span.set_attribute("mcp.response.result", str(result)[:4096])
                
                # Record duration metrics
                if _metrics is not None:
                    _metrics.jsonrpc_request_duration.record(duration, {"method": method})
                    if method == "tools/call":
                        tool_name = request.get("params", {}).get("name", "unknown")
                        _metrics.tool_calls_total.add(1, {"tool": tool_name})
                        _metrics.tool_call_duration.record(duration, {"tool": tool_name})
                
                return response
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                
                if _metrics is not None:
                    _metrics.jsonrpc_errors_total.add(1, {"method": method, "error_code": "exception"})
                    if method == "tools/call":
                        tool_name = request.get("params", {}).get("name", "unknown")
                        _metrics.tool_call_errors.add(1, {"tool": tool_name})
                
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
        _original_methods["MCPServerComposer.compose_from_pyproject"] = MCPServerComposer.compose_from_pyproject
        original_compose_from_pyproject = MCPServerComposer.compose_from_pyproject
        
        @functools.wraps(original_compose_from_pyproject)
        def traced_compose_from_pyproject(self: Any, *args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            
            with tracer.start_as_current_span(
                "mcp.compose_from_pyproject",
                kind=SpanKind.INTERNAL,
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
                    span.set_attribute("mcp.duration_seconds", time.time() - start_time)
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        MCPServerComposer.compose_from_pyproject = traced_compose_from_pyproject
    
    # Instrument compose_from_discovery
    if hasattr(MCPServerComposer, 'compose_from_discovery'):
        _original_methods["MCPServerComposer.compose_from_discovery"] = MCPServerComposer.compose_from_discovery
        original_compose_from_discovery = MCPServerComposer.compose_from_discovery
        
        @functools.wraps(original_compose_from_discovery)
        async def traced_compose_from_discovery(self: Any, *args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            
            with tracer.start_as_current_span(
                "mcp.compose_from_discovery",
                kind=SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.operation", "compose_from_discovery")
                span.set_attribute("mcp.composed_server.name", self.composed_server_name)
                
                try:
                    result = await original_compose_from_discovery(self, *args, **kwargs)
                    
                    # Record composition stats
                    span.set_attribute("mcp.tools.count", len(self.composed_tools))
                    span.set_attribute("mcp.prompts.count", len(self.composed_prompts))
                    span.set_attribute("mcp.conflicts.resolved", len(self.conflicts_resolved))
                    span.set_attribute("mcp.duration_seconds", time.time() - start_time)
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        MCPServerComposer.compose_from_discovery = traced_compose_from_discovery
    
    # Instrument invoke_tool for server-side tracing
    if hasattr(MCPServerComposer, 'invoke_tool'):
        _original_methods["MCPServerComposer.invoke_tool"] = MCPServerComposer.invoke_tool
        original_invoke_tool = MCPServerComposer.invoke_tool
        
        @functools.wraps(original_invoke_tool)
        async def traced_invoke_tool(self: Any, tool_id: str, arguments: dict, *args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            
            with tracer.start_as_current_span(
                f"mcp.server.invoke_tool: {tool_id}",
                kind=SpanKind.SERVER,
            ) as span:
                span.set_attribute("mcp.operation", "invoke_tool")
                span.set_attribute("mcp.tool.id", tool_id)
                span.set_attribute("rpc.system", "jsonrpc")
                span.set_attribute("rpc.method", "tools/call")
                
                # Parse tool_id to get server and tool name
                parts = tool_id.split(".", 1)
                if len(parts) == 2:
                    span.set_attribute("mcp.server.name", parts[0])
                    span.set_attribute("mcp.tool.name", parts[1])
                
                # Capture arguments
                if arguments:
                    try:
                        args_str = json.dumps(arguments)
                        if len(args_str) > 4096:
                            args_str = args_str[:4096] + "...(truncated)"
                        span.set_attribute("mcp.tool.arguments", args_str)
                    except (TypeError, ValueError):
                        span.set_attribute("mcp.tool.arguments", str(arguments)[:4096])
                
                try:
                    result = await original_invoke_tool(self, tool_id, arguments, *args, **kwargs)
                    duration = time.time() - start_time
                    
                    span.set_attribute("mcp.duration_seconds", duration)
                    
                    # Capture result preview
                    if result is not None:
                        try:
                            result_str = json.dumps(result) if not isinstance(result, str) else result
                            if len(result_str) > 1024:
                                result_str = result_str[:1024] + "...(truncated)"
                            span.set_attribute("mcp.tool.result_preview", result_str)
                        except (TypeError, ValueError):
                            pass
                    
                    # Record metrics
                    if _metrics is not None:
                        tool_name = parts[1] if len(parts) == 2 else tool_id
                        _metrics.tool_calls_total.add(1, {"tool": tool_name})
                        _metrics.tool_call_duration.record(duration, {"tool": tool_name})
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    
                    if _metrics is not None:
                        tool_name = parts[1] if len(parts) == 2 else tool_id
                        _metrics.tool_call_errors.add(1, {"tool": tool_name})
                    
                    raise
        
        MCPServerComposer.invoke_tool = traced_invoke_tool


def _instrument_tool_manager(tracer: Any) -> None:
    """Instrument ToolManager for tracing tool registration and resolution."""
    try:
        from .tool_manager import ToolManager
    except ImportError:
        logger.debug("ToolManager not available, skipping instrumentation")
        return
    
    # Instrument register_tools
    _original_methods["ToolManager.register_tools"] = ToolManager.register_tools
    original_register_tools = ToolManager.register_tools
    
    @functools.wraps(original_register_tools)
    def traced_register_tools(
        self: Any,
        server_name: str,
        tools: dict,
        server_version: Optional[str] = None,
    ) -> dict:
        start_time = time.time()
        
        with tracer.start_as_current_span(
            f"mcp.register_tools: {server_name}",
            kind=SpanKind.INTERNAL,
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
                span.set_attribute("mcp.duration_seconds", time.time() - start_time)
                
                # Record metrics
                if _metrics is not None:
                    _metrics.tools_discovered.add(len(result), {"server": server_name})
                
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
        _original_methods["ProcessManager.start_process"] = ProcessManager.start_process
        original_start_process = ProcessManager.start_process
        
        @functools.wraps(original_start_process)
        async def traced_start_process(self: Any, name: str, *args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            
            with tracer.start_as_current_span(
                f"mcp.process.start: {name}",
                kind=SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.operation", "start_process")
                span.set_attribute("mcp.process.name", name)
                
                try:
                    result = await original_start_process(self, name, *args, **kwargs)
                    
                    span.set_attribute("mcp.duration_seconds", time.time() - start_time)
                    
                    # Record metrics
                    if _metrics is not None:
                        _metrics.active_processes.add(1, {"process": name})
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        ProcessManager.start_process = traced_start_process
    
    # Instrument stop_process
    if hasattr(ProcessManager, 'stop_process'):
        _original_methods["ProcessManager.stop_process"] = ProcessManager.stop_process
        original_stop_process = ProcessManager.stop_process
        
        @functools.wraps(original_stop_process)
        async def traced_stop_process(self: Any, name: str, *args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(
                f"mcp.process.stop: {name}",
                kind=SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.operation", "stop_process")
                span.set_attribute("mcp.process.name", name)
                
                try:
                    result = await original_stop_process(self, name, *args, **kwargs)
                    
                    # Record metrics
                    if _metrics is not None:
                        _metrics.active_processes.add(-1, {"process": name})
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        ProcessManager.stop_process = traced_stop_process
    
    # Instrument restart_process
    if hasattr(ProcessManager, 'restart_process'):
        _original_methods["ProcessManager.restart_process"] = ProcessManager.restart_process
        original_restart_process = ProcessManager.restart_process
        
        @functools.wraps(original_restart_process)
        async def traced_restart_process(self: Any, name: str, *args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(
                f"mcp.process.restart: {name}",
                kind=SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.operation", "restart_process")
                span.set_attribute("mcp.process.name", name)
                
                try:
                    result = await original_restart_process(self, name, *args, **kwargs)
                    
                    # Record metrics
                    if _metrics is not None:
                        _metrics.process_restarts.add(1, {"process": name})
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        ProcessManager.restart_process = traced_restart_process


def _instrument_process(tracer: Any) -> None:
    """Instrument Process class for detailed process lifecycle tracing."""
    try:
        from .process import Process
    except ImportError:
        logger.debug("Process not available, skipping instrumentation")
        return
    
    # Instrument start
    if hasattr(Process, 'start'):
        _original_methods["Process.start"] = Process.start
        original_start = Process.start
        
        @functools.wraps(original_start)
        async def traced_start(self: Any) -> None:
            start_time = time.time()
            
            with tracer.start_as_current_span(
                f"mcp.process.lifecycle.start: {self.name}",
                kind=SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.process.name", self.name)
                span.set_attribute("mcp.process.command", " ".join(self.command) if self.command else "")
                span.set_attribute("mcp.operation", "process_start")
                
                try:
                    await original_start(self)
                    
                    span.set_attribute("mcp.process.pid", self.pid or 0)
                    span.set_attribute("mcp.process.state", str(self.state.value) if hasattr(self.state, 'value') else str(self.state))
                    span.set_attribute("mcp.duration_seconds", time.time() - start_time)
                    
                    if _metrics is not None:
                        _metrics.active_processes.add(1, {"process": self.name})
                    
                    span.set_status(Status(StatusCode.OK))
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        Process.start = traced_start
    
    # Instrument stop
    if hasattr(Process, 'stop'):
        _original_methods["Process.stop"] = Process.stop
        original_stop = Process.stop
        
        @functools.wraps(original_stop)
        async def traced_stop(self: Any, timeout: float = 5.0) -> None:
            with tracer.start_as_current_span(
                f"mcp.process.lifecycle.stop: {self.name}",
                kind=SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("mcp.process.name", self.name)
                span.set_attribute("mcp.process.pid", self.pid or 0)
                span.set_attribute("mcp.operation", "process_stop")
                span.set_attribute("mcp.process.stop_timeout", timeout)
                
                try:
                    await original_stop(self, timeout)
                    
                    span.set_attribute("mcp.process.exit_code", self._exit_code if hasattr(self, '_exit_code') else -1)
                    
                    if _metrics is not None:
                        _metrics.active_processes.add(-1, {"process": self.name})
                    
                    span.set_status(Status(StatusCode.OK))
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        Process.stop = traced_stop
    
    # Instrument send_message for detailed I/O tracing
    if hasattr(Process, 'send_message'):
        _original_methods["Process.send_message"] = Process.send_message
        original_send_message = Process.send_message
        
        @functools.wraps(original_send_message)
        async def traced_send_message(self: Any, message: dict) -> None:
            method = message.get("method", "unknown")
            
            with tracer.start_as_current_span(
                f"mcp.process.send: {method}",
                kind=SpanKind.PRODUCER,
            ) as span:
                span.set_attribute("mcp.process.name", self.name)
                span.set_attribute("rpc.method", method)
                span.set_attribute("rpc.system", "jsonrpc")
                
                # Capture message size
                try:
                    msg_str = json.dumps(message)
                    span.set_attribute("mcp.message.size_bytes", len(msg_str))
                except:
                    pass
                
                try:
                    await original_send_message(self, message)
                    span.set_status(Status(StatusCode.OK))
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        Process.send_message = traced_send_message
    
    # Instrument read_message for detailed I/O tracing
    if hasattr(Process, 'read_message'):
        _original_methods["Process.read_message"] = Process.read_message
        original_read_message = Process.read_message
        
        @functools.wraps(original_read_message)
        async def traced_read_message(self: Any, timeout: Optional[float] = None) -> Optional[dict]:
            with tracer.start_as_current_span(
                f"mcp.process.receive",
                kind=SpanKind.CONSUMER,
            ) as span:
                span.set_attribute("mcp.process.name", self.name)
                span.set_attribute("rpc.system", "jsonrpc")
                if timeout is not None:
                    span.set_attribute("mcp.read_timeout", timeout)
                
                try:
                    message = await original_read_message(self, timeout)
                    
                    if message is not None:
                        method = message.get("method", message.get("id", "response"))
                        span.set_attribute("rpc.method", str(method))
                        
                        # Capture message size
                        try:
                            msg_str = json.dumps(message)
                            span.set_attribute("mcp.message.size_bytes", len(msg_str))
                        except:
                            pass
                        
                        # Check for errors
                        if "error" in message:
                            error = message["error"]
                            span.set_attribute("rpc.jsonrpc.error_code", error.get("code", -1))
                            span.set_attribute("rpc.jsonrpc.error_message", error.get("message", "")[:500])
                    
                    span.set_status(Status(StatusCode.OK))
                    return message
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        Process.read_message = traced_read_message


def _instrument_transport(tracer: Any, capture_config: dict) -> None:
    """Instrument transport layer for HTTP/SSE tracing."""
    capture_headers = capture_config.get("headers", False)
    capture_request_body = capture_config.get("request_body", False)
    capture_response_body = capture_config.get("response_body", False)
    
    # Instrument HttpStreamTransport
    try:
        from .transport.http_stream import HttpStreamTransport
        
        # Instrument connect
        if hasattr(HttpStreamTransport, 'connect'):
            _original_methods["HttpStreamTransport.connect"] = HttpStreamTransport.connect
            original_connect = HttpStreamTransport.connect
            
            @functools.wraps(original_connect)
            async def traced_connect(self: Any) -> None:
                start_time = time.time()
                
                with tracer.start_as_current_span(
                    f"mcp.transport.http.connect",
                    kind=SpanKind.CLIENT,
                ) as span:
                    span.set_attribute("mcp.transport.name", self.name)
                    span.set_attribute("mcp.transport.type", "http_stream")
                    span.set_attribute("http.url", self.url)
                    span.set_attribute("http.method", "GET")
                    
                    try:
                        await original_connect(self)
                        
                        span.set_attribute("mcp.duration_seconds", time.time() - start_time)
                        
                        if _metrics is not None:
                            _metrics.http_requests_total.add(1, {
                                "method": "CONNECT",
                                "transport": "http_stream",
                            })
                        
                        span.set_status(Status(StatusCode.OK))
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
            
            HttpStreamTransport.connect = traced_connect
        
        # Instrument send
        if hasattr(HttpStreamTransport, 'send'):
            _original_methods["HttpStreamTransport.send"] = HttpStreamTransport.send
            original_send = HttpStreamTransport.send
            
            @functools.wraps(original_send)
            async def traced_send(self: Any, message: dict) -> None:
                method = message.get("method", "unknown")
                start_time = time.time()
                
                with tracer.start_as_current_span(
                    f"mcp.transport.http.send: {method}",
                    kind=SpanKind.CLIENT,
                ) as span:
                    span.set_attribute("mcp.transport.name", self.name)
                    span.set_attribute("http.url", self.url)
                    span.set_attribute("http.method", "POST")
                    span.set_attribute("rpc.method", method)
                    span.set_attribute("rpc.system", "jsonrpc")
                    
                    if capture_request_body:
                        try:
                            body_str = json.dumps(message)
                            if len(body_str) > 4096:
                                body_str = body_str[:4096] + "...(truncated)"
                            span.set_attribute("http.request.body", body_str)
                        except:
                            pass
                    
                    try:
                        await original_send(self, message)
                        duration = time.time() - start_time
                        
                        span.set_attribute("mcp.duration_seconds", duration)
                        
                        if _metrics is not None:
                            _metrics.http_requests_total.add(1, {"method": "POST", "transport": "http_stream"})
                            _metrics.http_request_duration.record(duration, {"method": "POST", "transport": "http_stream"})
                        
                        span.set_status(Status(StatusCode.OK))
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
            
            HttpStreamTransport.send = traced_send
    
    except ImportError:
        logger.debug("HttpStreamTransport not available, skipping instrumentation")
    
    # Instrument SSETransport
    try:
        from .transport.sse_server import SSETransport
        
        if hasattr(SSETransport, 'connect'):
            _original_methods["SSETransport.connect"] = SSETransport.connect
            original_sse_connect = SSETransport.connect
            
            @functools.wraps(original_sse_connect)
            async def traced_sse_connect(self: Any) -> None:
                with tracer.start_as_current_span(
                    f"mcp.transport.sse.connect",
                    kind=SpanKind.SERVER,
                ) as span:
                    span.set_attribute("mcp.transport.name", self.name)
                    span.set_attribute("mcp.transport.type", "sse")
                    span.set_attribute("server.address", self.host)
                    span.set_attribute("server.port", self.port)
                    
                    try:
                        await original_sse_connect(self)
                        span.set_status(Status(StatusCode.OK))
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
            
            SSETransport.connect = traced_sse_connect
    
    except ImportError:
        logger.debug("SSETransport not available, skipping instrumentation")


def _instrument_fastmcp(tracer: Any, capture_config: dict) -> None:
    """
    Instrument FastMCP server for tracing incoming tool calls.
    
    This instruments the FastMCP ToolManager which handles all incoming
    tools/call requests from agents.
    """
    logger.info("Starting FastMCP instrumentation")
    capture_arguments = capture_config.get("tool_arguments", True)
    capture_results = capture_config.get("tool_results", True)
    
    try:
        from mcp.server.fastmcp.tools import ToolManager as FastMCPToolManager
        from mcp.server.fastmcp.server import StreamableHTTPSessionManager
        
        # Instrument call_tool method which handles incoming tool calls
        if hasattr(FastMCPToolManager, 'call_tool'):
            _original_methods["FastMCPToolManager.call_tool"] = FastMCPToolManager.call_tool
            original_call_tool = FastMCPToolManager.call_tool
            
            @functools.wraps(original_call_tool)
            async def traced_call_tool(
                self: Any,
                name: str,
                arguments: dict,
                context: Any = None,
                convert_result: bool = False,
            ) -> Any:
                start_time = time.time()
                
                with tracer.start_as_current_span(
                    f"mcp.server.tool.call: {name}",
                    kind=SpanKind.SERVER,
                ) as span:
                    span.set_attribute("mcp.tool.name", name)
                    span.set_attribute("mcp.operation", "tool_call")
                    span.set_attribute("rpc.system", "jsonrpc")
                    span.set_attribute("rpc.method", "tools/call")
                    
                    # Capture arguments
                    if capture_arguments and arguments:
                        try:
                            args_str = json.dumps(arguments)
                            if len(args_str) > 4096:
                                args_str = args_str[:4096] + "...(truncated)"
                            span.set_attribute("mcp.tool.arguments", args_str)
                        except (TypeError, ValueError):
                            span.set_attribute("mcp.tool.arguments", str(arguments)[:4096])
                    
                    try:
                        result = await original_call_tool(
                            self,
                            name,
                            arguments,
                            context=context,
                            convert_result=convert_result,
                        )
                        duration = time.time() - start_time
                        
                        span.set_attribute("mcp.duration_seconds", duration)
                        
                        # Capture result preview
                        if capture_results and result is not None:
                            try:
                                # Handle list of content items
                                if isinstance(result, list):
                                    result_preview = []
                                    for item in result[:5]:  # First 5 items
                                        if hasattr(item, 'text'):
                                            result_preview.append(item.text[:200])
                                        else:
                                            result_preview.append(str(item)[:200])
                                    span.set_attribute("mcp.tool.result_preview", str(result_preview))
                                else:
                                    result_str = str(result)[:1024]
                                    span.set_attribute("mcp.tool.result_preview", result_str)
                            except Exception:
                                pass
                        
                        # Record metrics
                        if _metrics is not None:
                            _metrics.tool_calls_total.add(1, {"tool": name, "source": "fastmcp"})
                            _metrics.tool_call_duration.record(duration, {"tool": name})
                        
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        duration = time.time() - start_time
                        span.set_attribute("mcp.duration_seconds", duration)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        
                        if _metrics is not None:
                            _metrics.tool_call_errors.add(1, {"tool": name})
                        
                        raise
            
            FastMCPToolManager.call_tool = traced_call_tool
            logger.debug("FastMCP ToolManager.call_tool instrumented")
    
    except ImportError:
        logger.debug("FastMCP ToolManager not available, skipping instrumentation")
    
    # Also try to instrument the MCP server's request handler for list operations
    try:
        from mcp.server.fastmcp import FastMCP
        
        # Instrument list_tools to trace tools/list requests
        if hasattr(FastMCP, '_mcp_list_tools'):
            _original_methods["FastMCP._mcp_list_tools"] = FastMCP._mcp_list_tools
            original_list_tools = FastMCP._mcp_list_tools
            
            @functools.wraps(original_list_tools)
            async def traced_list_tools(self: Any) -> Any:
                with tracer.start_as_current_span(
                    "mcp.server.tools.list",
                    kind=SpanKind.SERVER,
                ) as span:
                    span.set_attribute("mcp.operation", "list_tools")
                    span.set_attribute("rpc.system", "jsonrpc")
                    span.set_attribute("rpc.method", "tools/list")
                    
                    try:
                        result = await original_list_tools(self)
                        
                        # Record tools count
                        if result and hasattr(result, 'tools'):
                            span.set_attribute("mcp.tools.count", len(result.tools))
                        
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
            
            FastMCP._mcp_list_tools = traced_list_tools
            logger.debug("FastMCP._mcp_list_tools instrumented")
    
    except ImportError:
        logger.debug("FastMCP not available for list_tools instrumentation")

    # Instrument FastMCP.run_stdio_async
    try:
        from mcp.server.fastmcp import FastMCP
        
        if hasattr(FastMCP, 'run_stdio_async'):
            _original_methods["FastMCP.run_stdio_async"] = FastMCP.run_stdio_async
            original_run_stdio = FastMCP.run_stdio_async

            @functools.wraps(original_run_stdio)
            async def traced_run_stdio(self: Any) -> Any:
                with tracer.start_as_current_span(
                    "mcp.server.run_stdio",
                    kind=SpanKind.SERVER,
                ) as span:
                    span.set_attribute("mcp.transport", "stdio")
                    logger.info("Starting traced run_stdio_async") 
                    try:
                        return await original_run_stdio(self)
                    except Exception as e:
                        span.record_exception(e)
                        raise

            FastMCP.run_stdio_async = traced_run_stdio
            logger.info("FastMCP.run_stdio_async instrumented successfully")
    except ImportError:
        logger.debug("FastMCP not available for run_stdio_async instrumentation")

    # Instrument LowLevelServer.run to trace the main server loop
    try:
        from mcp.server.lowlevel.server import Server as LowLevelServer
        
        if hasattr(LowLevelServer, 'run'):
            _original_methods["LowLevelServer.run"] = LowLevelServer.run
            original_run = LowLevelServer.run

            @functools.wraps(original_run)
            async def traced_run(
                self: Any,
                read_stream: Any,
                write_stream: Any,
                initialization_options: Any,
                raise_exceptions: bool = False,
                stateless: bool = False,
            ) -> Any:
                with tracer.start_as_current_span(
                    "mcp.server.run",
                    kind=SpanKind.SERVER,
                ) as span:
                    span.set_attribute("mcp.transport", "stdio" if "stdio" in str(read_stream).lower() else "unknown")
                    try:
                        return await original_run(
                            self, read_stream, write_stream, initialization_options, raise_exceptions, stateless
                        )
                    except Exception as e:
                        span.record_exception(e)
                        raise

            LowLevelServer.run = traced_run
            logger.info("LowLevelServer.run instrumented successfully")
    except ImportError:
        logger.debug("LowLevelServer not available for run instrumentation")

    # Instrument LowLevelServer._handle_request to trace request handling
    try:
        from mcp.server.lowlevel.server import Server as LowLevelServer

        if hasattr(LowLevelServer, '_handle_request'):
            _original_methods["LowLevelServer._handle_request"] = LowLevelServer._handle_request
            original_handle_request = LowLevelServer._handle_request

            @functools.wraps(original_handle_request)
            async def traced_handle_request(
                self: Any,
                message: Any,
                request: Any,
                *args: Any,
                **kwargs: Any,
            ) -> Any:
                method = getattr(request, 'method', 'unknown')
                span_name = f"mcp.server.request: {method}"
                
                # Check for tool name in CallTool
                if hasattr(request, 'params') and hasattr(request.params, 'name'):
                    tool_name = request.params.name
                    span_name += f" {tool_name}"
                
                # Create a specific context to detach from the parent 'run' span if needed
                # However, for request handlers, we usually want them to appear as distinct operations
                # We can use links if we want to refer back to the server process
                
                # NOTE: To fix "Incomplete" traces in visualizers that expect request-response to be 
                # distinct roots or not nested in a long-running process span, we can detach context.
                # However, keeping them nested is semantically correct for an embedded server.
                # The "Incomplete" message in Logfire usually relates to missing parents or unclosed spans.
                # If these are nested in 'mcp.server.run' which never closes, Logfire might flag them.
                
                # Let's try creating a NEW ROOT span for each request to ensure they show up as 
                # complete, independent transactions in the trace list.
                
                with tracer.start_as_current_span(
                    span_name,
                    kind=SpanKind.SERVER,
                    context=context.Context(), # Create as root span (detach from mcp.server.run)
                ) as span:
                    span.set_attribute("mcp.message.type", "request")
                    span.set_attribute("mcp.message.method", method)
                    span.set_attribute("rpc.system", "jsonrpc")

                    # Capture request params
                    try:
                        if hasattr(request, 'model_dump_json'):
                            # Pydantic v2
                            span.set_attribute("mcp.message.params", request.model_dump_json())
                        elif hasattr(request, 'json'):
                            # Pydantic v1
                            span.set_attribute("mcp.message.params", request.json())
                        else:
                            span.set_attribute("mcp.message.params", str(request))
                    except Exception:
                        pass
                    
                    try:
                        result = await original_handle_request(self, message, request, *args, **kwargs)
                        
                        # Capture result
                        try:
                            if result is not None:
                                if hasattr(result, 'model_dump_json'):
                                    span.set_attribute("mcp.message.result", result.model_dump_json())
                                elif hasattr(result, 'json'):
                                    span.set_attribute("mcp.message.result", result.json())
                                else:
                                    span.set_attribute("mcp.message.result", str(result))
                        except Exception:
                            pass
                            
                        return result
                    except Exception as e:
                        span.record_exception(e)
                        raise

            LowLevelServer._handle_request = traced_handle_request
            logger.info("LowLevelServer._handle_request instrumented successfully")
    except ImportError:
        logger.debug("LowLevelServer not available for _handle_request instrumentation")

    # Instrument Server._handle_message to trace all inbound MCP messages
    try:
        # Import the ACTUAL Server class from lowlevel module
        # (MCPServer in fastmcp.server is just a re-export)
        from mcp.server.lowlevel.server import Server as LowLevelServer
        import sys

        if hasattr(LowLevelServer, '_handle_message'):
            logger.debug(f"Instrumenting LowLevelServer._handle_message")
            _original_methods["LowLevelServer._handle_message"] = LowLevelServer._handle_message
            original_handle_message = LowLevelServer._handle_message

            @functools.wraps(original_handle_message)
            async def traced_handle_message(
                self: Any,
                message: Any,
                session: Any,
                lifespan_context: Any,
                raise_exceptions: bool = False,
            ) -> Any:
                # logger.info(f"MCPServer._handle_message called with message type: {type(message).__name__}")
                
                # Extract request type from message
                request_type = "unknown"
                request_method = "unknown"
                
                try:
                    # Check if this is a RequestResponder (request message)
                    if hasattr(message, 'request') and hasattr(message.request, 'root'):
                        req = message.request.root
                        request_type = type(req).__name__
                        # Try to extract method from common request types
                        if hasattr(req, 'method'):
                            request_method = req.method
                        elif 'CallTool' in request_type:
                            request_method = 'tools/call'
                            if hasattr(req, 'params') and hasattr(req.params, 'name'):
                                request_method = f"tools/call:{req.params.name}"
                        elif 'ListTools' in request_type:
                            request_method = 'tools/list'
                        elif 'ListResources' in request_type:
                            request_method = 'resources/list'
                        elif 'ListPrompts' in request_type:
                            request_method = 'prompts/list'
                        elif 'Initialize' in request_type:
                            request_method = 'initialize'
                    # Check if this is a notification
                    elif hasattr(message, 'root'):
                        request_type = type(message.root).__name__
                        request_method = 'notification'
                except Exception:
                    pass

                # logger.debug(f"Tracing message: {request_method}")
                with tracer.start_as_current_span(
                    f"mcp.server.message: {request_method}",
                    kind=SpanKind.SERVER,
                ) as span:
                    span.set_attribute("mcp.message.type", request_type)
                    span.set_attribute("mcp.message.method", request_method)
                    span.set_attribute("mcp.operation", "handle_message")
                    span.set_attribute("rpc.system", "jsonrpc")

                    # Capture request params
                    try:
                        req_obj = None
                        if hasattr(message, 'request') and hasattr(message.request, 'root'):
                            req_obj = message.request.root
                        elif hasattr(message, 'root'):
                            req_obj = message.root
                        
                        if req_obj:
                            if hasattr(req_obj, 'model_dump_json'):
                                span.set_attribute("mcp.message.params", req_obj.model_dump_json())
                            elif hasattr(req_obj, 'json'):
                                span.set_attribute("mcp.message.params", req_obj.json())
                            else:
                                span.set_attribute("mcp.message.params", str(req_obj))
                    except Exception:
                        pass

                    try:
                        result = await original_handle_message(
                            self, message, session, lifespan_context, raise_exceptions
                        )
                        
                        # Capture result (note: _handle_message might return None for some message types)
                        try:
                            if result is not None:
                                if hasattr(result, 'model_dump_json'):
                                    span.set_attribute("mcp.message.result", result.model_dump_json())
                                elif hasattr(result, 'json'):
                                    span.set_attribute("mcp.message.result", result.json())
                                else:
                                    span.set_attribute("mcp.message.result", str(result))
                        except Exception:
                            pass
                            
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise

            LowLevelServer._handle_message = traced_handle_message
            logger.info("LowLevelServer._handle_message instrumented successfully")
    except ImportError:
        logger.debug("LowLevelServer not available for _handle_message instrumentation")


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


def get_server_meter(service_name: str = "mcp-compose") -> Any:
    """
    Get a meter for server-side metrics.
    
    This is used by the mcp-compose server to record metrics.
    
    Args:
        service_name: Name of the service for metrics.
        
    Returns:
        OpenTelemetry Meter instance, or None if metrics are not available.
    """
    if not METRICS_AVAILABLE:
        return None
    
    return metrics.get_meter(service_name, "0.1.0")


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
        start_time = time.time()
        
        with tracer.start_as_current_span(
            f"mcp.server.tool_call: {tool_name}",
            kind=SpanKind.SERVER,
        ) as span:
            span.set_attribute("mcp.tool.name", tool_name)
            span.set_attribute("mcp.server.name", server_name)
            span.set_attribute("mcp.operation", "tool_call")
            span.set_attribute("rpc.system", "jsonrpc")
            span.set_attribute("rpc.method", "tools/call")
            
            if capture_arguments and kwargs:
                try:
                    args_str = json.dumps(kwargs, default=str)
                    if len(args_str) > 4096:
                        args_str = args_str[:4096] + "...(truncated)"
                    span.set_attribute("mcp.tool.arguments", args_str)
                except Exception:
                    pass
            
            try:
                result = await original_func(*args, **kwargs)
                duration = time.time() - start_time
                
                span.set_attribute("mcp.duration_seconds", duration)
                
                if capture_results and result is not None:
                    try:
                        result_str = str(result)
                        if len(result_str) > 1024:
                            result_str = result_str[:1024] + "...(truncated)"
                        span.set_attribute("mcp.tool.result_preview", result_str)
                    except Exception:
                        pass
                
                # Record metrics
                if _metrics is not None:
                    _metrics.tool_calls_total.add(1, {"tool": tool_name, "server": server_name})
                    _metrics.tool_call_duration.record(duration, {"tool": tool_name})
                
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                
                if _metrics is not None:
                    _metrics.tool_call_errors.add(1, {"tool": tool_name, "server": server_name})
                
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
        f"mcp.server.startup: {service_name}",
        kind=SpanKind.INTERNAL,
    )
    span.set_attribute("mcp.server.name", service_name)
    span.set_attribute("mcp.operation", "server_startup")
    
    for key, value in config_info.items():
        try:
            span.set_attribute(f"mcp.server.config.{key}", str(value))
        except Exception:
            pass
    
    return span


# ============================================================================
# FastAPI/Starlette middleware for HTTP request tracing
# ============================================================================

def create_otel_middleware(tracer: Any = None, service_name: str = "mcp-compose"):
    """
    Create a Starlette/FastAPI middleware for tracing HTTP requests.
    
    This middleware adds OpenTelemetry tracing to all HTTP requests handled
    by the mcp-compose API server.
    
    Args:
        tracer: OpenTelemetry Tracer instance. If None, uses global tracer.
        service_name: Name of the service for tracing.
        
    Returns:
        Middleware class for use with FastAPI/Starlette.
    
    Example:
        from fastapi import FastAPI
        from mcp_compose.otel import create_otel_middleware
        
        app = FastAPI()
        app.add_middleware(create_otel_middleware())
    """
    if tracer is None:
        tracer = get_server_tracer(service_name)
    
    if tracer is None:
        # Return a no-op middleware if OTEL is not available
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class NoOpMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                return await call_next(request)
        
        return NoOpMiddleware
    
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    
    class OTelMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start_time = time.time()
            
            # Extract path and method
            method = request.method
            path = request.url.path
            
            with tracer.start_as_current_span(
                f"{method} {path}",
                kind=SpanKind.SERVER,
            ) as span:
                # HTTP semantic conventions
                span.set_attribute("http.method", method)
                span.set_attribute("http.url", str(request.url))
                span.set_attribute("http.target", path)
                span.set_attribute("http.scheme", request.url.scheme)
                span.set_attribute("http.host", request.url.netloc)
                
                # Client info
                if request.client:
                    span.set_attribute("http.client_ip", request.client.host)
                
                # User agent
                user_agent = request.headers.get("user-agent", "")
                if user_agent:
                    span.set_attribute("http.user_agent", user_agent[:500])
                
                try:
                    response = await call_next(request)
                    duration = time.time() - start_time
                    
                    # Response attributes
                    span.set_attribute("http.status_code", response.status_code)
                    span.set_attribute("mcp.duration_seconds", duration)
                    
                    # Set status based on HTTP status code
                    if response.status_code >= 500:
                        span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                    elif response.status_code >= 400:
                        span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                    else:
                        span.set_status(Status(StatusCode.OK))
                    
                    # Record metrics
                    if _metrics is not None:
                        _metrics.http_requests_total.add(1, {
                            "method": method,
                            "path": path,
                            "status_code": str(response.status_code),
                        })
                        _metrics.http_request_duration.record(duration, {
                            "method": method,
                            "path": path,
                        })
                    
                    return response
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
    
    return OTelMiddleware
