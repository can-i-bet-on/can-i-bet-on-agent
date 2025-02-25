import asyncio
import time
from db.redis import get_redis_client
from twitter_check import POLLING_INTERVAL, poll_tweet_mentions


if __name__ == "__main__":
    while True:
        redis_client = get_redis_client()
        asyncio.run(poll_tweet_mentions())
        # print("Waiting 1 hour before next tweet...")
        time.sleep(POLLING_INTERVAL)  
