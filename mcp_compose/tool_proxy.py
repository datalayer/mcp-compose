"""
Tool Proxy Module.

This module handles communication with child MCP servers via STDIO
and proxies tool calls to them.
"""

import asyncio
import inspect
import json
import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp.tools.base import Tool
from .process import Process
from .process_manager import ProcessManager

logger = logging.getLogger(__name__)


class ToolProxy:
    """
    Proxies MCP tool calls to child STDIO processes.
    
    Handles MCP protocol communication over STDIO to discover tools
    and execute them on child servers.
    """
    
    def __init__(self, process_manager: ProcessManager, composer: Any):
        """
        Initialize tool proxy.
        
        Args:
            process_manager: ProcessManager instance managing child processes
            composer: MCPServerComposer instance for registering discovered tools
        """
        self.process_manager = process_manager
        self.composer = composer
        self.server_tools: Dict[str, Dict[str, Any]] = {}
        
    async def discover_tools(self, server_name: str, process: Process) -> None:
        """
        Discover tools from a child MCP server via STDIO.
        
        Args:
            server_name: Name of the server
            process: Process instance running the MCP server
        """
        try:
            logger.info(f"Starting tool discovery for {server_name}")
            
            # Send MCP initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "mcp-compose",
                        "version": "0.1.0"
                    }
                }
            }
            
            logger.debug(f"Sending initialize request to {server_name}")
            response = await self._send_request(process, init_request)
            
            if not response:
                logger.error(f"No response to initialize from {server_name}")
                return
                
            if "error" in response:
                logger.error(f"Failed to initialize {server_name}: {response.get('error')}")
                return
            
            logger.debug(f"Initialize response from {server_name}: {response}")
            
            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            await self._send_notification(process, initialized_notification)
            
            # Request tools list
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            logger.debug(f"Requesting tools list from {server_name}")
            tools_response = await self._send_request(process, tools_request)
            
            if not tools_response:
                logger.error(f"No response to tools/list from {server_name}")
                return
            
            logger.debug(f"Tools list response from {server_name}: {tools_response}")
            
            if tools_response and "result" in tools_response:
                tools = tools_response["result"].get("tools", [])
                logger.info(f"Discovered {len(tools)} tools from {server_name}: {[t.get('name') for t in tools]}")
                
                # Register each tool as a proxy
                for tool in tools:
                    tool_name = tool.get("name")
                    if tool_name:
                        # Create proxy function for this tool
                        self._register_tool_proxy(server_name, tool_name, tool, process)
                
                logger.info(f"Registered {len(tools)} proxy tools from {server_name}")
                
        except Exception as e:
            logger.error(f"Error discovering tools from {server_name}: {e}", exc_info=True)
    
    def _register_tool_proxy(self, server_name: str, tool_name: str, tool_def: Dict[str, Any], process: Process) -> None:
        """
        Register a proxy function for a tool.
        
        Args:
            server_name: Name of the server providing the tool
            tool_name: Name of the tool
            tool_def: Tool definition from MCP protocol
            process: Process instance to communicate with
        """
        # Apply name prefix based on conflict resolution
        from .composer import ConflictResolution
        
        if self.composer.conflict_resolution == ConflictResolution.PREFIX:
            # Use underscore instead of colon for tool names (required by some LLM APIs)
            prefixed_name = f"{server_name}_{tool_name}"
        else:
            prefixed_name = tool_name
        
        # Create a closure to capture the current values
        def make_proxy_tool(srv_name: str, tl_name: str, proc: Process, schema: Dict[str, Any]):
            """Create proxy function with proper signature based on schema."""
            
            # Get parameter info from schema
            properties = schema.get("properties", {}) if schema else {}
            required_params = schema.get("required", []) if schema else []
            
            # Build parameter list with proper types
            params = []
            annotations = {}
            
            for param_name, param_spec in properties.items():
                # Map JSON Schema types to Python types
                param_type = param_spec.get("type", "string")
                if param_type == "number":
                    python_type = float
                elif param_type == "integer":
                    python_type = int
                elif param_type == "boolean":
                    python_type = bool
                elif param_type == "array":
                    python_type = list
                elif param_type == "object":
                    python_type = dict
                else:
                    python_type = str
                
                annotations[param_name] = python_type
                
                # Create parameter with proper default
                if param_name in required_params:
                    param = inspect.Parameter(param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=python_type)
                else:
                    param = inspect.Parameter(param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=python_type)
                params.append(param)
            
            # Add return annotation
            annotations["return"] = str
            
            # Create the actual async function that will be called
            async def _proxy_impl(**kwargs) -> str:
                """Proxy function that forwards tool calls to child process."""
                try:
                    logger.info(f"Tool {tl_name} called with arguments: {kwargs}")
                    
                    request = {
                        "jsonrpc": "2.0",
                        "id": "tool-call",
                        "method": "tools/call",
                        "params": {
                            "name": tl_name,
                            "arguments": kwargs
                        }
                    }
                    
                    logger.debug(f"Sending request to {srv_name}: {json.dumps(request)}")
                    response = await self._send_request(proc, request)
                    logger.debug(f"Response from {srv_name}: {response}")
                    
                    if response and "result" in response:
                        result = response["result"]
                        # Handle MCP protocol response format
                        if isinstance(result, dict) and "content" in result:
                            content = result["content"]
                            if isinstance(content, list) and len(content) > 0:
                                # Return the text from the first content item
                                text_result = content[0].get("text", str(content))
                                logger.info(f"Tool {tl_name} returned: {text_result}")
                                return text_result
                            return str(content)
                        return str(result)
                    elif response and "error" in response:
                        error = response["error"]
                        error_msg = f"Tool execution error: {error.get('message', 'Unknown error')}"
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)
                    else:
                        raise RuntimeError("No response from tool execution")
                        
                except Exception as e:
                    logger.error(f"Error calling tool {tl_name} on {srv_name}: {e}", exc_info=True)
                    raise
            
            # Create wrapper function with proper signature
            # This function will have the correct parameters in its signature
            async def proxy_tool(*args, **kwargs) -> str:
                # Convert positional args to kwargs based on parameter order
                for i, param in enumerate(params):
                    if i < len(args):
                        kwargs[param.name] = args[i]
                return await _proxy_impl(**kwargs)
            
            # Set the proper signature on the wrapper
            proxy_tool.__signature__ = inspect.Signature(parameters=params, return_annotation=str)
            proxy_tool.__annotations__ = annotations
            
            return proxy_tool
        
        # Create the proxy function with closure, passing the inputSchema
        input_schema = tool_def.get("inputSchema", {})
        proxy_func = make_proxy_tool(server_name, tool_name, process, input_schema)
        
        # Set function metadata (for Python introspection)
        # Replace any remaining special characters with underscores
        safe_name = prefixed_name.replace("-", "_").replace(":", "_")
        proxy_func.__name__ = safe_name
        proxy_func.__doc__ = tool_def.get("description", "")
        
        # Register with FastMCP server
        # Use from_function to create proper Tool object, then override parameters
        try:
            # Create Tool from function (this generates fn_metadata)
            tool_obj = Tool.from_function(
                proxy_func,
                name=prefixed_name,
                description=tool_def.get("description", "")
            )
            
            # Override the parameters with the actual MCP inputSchema
            # This ensures the LLM sees the correct parameter types from the child server
            if input_schema:
                tool_obj.parameters = input_schema
                logger.debug(f"Tool {prefixed_name} parameters after override: {json.dumps(input_schema, indent=2)}")
                
                # CRITICAL FIX: Also update fn_metadata.arg_model to match the schema
                # This prevents Pydantic from converting arrays to strings during validation
                from pydantic import create_model, BaseModel
                from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase
                
                # Build Pydantic model fields from inputSchema
                model_fields = {}
                properties = input_schema.get("properties", {})
                required = input_schema.get("required", [])
                
                for field_name, field_spec in properties.items():
                    field_type = field_spec.get("type", "string")
                    
                    # Map JSON Schema types to Python/Pydantic types
                    if field_type == "array":
                        # Get item type from schema
                        items = field_spec.get("items", {})
                        item_type = items.get("type", "string")
                        if item_type == "string":
                            python_type = list[str]
                        elif item_type == "number":
                            python_type = list[float]
                        elif item_type == "integer":
                            python_type = list[int]
                        elif item_type == "boolean":
                            python_type = list[bool]
                        elif item_type == "object":
                            python_type = list[dict]
                        else:
                            python_type = list[Any]
                    elif field_type == "object":
                        python_type = dict[str, Any]
                    elif field_type == "number":
                        python_type = float
                    elif field_type == "integer":
                        python_type = int
                    elif field_type == "boolean":
                        python_type = bool
                    else:
                        python_type = str
                    
                    # Add default if not required
                    if field_name in required:
                        model_fields[field_name] = (python_type, ...)
                    else:
                        model_fields[field_name] = (python_type, None)
                
                # Create new arg_model with correct types (using ArgModelBase as base)
                new_arg_model = create_model(
                    f"{safe_name}Arguments",
                    __base__=ArgModelBase,
                    **model_fields
                )
                
                # Replace the arg_model in fn_metadata
                tool_obj.fn_metadata.arg_model = new_arg_model
                logger.debug(f"Tool {prefixed_name} arg_model updated with correct types")
            
            self.composer.composed_server._tool_manager._tools[tool_obj.name] = tool_obj
            logger.info(f"Registered proxy tool: {tool_obj.name} with schema: {list(input_schema.get('properties', {}).keys())}")
        except Exception as e:
            logger.error(f"Failed to register tool {prefixed_name}: {e}", exc_info=True)
            raise
        
        # Also track in composer's composed_tools dict
        self.composer.composed_tools[prefixed_name] = {
            "description": tool_def.get("description", ""),
            "inputSchema": tool_def.get("inputSchema", {})
        }
        self.composer.source_mapping[prefixed_name] = server_name
        
    async def _send_request(self, process: Process, request: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Send a JSON-RPC request to a child process and wait for response.
        
        Args:
            process: Process instance to send to
            request: JSON-RPC request dict
            timeout: Timeout in seconds
            
        Returns:
            Response dict or None if timeout/error
        """
        if not process._stdin_writer or not process._stdout_reader:
            logger.error(f"Process {process.name} has no stdin/stdout")
            return None
        
        try:
            # Send request
            request_json = json.dumps(request) + "\n"
            process._stdin_writer.write(request_json.encode())
            await process._stdin_writer.drain()
            
            # Read response with timeout
            try:
                response_line = await asyncio.wait_for(
                    process._stdout_reader.readline(),
                    timeout=timeout
                )
                
                if response_line:
                    response = json.loads(response_line.decode().strip())
                    return response
                else:
                    logger.warning(f"Empty response from {process.name}")
                    return None
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for response from {process.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending request to {process.name}: {e}")
            return None
    
    async def _send_notification(self, process: Process, notification: Dict[str, Any]) -> None:
        """
        Send a JSON-RPC notification to a child process (no response expected).
        
        Args:
            process: Process instance to send to
            notification: JSON-RPC notification dict
        """
        if not process._stdin_writer:
            logger.error(f"Process {process.name} has no stdin")
            return
        
        try:
            notification_json = json.dumps(notification) + "\n"
            process._stdin_writer.write(notification_json.encode())
            await process._stdin_writer.drain()
        except Exception as e:
            logger.error(f"Error sending notification to {process.name}: {e}")


def fix_tool_argument_model(tool_obj: Tool, input_schema: Dict[str, Any]) -> None:
    """
    Fix the tool's argument model to preserve array/object types from JSON Schema.
    
    When Tool.from_function() creates a tool, it generates a Pydantic model from
    the function signature. However, when we override tool_obj.parameters with
    the downstream server's inputSchema, the fn_metadata.arg_model still has
    the original types. This causes arrays to be converted to strings.
    
    This function creates a new Pydantic model from the inputSchema and replaces
    the tool's arg_model to ensure proper type coercion.
    
    Args:
        tool_obj: Tool instance to fix
        input_schema: JSON Schema from the downstream server
    """
    try:
        from pydantic import create_model
        from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase
        from typing import Any as AnyType, List, Dict as DictType, Optional, Union
        
        # Build field definitions for Pydantic model
        fields = {}
        properties = input_schema.get('properties', {})
        required_fields = input_schema.get('required', [])
        
        for field_name, field_schema in properties.items():
            # Handle anyOf (union types like array|null)
            if 'anyOf' in field_schema:
                any_of = field_schema['anyOf']
                # Find non-null type
                main_type = None
                for option in any_of:
                    if option.get('type') != 'null':
                        main_type = option
                        break
                
                if main_type:
                    field_type = main_type.get('type', 'string')
                    
                    # Handle array in anyOf
                    if field_type == 'array':
                        items_schema = main_type.get('items', {})
                        items_type = items_schema.get('type', 'string')
                        
                        if items_type == 'string':
                            python_type = Optional[List[str]]
                        elif items_type == 'number':
                            python_type = Optional[List[float]]
                        elif items_type == 'integer':
                            python_type = Optional[List[int]]
                        elif items_type == 'boolean':
                            python_type = Optional[List[bool]]
                        elif items_type == 'object':
                            python_type = Optional[List[dict]]
                        else:
                            python_type = Optional[List[AnyType]]
                    elif field_type == 'object':
                        python_type = Optional[DictType[str, AnyType]]
                    elif field_type == 'number':
                        python_type = Optional[float]
                    elif field_type == 'integer':
                        python_type = Optional[int]
                    elif field_type == 'boolean':
                        python_type = Optional[bool]
                    else:
                        python_type = Optional[str]
                else:
                    python_type = Optional[str]
            else:
                # Regular type handling
                field_type = field_schema.get('type', 'string')
                
                # Handle array types
                if field_type == 'array':
                    items_schema = field_schema.get('items', {})
                    items_type = items_schema.get('type', 'string')
                    
                    # Map item types using typing.List for compatibility
                    if items_type == 'string':
                        python_type = List[str]
                    elif items_type == 'number':
                        python_type = List[float]
                    elif items_type == 'integer':
                        python_type = List[int]
                    elif items_type == 'boolean':
                        python_type = List[bool]
                    elif items_type == 'object':
                        python_type = List[dict]
                    else:
                        python_type = List[AnyType]
                # Handle object types
                elif field_type == 'object':
                    python_type = DictType[str, AnyType]
                elif field_type == 'number':
                    python_type = float
                elif field_type == 'integer':
                    python_type = int
                elif field_type == 'boolean':
                    python_type = bool
                else:
                    python_type = str
            
            # Set default value based on whether field is required
            if field_name in required_fields:
                fields[field_name] = (python_type, ...)  # Required field
            else:
                # Optional field with default from schema or None
                default = field_schema.get('default', None)
                fields[field_name] = (python_type, default)
        
        # Create new Pydantic model that extends ArgModelBase
        new_model = create_model(
            f"{tool_obj.name}_Args",
            __base__=ArgModelBase,
            **fields
        )
        
        # Replace the arg_model in fn_metadata
        if hasattr(tool_obj, 'fn_metadata') and tool_obj.fn_metadata:
            tool_obj.fn_metadata.arg_model = new_model
            logger.info(f"✓ Fixed argument model for tool {tool_obj.name}")
            logger.debug(f"  Field definitions: {fields}")
            logger.debug(f"  New model: {new_model}")
            logger.debug(f"  Model schema: {new_model.model_json_schema()}")
    
    except Exception as e:
        logger.error(f"Failed to fix argument model for tool {tool_obj.name}: {e}", exc_info=True)
