from datetime import datetime
from pprint import pprint
from typing import Annotated
from pydantic import BaseModel
import json

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from common import big_llm, smol_llm
from db.betting_pool_db import BettingPoolDB
from langchain_community.tools.tavily_search import TavilySearchResults
import random

from tools.news import get_news_for_topic

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
    topic: str
    search_results: list[str]
    news_results: list[str]
    # image_results: list[dict]
    betting_pool_idea: BettingPoolGeneratorOutput


class BettingPoolGeneratorTopicOutput(BaseModel):
    topic: str


class ImageSearchQuery(BaseModel):
    search_query: str


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
    print("Generating betting pool idea")
    betting_pool_db = BettingPoolDB()

    # Choose LLM based on preference

    # For fast responses, fetch news articles first
    news_context = ""
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
    betting_pool_idea = big_llm.invoke([prompt] + state["messages"])
    print("Betting pool idea:", betting_pool_idea)
    betting_pool_idea = json.loads(
        betting_pool_idea.content.replace("```json", "").replace(
            "```", ""
        )  # TODO I can't seem to convince the LLM to not include markdown enclosures, which breaks structured_output
    )

    # Store the new betting pool idea in the database to avoid repeating the same idea multiple time when invoked
    try:
        betting_pool_db.add_betting_pool(state.get("topic"), betting_pool_idea)
    except Exception as e:
        print(f"Error storing betting pool: {e}")

    return {"betting_pool_idea": betting_pool_idea}


betting_pool_idea_generator = StateGraph(ResearchGraphOutput)
betting_pool_idea_generator.add_node("extract_topic", extract_topic)
betting_pool_idea_generator.add_node("generate_topic", generate_topic)
betting_pool_idea_generator.add_node(
    "generate_betting_pool_idea", generate_betting_pool_idea
)

betting_pool_idea_generator.add_edge(START, "extract_topic")
betting_pool_idea_generator.add_edge("extract_topic", "generate_topic")
betting_pool_idea_generator.add_edge("generate_topic", "generate_betting_pool_idea")
betting_pool_idea_generator.add_edge("generate_betting_pool_idea", END)

betting_pool_idea_generator_agent = betting_pool_idea_generator.compile()
