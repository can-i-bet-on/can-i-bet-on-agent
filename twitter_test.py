import os
import time
import tweepy
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
CLIENT_ID = os.getenv("TWITTER_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITTER_CLIENT_SECRET")

print("Loaded environment variables:")
print(f"ACCESS_TOKEN: {ACCESS_TOKEN}")
print(f"REFRESH_TOKEN: {REFRESH_TOKEN}")
print(f"CLIENT_ID: {CLIENT_ID}")
print(f"CLIENT_SECRET: {CLIENT_SECRET}")

# After loading environment variables, add validation
if not all([ACCESS_TOKEN, REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET]):
    raise ValueError(
        "Missing required environment variables. Please ensure ACCESS_TOKEN, "
        "REFRESH_TOKEN, CLIENT_ID, and CLIENT_SECRET are set in your .env file"
    )

# Twitter API endpoint for token refresh
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"

def refresh_access_token():
    """Refreshes the access token using the refresh token."""
    global ACCESS_TOKEN, REFRESH_TOKEN
    
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if response.status_code == 200:
        data = response.json()
        ACCESS_TOKEN = data["access_token"]
        REFRESH_TOKEN = data.get("refresh_token", REFRESH_TOKEN)  # Some services return a new refresh token
        os.environ["ACCESS_TOKEN"] = ACCESS_TOKEN
        os.environ["REFRESH_TOKEN"] = REFRESH_TOKEN
        print(f"NEW ACCESS_TOKEN: {ACCESS_TOKEN}")
        print(f"NEW REFRESH_TOKEN: {REFRESH_TOKEN}")
        print("Access token refreshed successfully.")
    else:
        print(f"Failed to refresh token: {response.text}")
        raise Exception("Token refresh failed")

def post_tweet():
    """Attempts to post a tweet using the current access token."""
    global ACCESS_TOKEN
    
    print("\nDebug - Values being passed to Tweepy client:")
    print(f"CLIENT_ID type: {type(CLIENT_ID)}")
    print(f"CLIENT_ID value: {CLIENT_ID}")
    
    client = tweepy.Client(
        consumer_key=CLIENT_ID,
        consumer_secret=CLIENT_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )
    
    print("Client created successfully")
    
    try:
        response = client.create_tweet(text="Hello world from eth Denver 2025!")
        print("Tweet posted successfully:", response)
    except tweepy.TweepyException as e:
        print(f"Failed to post tweet: {e}")
        if "401" in str(e) or "403" in str(e): 
            print("Access token may have expired. Refreshing token and retrying...")
            refresh_access_token()
            post_tweet()

if __name__ == "__main__":
    while True:
        post_tweet()
        print("Waiting 1 hour before next tweet...")
        time.sleep(3600)  
