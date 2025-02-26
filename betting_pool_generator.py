from datetime import datetime
from pprint import pprint
from typing import Annotated
from pydantic import BaseModel
import json

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
import os
from db.betting_pool_db import BettingPoolDB
import requests
from langchain_community.tools.tavily_search import TavilySearchResults
import random

load_dotenv()


class BettingPoolGeneratorOutput(BaseModel):
    betting_pool_idea: str
    options: list[str]
    closure_summary: str
    closure_instructions: str
    category: str
    odds_format: str
    odds_type: str
    odds_value: str


class ResearchGraphOutput(MessagesState):
    prefer_fast_response: bool
    topic: str
    search_results: list[str]
    news_results: list[str]
    # image_results: list[dict]
    betting_pool_idea: BettingPoolGeneratorOutput


class BettingPoolGeneratorTopicOutput(BaseModel):
    topic: str


class NewsSearchQuery(BaseModel):
    search_query: str


class ImageSearchQuery(BaseModel):
    search_query: str


smol_llm = ChatOpenAI(
    # base_url="https://openrouter.ai/api/v1",
    model="gpt-4o",
    # model="perplexity/sonar-medium-online",
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY"),
)

big_llm =  ChatOpenAI(
    # base_url="https://openrouter.ai/api/v1",
    model="gpt-4o",
    # model="perplexity/sonar-medium-online",
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY"),
)

# llm = ChatAnthropic(
#     model="claude-3-5-haiku-20241022",
#     # model="claude-3-5-sonnet-20241022",
#     temperature=0,
# )


# TODO wire this up
def generate_betting_pool_idea_from_seed(state: ResearchGraphOutput):
    # Take a given message, website, tweet, etc and propose a betting bool idea based on the tweet.
    user1 = "@cosmic_ferris_wheel"
    user2 = "@KuphJr"
    user3 = "@lejohndary"
    user4 = "@can"  # TODO I couldn't figure out how to  get 4th team member's username in telegram, not sure if this is right
    bot = "@HalluciBetrBot"

    prompt = f"""
    The user has asked you to generate a betting pool with this message:
    <message>{state.get("message")}</message>
    
    Examples:
    {user1}: I'm supposed to fly into Denver from New York on the 21st, but there's going to be a big storm the night before my flight, so the airlines are already telling me to expect delays.
    {user2}: @HalluciBetrBot, create a betting pool on ^^^
    {bot}: Sure, I can do that. How does this sound: 
        Idea: "Will {user1}'s flight to Denver on the 21st be delayed due to weather?"
        Options: Yes, No
        Closure summary: We will check the weather on the 20th and see if any flights from NYC to Denver are delayed.
        Closure instructions: We will first check if {user1}'s communicated that their flight was delayed in this channel proactively. We will then check the weather on the 20th and see if any flights from NYC to Denver are delayed. If the user has said that their flight is delayed and we see that flights from NYC to Denver are generally delayed, we will return "Yes". Otherwise, we will return "No".

    {user2}: I'm going to the gym tomorrow, but I'm not sure if I'll be able to lift 200lbs.
    {user3}: @HalluciBetrBot, create a betting pool on ^^^
    {bot}: Sure, I can do that. How does this sound: 
        Idea: "Will {user1} be able to lift 200lbs tomorrow?"
        Options: Yes, No
        Closure summary: We will check {user1}'s gym log tomorrow and see if they can lift 200lbs.
        Closure instructions: We will scan {user1}'s public MyFitnessPal profile to see what weights they logged. If we do not find a log, we will instead check this channel in telegram. If we find nothing in telegram, we will DM {user1}'s associates, @{user2} and @{user3} to see if they know. If any of these sources confirm the 200lbs lift, we will return "Yes". Otherwise, we will return "No"
        
    
    Analyze the message and try to determine if the user is asking us to generate a betting pool for a specific topic or theme.
    1. First extract the idea. What are they going to bet on? Is there an item in the text that could have multiple outcomes (typically YES or NO)? 
    2. Then try to extract the possible outcomes from the idea. Initially, unless the user specifies options explicitly, you should try to extract a simple YES or NO outcome.
    3. Then try to figure out what conditions would determine a winner for the bet. Is there a date in which we'll know the outcome? Is there a specific event that will happen that will trigger this?
    4. Finally generate instructions fo a future agent to figure out which option won. Focus on things you can confirm digitally and try to avoid relying on a human to judge when possible.
    """


def extract_context_for_betting_pool_idea(state: ResearchGraphOutput):
    # TODO Write this. High level idea is to get info that can be passed into a tool call.
    # You have been given this context by the user, your goal is to extract URLs from the context to feed into a tool call.
    # You have been given this context by the user, your goal is to analyze the likely origin of the context so you can scrape it in a future tool call.(I want this to identify if the user is linking to a post on X or Telegram initially)
    #
    # Then taking that context, if there were URLs, we'd use crawl4ai to download the page and search for betting pool ideas
    # If there were X or Telegram posts, we'd go to the X or Telegram API to get the post content + surrounding messages
    return {}


def extract_topic(state: ResearchGraphOutput):
    """Extract the topic from the state"""
    prompt = f"""
    The user has asked you to generate a betting pool with this message:
    <message>{state.get("message")}</message>
    
    Analyze the message and try to determine if the user is asking us to generate a betting pool for a specific topic or theme.
    
    If they are, respond with the topic. If they are not, respond with an empty string.
    
    Important guidelines:
    - Be specific and include key details from the user's message
    - If the user mentions specific events (like "rain", "snow", "win", etc.), include those in the topic
    - If the user mentions specific locations or entities, include those
    - If the user mentions timeframes (like "today", "this week", etc.), include those
    - The topic should capture the essence of what the user wants to bet on
    
    For example:
    - If the message is "if it will rain in Denver today?", the topic should be "Rain in Denver today"
    - If the message is "Will the Broncos win their next game?", the topic should be "Broncos winning their next game"
    
    Your response should be the following JSON object and nothing else. Do not include any other text, any markdown, or any comments.
    {{
        "topic": "" // The specific topic for the betting pool if you can determine it, otherwise an empty string
    }}
    """

    structured_llm = smol_llm.with_structured_output(BettingPoolGeneratorTopicOutput)
    topic = structured_llm.invoke([prompt] + state["messages"])
    print("extracted topic:", topic)

    return {"topic": topic.topic}


def get_news_search_query(topic: str) -> str:
    """Generate an optimized search query from the topic"""
    prompt = f"""
    I need to search for news articles about this topic:
    "{topic}"

    Please generate a short, focused search query that would work well with a news API.
    The query should:
    - Be 1-3 words maximum
    - Focus on the key searchable terms
    - Remove any unnecessary context or descriptive words
    - Be optimized for finding relevant news articles

    Your response should be the following JSON object and nothing else. Do not include any other text, any markdown, or any comments.
    {{
        "search_query": "" // The optimized search query
    }}
    """

    structured_llm = smol_llm.with_structured_output(NewsSearchQuery)
    result = structured_llm.invoke(prompt)
    return result.search_query


def get_news_for_topic(topic: str) -> list[str]:
    """Get relevant news articles for the topic"""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("Warning: NEWS_API_KEY not found in environment")
        return []

    try:
        # First get an optimized search query
        search_query = get_news_search_query(topic)
        print(f"Using search query: {search_query}")

        url = f"https://newsapi.org/v2/everything?q={search_query}&apiKey={api_key}&pageSize=3"
        print(f"Fetching news from: {url}")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        articles = data.get("articles", [])
        return [
            f"Title: {article['title']}\nDescription: {article['description']}"
            for article in articles
        ]
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []


# Alright, seems to be functional for a PoC. This is using gpt-4o for speed, but for the idea where we'd have the AI pre-grenerate a bunch of betting pool ideas and have


# If the user doesn't provide a topic, generate one
def generate_topic(state: ResearchGraphOutput):
    """Generate a topic for the betting pool if user doesn't provide one"""

    if state.get("topic"):
        return {"topic": state.get("topic")}

    betting_pool_db = BettingPoolDB()
    recent_pools = betting_pool_db.get_recent_pools()

    recent_examples = "\n".join(
        [
            f"Topic: {pool[0]}\nBetting idea: {pool[1]['betting_pool_idea']}\n"
            for pool in recent_pools
        ]
    )

    topic_sys_msg = SystemMessage(
        content=f"""
        You have to determine a topic for a betting pool.
        
        The topic is just a theme for the betting pool.
        
        Here are the 5 most recent betting pools that were generated. Please avoid similar topics:
        
        <recent_pools>
        {recent_examples}
        </recent_pools>
        
        The theme should be something that is interesting and that people would want to bet on. Especially degenerate gamblers.
        
        The theme should be something that is a single sentence that is a high-level idea for a betting pool.
        
        The theme should be something that is currently in the news or that is trending. Or not, fuck it. Do whatever you want.
        
        Your response should be the following JSON object and nothing else. Do not include any other text, any markdown, or any comments.
        {{
            "topic": "" // The topic for the betting pool
        }}
    """
    )

    structured_llm = smol_llm.with_structured_output(BettingPoolGeneratorTopicOutput)
    topic = structured_llm.invoke([topic_sys_msg] + state["messages"])
    print("generated topic:", topic)
    return {"topic": topic.topic}


def generate_betting_pool_idea(state: ResearchGraphOutput):
    """Generate a betting pool"""
    print("OpenAI API key:", os.getenv("OPENAI_API_KEY"))
    print("Generating betting pool idea", state.get("prefer_fast_response"))
    betting_pool_db = BettingPoolDB()

    # Choose LLM based on preference
    selected_llm = smol_llm if state.get("prefer_fast_response") else big_llm

    # For fast responses, fetch news articles first
    news_context = ""
    if state.get("prefer_fast_response"):
        news_articles = get_news_for_topic(state.get("topic"))
        if news_articles:
            news_context = (
                "\n\nHere are some recent news articles about this topic:\n"
                + "\n\n".join(news_articles)
            )

    prompt = f"""
  
    Your goal is to generate an idea for something that users would like to bet on.
    
    Here is the high-level topic: 
    <topic>{state.get("topic")}</topic>
    {news_context}
    
    {f'Original user message: <message>{state.get("message")}</message>' if state.get("message") else ''}
    
    ## Generation guidelines
    - You can feel free to remix the topic, but try to keep the same theme.
    - If the user provided a specific message, prioritize and focus on creating a betting pool that directly addresses their query. Use the news context as reference, but don't feel constrained by it in this case.
    - Your response must be for a pool that can only be resolved in the future. Do not create a pool based on past events.
    - Avoid ambiguity in the betting pool idea. For instance, don't suggest "will a major stock reach 200% in...", instead provide a specific stock to see if it will reach a certain price.
    - Do not generate ideas for known outcomes or for things in the past. Note that the current date is {datetime.now().strftime("%Y-%m-%d")}.
    - For time-sensitive bets (like weather predictions), use dates that are very close to the current date.
    - You must provide exactly 2 mutually exclusive options. Examples:
      * "Above $500" vs "Below or equal to $500"
      * "Republicans" vs "Democrats"
      * "Before March 1st" vs "March 1st or later"
    - The options must be mutually exclusive and collectively exhaustive. There must not be any grey areas between the options - the answer will always be one of the two choices.
    - You should try to create a betting pool idea that is novel and would excite a community of degenerate gamblers.
    
     Your response must be the following JSON object and nothing else, no markdown, no comments, just the JSON object:
     {{
        "betting_pool_idea": "", // Single sentence describing what users are betting on
        "options": ["", "", ""], // List of options for the betting pool
        "closure_summary": "", // Single sentence summary of what date, condition, event, criteria, etc. that will determine a winner for this bet
        "closure_instructions": "", // Instructions for an LLM to follow to determine which option won
        "category": "", // The category of the betting idea. It should be one of the following: ["Politics", "Sports", "Crypto", "Entertainment", "AI", "Unknown"]
        "closure_date": "", // Timestamp in ISO 8601 format, UTC, when the bet will be closed if it applies. If it does apply, this date must be in the future both here and in the betting_pool_idea.
        "odds_format": "", // "decimal", "fractional", "american", idk what this is
        "odds_type": "", // "positive", "negative", idk what this is
        "odds_value": "" // The actual odds value, idk what this is
     }}
   
   Response must be a valid JSON object with no additional formatting, no markdown, and no code fences.
    """

    # Use the existing BettingPoolGeneratorOutput Pydantic model
    # structured_llm = selected_llm.with_structured_output(BettingPoolGeneratorOutput)
    # betting_pool_idea = structured_llm.invoke([prompt] + state["messages"])
    betting_pool_idea = selected_llm.invoke([prompt] + state["messages"])
    print("Betting pool idea:", betting_pool_idea)
    print("Betting pool idea type:", type(betting_pool_idea))
    print("Betting pool idea content:", betting_pool_idea.content)
    betting_pool_idea = json.loads(
        betting_pool_idea.content.replace("```json", "").replace(
            "```", ""
        )  # TODO I can't seem to convince the LLM to not include markdown enclosures, which breaks structured_output
    )
    print("Betting pool idea2:", betting_pool_idea)

    # Store the new betting pool idea in the database to avoid repeating the same idea multiple time when invoked
    try:
        betting_pool_db.add_betting_pool(state.get("topic"), betting_pool_idea)
    except Exception as e:
        print(f"Error storing betting pool: {e}")

    return {"betting_pool_idea": betting_pool_idea}


def search_images_for_pool(state: ResearchGraphOutput):
    """Search for relevant images for the betting pool topic and return one random image"""
    tavily_search = TavilySearchResults(
        max_results=20,
        include_images=True,
    )

    print(state)
    betting_pool = state.get("betting_pool_idea")
    topic = state.get("topic")

    # Create an optimized image search query
    search_prompt = f"""
    Generate a focused image search query for this betting pool:
    Topic: {topic}
    Betting idea: {betting_pool['betting_pool_idea'] if betting_pool else 'No betting pool available'}
    
    The query should:
    - Be 2-4 words maximum
    - Focus on the key visual elements of the idea
    - Be optimized for finding relevant images
    
    Your response should be the following JSON object and nothing else:
    {{
        "search_query": "" // The optimized image search query
    }}
    """

    structured_llm = smol_llm.with_structured_output(ImageSearchQuery)
    search_query = structured_llm.invoke(search_prompt)

    try:
        search_results = tavily_search.invoke(search_query.search_query)
        pprint(search_results)
        random_image = random.choice(search_results) if search_results else None
        return {"image_results": [random_image] if random_image else []}
    except Exception as e:
        print(f"Error searching for images: {e}")
        return {"image_results": []}


def search_images_for_pool(state: ResearchGraphOutput):
    """Search for relevant images for the betting pool topic and return one random image"""
    tavily_search = TavilySearchResults(
        max_results=20,
        include_images=True,
    )

    print(state)
    betting_pool = state.get("betting_pool_idea")
    topic = state.get("topic")

    # Create an optimized image search query
    search_prompt = f"""
    Generate a focused image search query for this betting pool:
    Topic: {topic}
    Betting idea: {betting_pool['betting_pool_idea'] if betting_pool else 'No betting pool available'}
    
    The query should:
    - Be 2-4 words maximum
    - Focus on the key visual elements of the idea
    - Be optimized for finding relevant images
    
    Your response should be the following JSON object and nothing else:
    {{
        "search_query": "" // The optimized image search query
    }}
    """

    structured_llm = smol_llm.with_structured_output(ImageSearchQuery)
    search_query = structured_llm.invoke(search_prompt)
    
    

    try:
        search_results = tavily_search.invoke(search_query.search_query)
        pprint(search_results)
        random_image = random.choice(search_results) if search_results else None
        return {"image_results": [random_image] if random_image else []}
    except Exception as e:
        print(f"Error searching for images: {e}")
        return {"image_results": []}


betting_pool_idea_generator = StateGraph(ResearchGraphOutput)
betting_pool_idea_generator.add_node("extract_topic", extract_topic)
betting_pool_idea_generator.add_node("generate_topic", generate_topic)
betting_pool_idea_generator.add_node(
    "generate_betting_pool_idea", generate_betting_pool_idea
)
# betting_pool_idea_generator.add_node("search_images", search_images_for_pool)

betting_pool_idea_generator.add_edge(START, "extract_topic")
betting_pool_idea_generator.add_edge("extract_topic", "generate_topic")
betting_pool_idea_generator.add_edge("generate_topic", "generate_betting_pool_idea")
betting_pool_idea_generator.add_edge("generate_betting_pool_idea", END)
# betting_pool_idea_generator.add_edge("search_images", END)

betting_pool_idea_generator_agent = betting_pool_idea_generator.compile()
