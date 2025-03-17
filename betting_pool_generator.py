from datetime import datetime, timedelta
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

tavily_search = TavilySearchResults(
    max_results=2,
    include_answer=True,
    include_raw_content=True,
    include_images=False,
    # search_depth="advanced", # Unclear what this does
)

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
    search_results: list
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
    - If the message is "celtics vs nets", the topic should be "Upcoming game between Boston Celtics and Brooklyn Nets"
    
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
        
        Remember that you must never generate a betting pool idea for a past event. Today's date and time is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}. Only generate ideas for future events past this date and time.
    """
    )

    structured_llm = smol_llm.with_structured_output(BettingPoolGeneratorTopicOutput)
    topic = structured_llm.invoke([topic_sys_msg] + state["messages"])
    print("generated topic:", topic)
    return {"topic": topic.topic}

def get_news_results(state: ResearchGraphOutput):
    # For fast responses, fetch news articles first
    news_results = ""
    news_articles = get_news_for_topic(state.get("topic"))
    if news_articles:
        news_results = (
            "\n\nHere are some recent news articles about this topic:\n"
            + "\n\n".join(news_articles)
        )
        print(f"Found {len(news_articles)} news articles for topic: {state.get('topic')}")
    else:
        print(f"No news articles found for topic: {state.get('topic')}")

    return {"news_results": news_results}

def search_for_topic(state: ResearchGraphOutput):
    """Search for information about the topic using Tavily search"""
    topic = state.get("topic")
    print(f"Searching for information about: {topic}")
    
    try:
        # Perform the search using Tavily
        search_results = tavily_search.invoke(topic)
        
        # Process the search results
        processed_results = []

        print(f"Search results: {search_results}")
        
        if isinstance(search_results, list):
            # Handle list format
            for result in search_results:
                if isinstance(result, dict):
                    # Extract title and content if available
                    title = result.get("title", "No title")
                    content = result.get("content", result.get("raw_content", "No content"))
                    url = result.get("url", "No URL")
                    
                    # Format the result
                    formatted_result = f"Title: {title}\nURL: {url}\nContent: {content}\n"
                    processed_results.append(formatted_result)
        elif isinstance(search_results, dict):
            # Handle dictionary format
            for result in search_results.get("results", []):
                if isinstance(result, dict):
                    # Extract title and content if available
                    title = result.get("title", "No title")
                    content = result.get("content", result.get("raw_content", "No content"))
                    url = result.get("url", "No URL")
                    
                    # Format the result
                    formatted_result = f"Title: {title}\nURL: {url}\nContent: {content}\n"
                    processed_results.append(formatted_result)
        
        # If we have an answer from Tavily, add it as well
        if isinstance(search_results, dict) and "answer" in search_results:
            answer = search_results["answer"]
            if answer:
                processed_results.append(f"Tavily Summary: {answer}")
        
        # Join all processed results
        if processed_results:
            print(f"Found {len(processed_results)} search results for topic: {topic}")
            return {"search_results": processed_results}
        else:
            print(f"No search results found for topic: {topic}")
            return {"search_results": ["No relevant information found for this topic."]}
            
    except Exception as e:
        print(f"Error searching for topic: {e}")
        return {"search_results": [f"Error searching for information: {str(e)}"]}

def generate_betting_pool_idea(state: ResearchGraphOutput):
    """Generate a betting pool"""
    print("Generating betting pool idea")
    betting_pool_db = BettingPoolDB()
    
    # Get current date for reference
    current_date = datetime.now()
    tomorrow = current_date + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%dT23:59:59Z")

    # For fast responses, fetch news articles first
    news_context = state.get("news_results")
    search_context = state.get("search_results")
    prompt = f"""
  
    Your goal is to generate an idea for something that users would like to bet on.
    
    Here is the high-level topic: 
    <topic>{state.get("topic")}</topic>
    <news_context>{news_context}</news_context>
    <search_context>{search_context}</search_context>
    
    {f'Original user message: <message>{state.get("message")}</message>' if state.get("message") else ''}
    
    ## Generation guidelines
    - You can feel free to remix the topic, but try to keep the same theme.
    - If the user provided a specific message, prioritize and focus on creating a betting pool that directly addresses their query. Use the news context as reference, but don't feel constrained by it in this case.
    - Your response must be for a pool that can only be resolved in the future. Do not create a pool based on past events.
    - Avoid ambiguity in the betting pool idea. For instance, don't suggest "will a major stock reach 200% in...", instead provide a specific stock to see if it will reach a certain price.
    - Do not generate ideas for known outcomes or for things in the past. Note that the current date and time is {current_date.strftime("%Y-%m-%d %H:%M:%S")}.
    - For time-sensitive bets (like weather predictions), use dates that are very close to the current date.
    - You must provide exactly 2 mutually exclusive options. Examples:
      * "Above $500" vs "Below or equal to $500"
      * "Republicans" vs "Democrats"
      * "Before March 1st" vs "March 1st or later"
    - The options must be mutually exclusive and collectively exhaustive. There must not be any grey areas between the options - the answer will always be one of the two choices.
    - You should try to create a betting pool idea that is novel and would excite a community of degenerate gamblers.
    
    ## IMPORTANT: BETTING POOL IDEA FORMAT
    - The betting_pool_idea field should include the specific date of the event when applicable
    - For sports games, the betting_pool_idea should follow this format: "Will [team] [action] against [opponent] on [specific date]?"
    - Examples:
      * "Will the Boston Celtics score more than 110 points against the Brooklyn Nets on November 10, 2023?"
      * "Will Bitcoin reach $80,000 by December 31, 2023?"
      * "Will it rain in Seattle on November 15, 2023?"
    - Try your best to include the specific date in the betting_pool_idea to make it clear exactly which event is being referenced
    
    ## IMPORTANT: DATE HANDLING
    - For the closure_date field, you MUST use a date that is factually accurate
    - If the news context mentions a specific date for an event (like a game date), use that EXACT date
    - NEVER make up a date far in the future (like 2025) unless you have explicit evidence for that date
    - For sports matchups specifically, search the news context carefully for phrases like:
      * "scheduled for"
      * "will play on"
      * "tonight"
      * "tomorrow"
      * "upcoming game"
      * Any specific dates mentioned
    - The date in the betting_pool_idea MUST match the date in the closure_date field
    
    ## IMPORTANT: PRIORITIZE IMMEDIATE EVENTS
    - If the topic is about a specific sports matchup or game, FIRST check the news context for information about an upcoming game
    - If you find information about an upcoming game in the news context, create a betting pool about that specific game
    - For sports matchups, look for information about:
      * When the game is scheduled to take place
      * Which teams are playing
      * Any relevant player information (injuries, recent performance)
    - If the news context mentions a specific upcoming game, use that exact information rather than making general predictions
    
    ## IMPORTANT: FACTUAL ACCURACY
    - DO NOT make up specific future events that aren't confirmed to happen
    - ONLY claim specific teams will play each other on specific dates if you have factual evidence from the news context
    - If you can't find specific information about an upcoming game in the news context:
      * For sports topics, create a bet about the next time these teams play (without specifying a date)
      * Or create a bet about player performance in their next matchup (without specifying a date)
    - If you're uncertain about a specific fact, make the betting pool more general rather than risking a factual error
    
     Your response must be the following JSON object and nothing else, no markdown, no comments, just the JSON object:
     {{
        "betting_pool_idea": "", // Single sentence describing what users are betting on - should include the specific date when applicable
        "options": ["", ""], // List of exactly 2 options for the betting pool
        "closure_summary": "", // Single sentence summary of what date, condition, event, criteria, etc. that will determine a winner for this bet
        "closure_instructions": "", // Instructions for an LLM to follow to determine which option won
        "category": "", // The category of the betting idea. It should be one of the following: ["Politics", "Sports", "Crypto", "Entertainment", "AI", "Unknown"]
        "closure_date": "", // Timestamp in ISO 8601 format, UTC, when the bet will be closed if it applies. If it does apply, this date must be in the future both here and in the betting_pool_idea.
        "odds_format": "", // "decimal", "fractional", "american", idk what this is
        "odds_type": "", // "positive", "negative", idk what this is
        "odds_value": "" // The actual odds value, idk what this is
     }}
   
   Response must be a valid JSON object with no additional formatting, no markdown, and no code fences.

   Remember that you must never generate a betting pool idea for a past event. Today's date and time is {current_date.strftime("%Y-%m-%d %H:%M:%S")}. Only generate ideas for future events past this date and time.
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
betting_pool_idea_generator.add_node("search_for_topic", search_for_topic)
betting_pool_idea_generator.add_node("get_news_results", get_news_results)
betting_pool_idea_generator.add_node(
    "generate_betting_pool_idea", generate_betting_pool_idea
)

betting_pool_idea_generator.add_edge(START, "extract_topic")
betting_pool_idea_generator.add_edge("extract_topic", "generate_topic")
betting_pool_idea_generator.add_edge("generate_topic", "get_news_results")
betting_pool_idea_generator.add_edge("get_news_results", "search_for_topic")
betting_pool_idea_generator.add_edge("search_for_topic", "generate_betting_pool_idea")
betting_pool_idea_generator.add_edge("generate_betting_pool_idea", END)

betting_pool_idea_generator_agent = betting_pool_idea_generator.compile()
