import os
from dotenv import load_dotenv
from db.redis import get_redis_client
import requests
from datetime import datetime, timedelta
import base64

# Load environment variables
load_dotenv()

def get_twitter_client_vars(redis_client):
    client_id = redis_client.get('TWITTER_CLIENT_ID')
    client_secret = redis_client.get('TWITTER_CLIENT_SECRET')
    return client_id, client_secret

def refresh_twitter_tokens(refresh_token):
    redis_client = get_redis_client()
    client_id, client_secret = get_twitter_client_vars(redis_client)
    """Refresh both access and refresh tokens using the Twitter API."""
    auth = f"{client_id}:{client_secret}"
    auth_bytes = auth.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    }
    
    response = requests.post(
        'https://api.twitter.com/2/oauth2/token',
        headers=headers,
        data=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.text}")
    
    return response.json()

def post_tweet(access_token, message, in_reply_to_id=None):
    """Post a tweet using the Twitter API v2."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'text': message,
    }
    if in_reply_to_id:
        data.update(reply={'in_reply_to_tweet_id': in_reply_to_id})
    
    response = requests.post(
        'https://api.twitter.com/2/tweets',
        headers=headers,
        json=data
    )
    
    if response.status_code != 201:
        raise Exception(f"Tweet posting failed: {response.text}")
    
    return response.json()

def refresh_and_store_tokens(redis_client):
    """Refresh tokens and store them in Redis."""
    current_refresh_token = redis_client.get('TWITTER_REFRESH_TOKEN')
    if not current_refresh_token:
        raise Exception("No refresh token found in Redis")
    
    # Refresh the tokens
    print("Refreshing tokens...")
    new_tokens = refresh_twitter_tokens(current_refresh_token)
    
    # Store new tokens in Redis with 90-day expiration
    expiration = int(timedelta(days=90).total_seconds())
    redis_client.set('TWITTER_ACCESS_TOKEN', new_tokens['access_token'], ex=expiration)
    redis_client.set('TWITTER_REFRESH_TOKEN', new_tokens['refresh_token'], ex=expiration)
    print("Successfully stored new tokens in Redis")
    
    return new_tokens['access_token']

def post_tweet_using_redis_token(tweet_text, in_reply_to_id=None):
    try:
        # Get Redis client
        redis_client = get_redis_client()
        
        # Attempt to post the tweet
        access_token = redis_client.get('TWITTER_ACCESS_TOKEN')
        result = post_tweet(access_token, tweet_text, in_reply_to_id)
        print(f"Successfully posted tweet! Tweet ID: {result['data']['id']}")
        return result['data']['id']
        
    except Exception as e:
        print(f"Error posting tweet: {str(e)}")
        
        # Attempt to refresh tokens and retry posting the tweet
        try:
            access_token = refresh_and_store_tokens(redis_client)
            result = post_tweet(access_token, tweet_text, in_reply_to_id)
            print(f"Successfully posted tweet after refreshing tokens! Tweet ID: {result['data']['id']}")
            return result['data']['id']
        
        except Exception as refresh_error:
            print(f"Error refreshing tokens or posting tweet after refresh: {str(refresh_error)}")
            return None
        
    finally:
        redis_client.close()

def main():
    try:
        # Get Redis client
        redis_client = get_redis_client()
        
        # Get current tokens from Redis
        current_refresh_token = redis_client.get('TWITTER_REFRESH_TOKEN')
        if not current_refresh_token:
            raise Exception("No refresh token found in Redis")
        
        # Refresh the tokens
        print("Refreshing tokens...")
        new_tokens = refresh_twitter_tokens(current_refresh_token)
        
        # Store new tokens in Redis with 90-day expiration
        expiration = int(timedelta(days=90).total_seconds())
        redis_client.set('TWITTER_ACCESS_TOKEN', new_tokens['access_token'], ex=expiration)
        redis_client.set('TWITTER_REFRESH_TOKEN', new_tokens['refresh_token'], ex=expiration)
        print("Successfully stored new tokens in Redis")
        
        # Post tweet with current timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tweet_text = f"Automated tweet posted at {current_time}"
        
        print("Posting tweet...")
        result = post_tweet(new_tokens['access_token'], tweet_text)
        print(f"Successfully posted tweet! Tweet ID: {result['data']['id']}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        redis_client.close()

if __name__ == "__main__":
    main()
