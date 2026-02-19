
You said:
import os
import asyncio
import certifi
import requests
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Fix SSL issues in corporate environments
os.environ["SSL_CERT_FILE"] = certifi.where()

def get_azure_access_token():
    """
    Generates Azure AD token using Service Principal.
    Will work once CLIENT_ID + SECRET are available.
    """

    tenant = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")

    if "waiting" in (tenant, client_id, client_secret):
        raise ValueError("Azure credentials not configured yet.")

    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

    payload = {
        "client_id": os.getenv("AZURE_CLIENT_ID"),
        "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
        "scope": "https://analysis.windows.net/powerbi/api/.default",
        "grant_type": "client_credentials",
    }

    response = requests.post(url, data=payload)
    response.raise_for_status()

    return response.json()["access_token"]

async def main():
    print("Generating Azure access token...")
    token = get_azure_access_token()

    servers = {
        "powerbi-remote": {
            "transport": "http",
            "url": "https://api.fabric.microsoft.com/v1/mcp/powerbi",
            "headers": {
                "Authorization": f"Bearer {token}"
            }
        }
    }

    print("Connecting to MCP server...")
    client = MultiServerMCPClient(servers)
    tools = await client.get_tools()

    print(f"Discovered {len(tools)} MCP tools")

    model = init_chat_model(
        os.getenv("MODEL"),
        model_provider="openai",
        api_key=os.getenv("GITHUB_TOKEN"),
        base_url=os.getenv("ENDPOINT"),
    )

    # system prompt for the agent (create_agent expects a simple system prompt)
    system_prompt = "You are a FinOps analyst querying Power BI semantic models."

    # create a compiled agent graph using the newer LangChain API
    agent_graph = create_agent(model, tools, system_prompt=system_prompt, debug=True)

    query = "Fetch the semantic model schema and describe all tables and measures."

    # create_agent expects inputs in the messages format
    inputs = {"messages": [{"role": "user", "content": query}]}

    # invoke the agent graph asynchronously
    result = await agent_graph.ainvoke(inputs)

    # result is typically a dict with output channels; print the full result
    print(result)

if __name__ == "__main__":
    asyncio.run(main())       
