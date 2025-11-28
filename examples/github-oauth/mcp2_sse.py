#!/usr/bin/env python3
"""
MCP Server 2 - Echo & String Tools (SSE Transport)

Simple MCP server providing string manipulation operations via SSE.
Authentication is handled at the MCP Compose level.
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


if __name__ == "__main__":
    # Run as SSE server on port 8081
    import uvicorn
    
    # Get the SSE app from FastMCP
    app = mcp.sse_app()
    
    # Run with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
