import os
import time
import tweepy
import requests
import asyncio
from dotenv import load_dotenv
from datetime import timezone, datetime
import dataclasses
from api.twitterapi.tweets import Tweet
from api.langgraph.agent import call_langgraph_agent

# Load environment variables
load_dotenv()

# ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
# ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
# REFRESH_TOKEN = os.getenv("TWITTER_REFRESH_TOKEN")
# CLIENT_ID = os.getenv("TWITTER_CLIENT_ID")
# CLIENT_SECRET = os.getenv("TWITTER_CLIENT_SECRET")

TWITTERAPI_BASE_URL = "https://api.twitterapi.io/twitter"
TWITTERAPI_API_KEY = os.getenv("TWITTERAPI_API_KEY")
LISTENER_TWITTER_HANDLE = os.getenv("LISTENER_TWITTER_HANDLE")
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL"))

# After loading environment variables, add validation
if not all([TWITTERAPI_API_KEY, LISTENER_TWITTER_HANDLE, POLLING_INTERVAL]):
    raise ValueError(
        "Missing required environment variables. Please ensure TWITTERAPI_API_KEY, LISTENER_TWITTER_HANDLE, "
        "POLLING_INTERVAL are set in your .env file"
    )




def pull_tweets(handle):
    review_timestamp = int(datetime.now(timezone.utc).timestamp() - POLLING_INTERVAL)

    print("reviewing since", review_timestamp)
    url = f"{TWITTERAPI_BASE_URL}/user/mentions?userName={handle}&sinceTime={review_timestamp}"
    
    try:
        response = requests.get(url, headers={"x-api-key": TWITTERAPI_API_KEY})
        response.raise_for_status()
        
        data = response.json()
        if data and data["tweets"]:
            return [Tweet.from_dict(tweet) for tweet in data["tweets"]]
        return []
        
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        if response.status_code == 429:
            print("Rate limit exceeded. Consider implementing backoff.")
        elif response.status_code == 401:
            print("Authentication error. Check your API key.")
        elif response.status_code == 404:
            print(f"User {handle} not found.")
        return None
        
    except requests.exceptions.RequestException as err:
        print(f"Error occurred while making request: {err}")
        return None
        
    except ValueError as err:  # Includes JSONDecodeError
        print(f"Error parsing JSON response: {err}")
        return None


async def poll_tweet_mentions():
    tweets = pull_tweets(LISTENER_TWITTER_HANDLE)
    if tweets is None:
        print("Failed to fetch tweets, will retry in next polling interval")
        return
        
    bets = [propose_bet(tweet_data) for tweet_data in tweets]
    return asyncio.gather(*bets)


async def propose_bet(tweet_data: Tweet):
    print(f"Proposing bet for new tweet from @{tweet_data.author.user_name}: {tweet_data.text}")
    try:
        # Call the Langraph agent
        langgraph_agent_response = await call_langgraph_agent(tweet_data.text, "")
        print(f"langgraph_agent_response: {langgraph_agent_response}")
        return langgraph_agent_response
    except Exception as e:
        print("Something went wrong with the bet proposal: ", str(e))

if __name__ == "__main__":
    while True:
        asyncio.run(poll_tweet_mentions())
        # print("Waiting 1 hour before next tweet...")
        time.sleep(POLLING_INTERVAL)  
