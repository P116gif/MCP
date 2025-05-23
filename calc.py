from mcp.server.fastmcp import FastMCP
import math

mcp = FastMCP("calculator")

#define tools

@mcp.tool()
def add(a: int, b: int) -> int:
    """
    Add two numbers.
    """
    return a + b

@mcp.tool()
def subtract(a: int, b: int) -> int:
    """
    Subtract two numbers.
    """
    return a - b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """
    Multiply two numbers.
    """
    return a * b

@mcp.tool()
def divide(a: int, b: int) -> float:
    """
    Divide two numbers.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b

@mcp.tool()
def power(base: int, exponent: int) -> float:
    """
    Raise a number to the power of another number.
    """
    return math.pow(base, exponent)

@mcp.tool()
def square_root(a: int) -> float:
    """
    Calculate the square root of a number.
    """
    if a < 0:
        raise ValueError("Cannot calculate the square root of a negative number.")
    return math.sqrt(a)

if __name__ == "__main__":
    mcp.run(transport="stdio")