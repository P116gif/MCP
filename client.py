import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from groq import AsyncGroq
from dotenv import load_dotenv
import os
import sys
import json

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.sessions: list[tuple[str, ClientSession]] = []
        self.exit_stack = AsyncExitStack()
        self.groq = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

    async def connect_to_server(self, server_name: str, command:str, args: list[str]):
        """Connect to an MCP server using command and args"""

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()
        self.sessions.append((server_name, session))
        

    async def process_query(self, query: str) -> str:
        """Process a query using Groq and available tools"""
        # Get available tools from the server
        print(f"Processing query: {query}")
        available_tools = []
        tool_session_map = {}

        for server_name, session in self.sessions:
            response = await session.list_tools()
            for tool in response.tools:
                tool_name = f"{server_name}::{tool.name}"
                available_tools.append({
                    "type": "function",
                    "function":{
                        "name":tool_name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })
                tool_session_map[tool_name] = session
        
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        print(messages)

        final_text = []
        tool_results = []

        while True:
            # Call Groq API with tools
            groq_response = await self.groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=1500,
                messages=messages, #type:ignore
                tools=available_tools,
                tool_choice="auto"
            )

            message = groq_response.choices[0].message

            # If Groq returns tool calls, execute them
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = tool_call.function.arguments

                    # tool_args is a JSON string, parse it
                    try:
                        tool_args_dict = json.loads(tool_args)
                    except Exception:
                        tool_args_dict = {}

                    session = tool_session_map.get(tool_name)

                    if session is None:
                        result = f"Tool {tool_name} not found in session {session}"
                    else:
                        #Remove server name from tool name to call the tool
                        _, actual_tool_name = tool_name.split("::",1)
                        result = await session.call_tool(actual_tool_name, tool_args_dict)
                        tool_results.append({"call": tool_name, "result": result})
                        final_text.append(f"[Calling tool {tool_name} with args {tool_args_dict}]")

                    # Add tool call and result to messages for next round
                    messages.append({
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": tool_args
                                }
                            }
                        ] #type: ignore
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result.content) if hasattr(result, "content") else str(result) #type:ignore
                    })
                # Continue the loop to let Groq process the tool results
                continue

            # If no tool calls, return the response
            if hasattr(message, "content") and message.content:
                final_text.append(message.content)
            break

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                print(f"Processing query {query}")
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py mcp.json")
        sys.exit(1)
        
    mcp_json = sys.argv[1]
    if not os.path.exists(mcp_json):
        print(f"File {mcp_json} does not exist.")
        sys.exit(1)
    
    with open(mcp_json,'r') as f:
        mcp_config = json.load(f)

    servers = mcp_config.get("mcpServers",{})
    if not servers:
        print("No MCP servers found in the configuration.")
        sys.exit(1)
    
    client = MCPClient()
    try:
        for server_name, server_info in servers.items():
            command = server_info.get("command")
            args = server_info.get("args", [])
            if not command or not args:
                print(f"Command not found for server {server_name}:{server_info}.")
                continue
            await client.connect_to_server(server_name, command, args)
        await client.chat_loop()
    finally:
        await client.cleanup()
        print("\nMCP Client Exiting!")


if __name__ == "__main__":
    asyncio.run(main())