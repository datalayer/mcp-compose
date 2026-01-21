#!/usr/bin/env python3
# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
MCP Server 2 - Echo & String Tools

Simple MCP server providing string manipulation operations.
"""

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
0

@mcp.tool()
def concatenate(strings: list[str], separator: str = " ") -> str:
    """Concatenate an array of strings with a separator.
    
    Args:
        strings: Array of strings to concatenate
        separator: Separator to use between strings (default: space)
        
    Returns:
        Concatenated string
    """
    return separator.join(strings)


if __name__ == "__main__":
    # Run as Streamable HTTP server
    import uvicorn
    
    # Create the FastAPI app with streamable HTTP transport
    app = mcp.streamable_http_app()
    
    # Run with uvicorn on port 8082
    uvicorn.run(app, host="0.0.0.0", port=8082)
