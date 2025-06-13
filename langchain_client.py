import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from fastmcp.client.auth import BearerAuth
from langchain_groq import ChatGroq
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent, chat_agent_executor
from langgraph.checkpoint.memory import InMemorySaver

import json 
from dotenv import load_dotenv

load_dotenv()

model = ChatGroq(model="llama-3.3-70b-versatile")

async def main():
    #get jwt from the file
    with open("token.json", "r") as f:
        token_data = json.load(f)

    token = token_data["access_token"]

    async with sse_client("http://localhost:8000/sse", auth = BearerAuth(token=token)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)

            agent = create_react_agent(model=model, tools=tools)

            while True:
                print("\nInside agent loop")
                query = input("\nEnter Query: ")

                if query.lower() == "quit":
                    break
                
                #LANGCHAIN / GRAPH NEEDS TO BE INVOKED INSIDE A DICT THAT CONTAINS {MESSAGES:[]} OTHERWISE ERROR COME AND MIND GO
                response = await agent.ainvoke({
                    "messages": [
                            {
                                "role": "user", 
                                "content":query
                            }
                        ]
                    }
                )

                for message in response["messages"]:
                    message.pretty_print()

if __name__ == "__main__":
    asyncio.run(main())
