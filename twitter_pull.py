import os
import time
import tweepy
import requests
from dotenv import load_dotenv
from datetime import timezone, datetime

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



def poll_tweet_mentions():
    review_timestamp = int(datetime.now(timezone.utc).timestamp() - POLLING_INTERVAL)

    print("reviewing since", review_timestamp)
    url = f"{TWITTERAPI_BASE_URL}/user/mentions?userName={LISTENER_TWITTER_HANDLE}&sinceTime={review_timestamp}"
    print("url", url)
    fetch_url = requests.get(url, headers={"x-api-key": TWITTERAPI_API_KEY})
    print(fetch_url.json())

if __name__ == "__main__":
    while True:
        poll_tweet_mentions()
        # print("Waiting 1 hour before next tweet...")
        time.sleep(POLLING_INTERVAL)  
