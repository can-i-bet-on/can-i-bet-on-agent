from langchain_openai import ChatOpenAI


import os


big_llm = ChatOpenAI(
    # base_url="https://openrouter.ai/api/v1",
    model="gpt-4o",
    # model="perplexity/sonar-medium-online",
    temperature=0.2,
    api_key=os.getenv("OPENAI_API_KEY"),
)
smol_llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
    api_key=os.getenv("OPENAI_API_KEY"),
)
perplexity_llm = ChatOpenAI(
    base_url="https://api.perplexity.ai",
    model="sonar-pro",
    temperature=0,
    api_key=os.getenv("PPLX_API_KEY"),
)
