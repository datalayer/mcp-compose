#!/usr/bin/env python3
"""
Calculator MCP Server - Embedded Module

Simple MCP server providing calculator operations.
This module is designed to be imported by mcp-compose as an embedded server.
"""

from mcp.server.fastmcp import FastMCP

# Create MCP server - this 'mcp' object will be imported by the composer
mcp = FastMCP("calculator-server")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Difference of a and b
    """
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Product of a and b
    """
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b.
    
    Args:
        a: Numerator
        b: Denominator
        
    Returns:
        Quotient of a divided by b
        
    Raises:
        ValueError: If b is zero
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


# Note: When used as an embedded server, the composer imports the 'mcp' object directly.
# The __main__ block below is only for standalone testing.
if __name__ == "__main__":
    # Run as standalone STDIO server for testing
    mcp.run(transport="stdio")
