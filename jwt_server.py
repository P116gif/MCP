""" from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import RSAKeyPair, BearerAuthProvider
import random
import sys
# Generate RSA key pair and create token
key_pair = RSAKeyPair.generate()
access_token = key_pair.create_token(audience="my-server")

# Create bearer auth provider
auth = BearerAuthProvider(
    public_key=key_pair.public_key,
    audience="my-server",
)

# Create FastMCP server with auth
mcp = FastMCP(name="My Authenticated Server", auth=auth)

@mcp.tool()
def roll_dice(n_dice: int) -> list[int]:
    Roll `n_dice` 6-sided dice and return the results
    return [random.randint(1, 6) for _ in range(n_dice)]

@mcp.tool()
def greet(name: str) -> str:
    Greet someone by name
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(f"\n🔑 Access token:\n{access_token}\n")
    sys.stdout.flush()
    mcp.run(transport="sse", port=8000) """


from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
import random
import json 

key_pair = RSAKeyPair.generate()
access_token = key_pair.create_token(audience="dice-client")

#save token to file
with open("token.json", "w") as f:
    json.dump({"access_token": access_token}, f)

auth = BearerAuthProvider(
    public_key=key_pair.public_key,
    audience="dice-client"
)

mcp = FastMCP(name="Dice Roller", auth=auth)

@mcp.tool()
def roll_dice(n_dice: int) -> list[int]:
    """Roll n dices each with 6 sides and return the results"""
    return [random.randint(1,6) for _ in range(n_dice)]

if __name__ == "__main__":
    print("🔑 Token saved to token.json")
    mcp.run(transport="sse", port=8000)

    