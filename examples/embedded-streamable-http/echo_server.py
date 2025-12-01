#!/usr/bin/env python3
"""
Echo MCP Server - Embedded Module

Simple MCP server providing string manipulation operations.
This module is designed to be imported by mcp-compose as an embedded server.
"""

from mcp.server.fastmcp import FastMCP

# Create MCP server - this 'mcp' object will be imported by the composer
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


# Note: When used as an embedded server, the composer imports the 'mcp' object directly.
# The __main__ block below is only for standalone testing.
if __name__ == "__main__":
    # Run as standalone STDIO server for testing
    mcp.run(transport="stdio")
