
import os
import autogen
from typing import Annotated
from tavily import TavilyClient

# Construct the config list directly from environment variables
config_list = [
    {
        "model": os.environ.get("GROQ_DEFAULT_MODEL_NAME", "gpt-4o-mini"),
        "api_key": os.environ.get("GROQ_API_KEY"),
        "base_url": "https://api.groq.com/openai/v1",
    }
]

tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

# Define the function for web search
def web_search(query: str) -> str:
    """
    Perform a web search using Tavily to find relevant information.
    """
    try:
        result = tavily.search(query=query, max_results=5)
        return "\n".join([res["content"] for res in result["results"]])
    except Exception as e:
        return f"Error performing web search: {e}"

class ResearchAgent:
    def __init__(self):
        self.researcher = autogen.AssistantAgent(
            name="Researcher",
            llm_config={"config_list": config_list},
            system_message="""
            As a Research Agent, your role is to gather, analyze, and synthesize information from the web to support proposal creation.
            You are equipped with a web search tool that you must use to find relevant data.
            
            When you receive a research request, you should:
            1.  Understand the core requirements of the request (e.g., client name, industry, specific topics).
            2.  Formulate targeted search queries.
            3.  Use the `web_search` tool to gather information.
            4.  Synthesize the search results into a concise, well-structured summary.
            5.  Provide the summary as your final output.
            
            You must call the `web_search` tool to perform your research. Do not provide information without backing it up with search results.
            """,
        )
        
        # Register the tool with the agent
        self.researcher.register_function(
            function_map={
                "web_search": web_search
            }
        )

    def get_agent(self):
        return self.researcher

research_agent = ResearchAgent().get_agent()
