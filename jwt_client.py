from fastmcp import Client
import asyncio
from fastmcp.client.auth import BearerAuth
import json 

from contextlib import AsyncExitStack
from groq import AsyncGroq
from dotenv import load_dotenv
import os
import sys

from mcp import ClientSession
from mcp.client.sse import sse_client

load_dotenv()

class MCPClient:
    def __init__(self) -> None:
        self.session: ClientSession
        self.exit_stack = AsyncExitStack()
        self.groq = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

    async def connect_to_server(self):
        """Connect to dice roll server"""
        with open("token.json", "r") as f:
            token_data = json.load(f)
        token = token_data["access_token"]

        sse_transport = await self.exit_stack.enter_async_context(sse_client(url="http://localhost:8000/sse", auth=BearerAuth(token=token)))
        sse, write = sse_transport
        session = await self.exit_stack.enter_async_context(ClientSession(sse, write))
        await session.initialize()
        self.session = session 

    async def process_query(self, query: str) -> str:
        """Process a query using Groq and available tools"""
        print(f"Processeing query {query}")

        available_tools = []

        response = await self.session.list_tools()
        for tool in response.tools:
            available_tools.append({
                "type":"function",
                "function":{
                    "name":tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema 
                }
            })

        messages = [
            {
                "role" : "user",
                "content" : query
            }
        ]

        print(messages)

        final_text = []
        tool_results = []

        while True:
            groq_response = await self.groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_completion_tokens=1500,
                messages=messages,
                tools=available_tools,
                tool_choice="auto"
            ) #type: ignore

            message = groq_response.choices[0].message

            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = tool_call.function.arguments

                    try:
                        tool_args_dict = json.loads(tool_args)
                    except Exception:
                        tool_args_dict = {}

                    result = await self.session.call_tool(tool_name, tool_args_dict)
                    tool_results.append({"call": tool_name, "result": result})
                    final_text.append(f"[Calling Tool {tool_name} with args {tool_args_dict}]")

                    messages.append({
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name" : tool_name,
                                    "arguments": tool_args
                                }
                            }
                        ] #type: ignore
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result.content) if hasattr(result,"content") else str(result) 
                    })

                continue

            if hasattr(message, "content") and message.content:
                final_text.append(message.content)
            break

        return "\n".join(final_text)
    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or quit to exit")

        while True:
            try:
                query = input("\nQuery: ").strip()
                print(f"Processing query {query}")
                if query.lower() == "quit":
                    break
                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """
        Clean, clean, clean the boat, I'm dying on the street, 
        Happily, merrily, crudely~
        Dying on the street    
        """ 
        await self.exit_stack.aclose()

async def main():
    client = MCPClient()
    try:
        await client.connect_to_server()
        await client.chat_loop()
    finally:
        await client.cleanup()
        print("\nMCP Client Exiting")

if __name__ == "__main__":
    asyncio.run(main())
