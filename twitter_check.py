import os
import asyncio
from dotenv import load_dotenv
from datetime import timezone, datetime
from api.twitterapi.tweets import Tweet, twitterapi_get
from betting_pool_core import call_langgraph_agent, create_pool, create_pool_data, generate_market_creation_tweet_content, set_twitter_post_id
from betting_pool_generator import betting_pool_idea_generator_agent
from db.redis import get_redis_client
from twitter_post import post_tweet_using_redis_token

# Load environment variables
load_dotenv()

TWITTERAPI_BASE_URL = "https://api.twitterapi.io/twitter"
TWITTERAPI_API_KEY = os.getenv("TWITTERAPI_API_KEY")
FRONTEND_URL_PREFIX = os.getenv("FRONTEND_URL_PREFIX")
LISTENER_TWITTER_HANDLE = os.getenv("LISTENER_TWITTER_HANDLE")
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", 30))
POLLING_WINDOW = int(os.getenv("POLLING_WINDOW", 3600))
GENERATE_BETTING_POOL_COMMAND = os.getenv("GENERATE_BETTING_POOL_COMMAND", "@CanIBetOn")
# After loading environment variables, add validation
if not all([TWITTERAPI_API_KEY, LISTENER_TWITTER_HANDLE, FRONTEND_URL_PREFIX]):
		raise ValueError(
				"Missing required environment variables. Please ensure TWITTERAPI_API_KEY, LISTENER_TWITTER_HANDLE, FRONTEND_URL_PREFIX "
				"are set in your .env file"
		)


def pull_tweet(tweet_id):
		url = f"{TWITTERAPI_BASE_URL}/tweets?tweet_ids={tweet_id}"
		print(f"pulling tweet {tweet_id} from {url}")
		response = twitterapi_get(url)
		if response:
				data = response.json()
				if data and data["tweets"]:
						return Tweet.from_dict(data["tweets"][0])

		return None

def pull_tweets(handle):
		review_timestamp = int(datetime.now(timezone.utc).timestamp() - POLLING_WINDOW)

		print("reviewing since", review_timestamp)
		url = f"{TWITTERAPI_BASE_URL}/user/mentions?userName={handle}&sinceTime={review_timestamp}"
		
		response = twitterapi_get(url)
		if response:
				data = response.json()
				if data and data["tweets"]:
						return [Tweet.from_dict(tweet) for tweet in data["tweets"]]
				return []
		else:
				return None


async def poll_tweet_mentions():
		redis_client = get_redis_client()
		reviewed_tweets = redis_client.smembers("reviewed_tweets")
		tweets = pull_tweets(LISTENER_TWITTER_HANDLE)
		if tweets is None:
				print("Failed to fetch tweets, will retry in next polling interval")
				return
		if tweets == []:
				print("No tweets found, will retry in next polling interval")
				return
		bets = [propose_bet(tweet_data) for tweet_data in tweets if tweet_data.tweet_id not in reviewed_tweets]
		return asyncio.gather(*bets)


async def propose_bet(tweet_data: Tweet):
		redis_client = get_redis_client()
		thread_text = []
		current_tweet = tweet_data
		while current_tweet.is_reply:
				prior_tweet = pull_tweet(current_tweet.in_reply_to_id)
				thread_text.append(f"@{prior_tweet.author.user_name}: {prior_tweet.text}")
				current_tweet = prior_tweet


		print(f"Proposing bet for new tweet from @{tweet_data.author.user_name}: {tweet_data.text}", f"replying to thread: {"\n----------\n".join(thread_text)}" if len(thread_text) > 0 else "")
		try:
				tweet_text = tweet_data.text.replace(f'{GENERATE_BETTING_POOL_COMMAND}', '').strip()
				# Call the Langraph agent
				langgraph_agent_response = await call_langgraph_agent(betting_pool_idea_generator_agent, tweet_text, "\n----------\n".join(thread_text))
				print(f"langgraph_agent_response: {langgraph_agent_response}")
								# Use the new function to create pool_data
				pool_data = create_pool_data(langgraph_agent_response, tweet_data.author.user_name, tweet_data.author.author_id)
				pool_id = create_pool(pool_data)
				print("created pool", pool_id)

				redis_client.sadd("reviewed_tweets", tweet_data.tweet_id)
				quote_tweet_text = generate_market_creation_tweet_content(pool_id, pool_data, FRONTEND_URL_PREFIX)
				timeline_post_id = post_tweet_using_redis_token(f"{quote_tweet_text}\n{tweet_data.url}")
				if timeline_post_id is not None:
					set_twitter_post_id(pool_id, timeline_post_id)
				return langgraph_agent_response
		except Exception as e:
				print("Something went wrong with the bet proposal: ", str(e))

if __name__ == "__main__":
		redis_client = get_redis_client()
		asyncio.run(poll_tweet_mentions())
