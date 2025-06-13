from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.mcp import MCPTools

from mcp import ClientSession
from mcp.client.sse import sse_client
from fastmcp.client.auth import BearerAuth

from agno.tools.mcp import MCPTools
from agno.tools.mcp import SSEClientParams
import json 
import asyncio

from dotenv import load_dotenv

load_dotenv()

async def main():
    with open("token.json", "r") as f:
        token_data = json.load(f)

    token = token_data["access_token"]
    
    async with MCPTools(transport="sse", url="http://localhost:8000/sse", server_params=SSEClientParams( url="http://localhost:8000/sse", auth=BearerAuth(token=token))) as mcp_tools:
            
            print(mcp_tools)
            agent = Agent(
            model=Groq(id="llama-3.3-70b-versatile"),
            tools=[mcp_tools],
            markdown=True
            )
        
            while True:
                print("\n Inside while")
                query = input("\nQuery: ")

                if query.lower() == "quit":
                    break
                
                await agent.aprint_response(message=query, markdown=True)


if __name__=="__main__":
    asyncio.run(main())


"""

async with sse_client("http://localhost:8000/sse", auth=BearerAuth(token=token)) as (read,write):
        async with ClientSession(read, write) as session:
            
            await session.initialize()

            tools = await session.list_tools()

"""