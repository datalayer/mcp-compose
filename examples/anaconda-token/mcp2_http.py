#!/usr/bin/env python3
# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
MCP Server 2 - Echo & String Tools (HTTP Streaming Transport)

Simple MCP server providing string manipulation operations via HTTP streaming.
Supports multiple streaming protocols: JSON Lines, chunked, and long-polling.
Authentication is handled at the MCP Compose level.
"""

import json
import asyncio
from typing import AsyncIterator
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("echo-server")


@mcp.tool()
def ping() -> str:
    """Simple ping that returns 'pong'.
    
    Returns:
        The string 'pong'
    """
    return "pong"


@mcp.tool()
def echo(message: str) -> str:
    """Echo back the provided message.
    
    Args:
        message: Message to echo back
        
    Returns:
        The same message
    """
    return message


@mcp.tool()
def reverse(text: str) -> str:
    """Reverse a string.
    
    Args:
        text: Text to reverse
        
    Returns:
        Reversed text
    """
    return text[::-1]


@mcp.tool()
def uppercase(text: str) -> str:
    """Convert text to uppercase.
    
    Args:
        text: Text to convert
        
    Returns:
        Uppercased text
    """
    return text.upper()


@mcp.tool()
def lowercase(text: str) -> str:
    """Convert text to lowercase.
    
    Args:
        text: Text to convert
        
    Returns:
        Lowercased text
    """
    return text.lower()


@mcp.tool()
def count_words(text: str) -> int:
    """Count the number of words in text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Number of words
    """
    return len(text.split())


# Create FastAPI app for HTTP streaming
app = FastAPI(title="MCP Echo Server - HTTP Streaming")

# Message queues for MCP communication
# Each client gets their own queue for responses
client_queues: dict[str, asyncio.Queue] = {}


async def json_lines_stream(client_id: str) -> AsyncIterator[str]:
    """
    Stream MCP messages as JSON Lines (newline-delimited JSON).
    Each message is a complete JSON object followed by a newline.
    
    Args:
        client_id: Unique identifier for this client connection
    """
    # Create a client-specific queue
    client_queue = asyncio.Queue()
    client_queues[client_id] = client_queue
    
    try:
        while True:
            try:
                # Wait for a message with timeout
                message = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                # Send as JSON line
                yield json.dumps(message) + "\n"
            except asyncio.TimeoutError:
                # Send keepalive
                yield json.dumps({"type": "keepalive"}) + "\n"
            except Exception as e:
                print(f"Error in stream for client {client_id}: {e}")
                break
    finally:
        # Clean up client queue
        if client_id in client_queues:
            del client_queues[client_id]


@app.get("/stream")
async def stream_messages(request: Request):
    """
    HTTP streaming endpoint using JSON Lines protocol.
    Returns newline-delimited JSON (NDJSON).
    """
    # Generate a unique client ID
    import uuid
    client_id = str(uuid.uuid4())
    
    return StreamingResponse(
        json_lines_stream(client_id),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "X-Client-Id": client_id,
        }
    )


@app.post("/stream")
async def receive_message(request: Request):
    """
    Receive MCP messages via POST.
    Processes the message and queues the response.
    """
    try:
        message = await request.json()
        
        # Get client ID from header (if streaming) or use a default
        client_id = request.headers.get("X-Client-Id", "default")
        
        # Ensure client queue exists
        if client_id not in client_queues:
            client_queues[client_id] = asyncio.Queue()
        
        client_queue = client_queues[client_id]
        
        # Handle MCP protocol messages
        if message.get("method") == "initialize":
            # Send initialize response
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "echo-server",
                        "version": "1.0.0"
                    }
                }
            }
            await client_queue.put(response)
            
        elif message.get("method") == "tools/list":
            # List available tools
            tools = []
            for tool_name, tool in mcp._tool_manager._tools.items():
                tool_info = {
                    "name": tool_name,
                    "description": tool.description or "",
                    "inputSchema": tool.parameters or {
                        "type": "object",
                        "properties": {}
                    }
                }
                tools.append(tool_info)
            
            response = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "tools": tools
                }
            }
            await client_queue.put(response)
            
        elif message.get("method") == "tools/call":
            # Call a tool
            params = message.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            try:
                # Get the tool function
                tool = mcp._tool_manager._tools.get(tool_name)
                if not tool:
                    raise ValueError(f"Tool not found: {tool_name}")
                
                # Call the tool
                result = tool.fn(**arguments)
                
                # Return result
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                            }
                        ]
                    }
                }
                await client_queue.put(response)
                
            except Exception as e:
                # Return error
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32000,
                        "message": str(e)
                    }
                }
                await client_queue.put(response)
        
        return {"status": "ok"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "server": "echo-server"}


@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "name": "MCP Echo Server",
        "version": "1.0.0",
        "transport": "HTTP Streaming (JSON Lines)",
        "endpoints": {
            "stream": "/stream (GET for streaming, POST for messages)",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("MCP Echo Server - HTTP Streaming Transport")
    print("=" * 60)
    print()
    print("Server starting on http://localhost:8082")
    print()
    print("Endpoints:")
    print("  • GET  /stream  - Stream MCP messages (JSON Lines)")
    print("  • POST /stream  - Send MCP messages")
    print("  • GET  /health  - Health check")
    print()
    print("Protocol: JSON Lines (newline-delimited JSON)")
    print()
    print("Available tools:")
    for tool_name in mcp._tool_manager._tools.keys():
        print(f"  • {tool_name}")
    print()
    print("=" * 60)
    
    # Run with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
