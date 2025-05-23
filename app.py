from fastapi import FastAPI, Request
from pydantic import BaseModel
import asyncio
import sys, os, json
from client import MCPClient

asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI()
client = MCPClient()

class QueryRequest(BaseModel):
    query: str

@app.on_event("startup")
async def startup_event():
    global client
    mcp_json = "mcp.json"

    if not os.path.exists(mcp_json):
        print(f"Error: {mcp_json} file not found.")
        sys.exit(1)

    with open(mcp_json, 'r') as f:
        mcp_config = json.load(f)

    servers = mcp_config.get("mcpServers", {})

    if not servers:
        print("Error: No MCP servers found in the configuration.")
        sys.exit(1)

    for server_name, server_info in servers.items():
        command = server_info.get("command")
        args = server_info.get("args")

        if not command or not args:
            print(f"Command: {command} or Args: {args} not found for server {server_name}.")
            continue

        await client.connect_to_server(server_name, command, args)
    app.state.client = client

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, 'client'):
        await client.cleanup()
        print("\nMCP Client Exiting!")

@app.post("/query")
async def query_endpoint(query: QueryRequest):
    client = app.state.client
    response = await client.process_query(query.query)
    return {"response": response}

