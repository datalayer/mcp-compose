#!/usr/bin/env python3
"""
MCP Server 1 - Calculator Tools

Simple MCP server providing calculator operations.
"""

from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("calculator-server")


@mcp.tool()
def add(a: float, b: list[float]) -> float:
    """Add a number to a list of numbers.
    
    Args:
        a: First number
        b: List of numbers to add to a
        
    Returns:
        Sum of a and all numbers in b
    """
    return a + sum(b)


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


if __name__ == "__main__":
    # Run as STDIO server
    mcp.run(transport="stdio")
