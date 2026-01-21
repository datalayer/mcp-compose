#!/usr/bin/env python3
# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
MCP Server 1 - Calculator Tools

Simple MCP server providing calculator operations.
Authentication is handled at the MCP Compose level.
"""

from mcp.server.fastmcp import FastMCP

# Create MCP server
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


if __name__ == "__main__":
    # Run as STDIO server
    mcp.run(transport="stdio")
