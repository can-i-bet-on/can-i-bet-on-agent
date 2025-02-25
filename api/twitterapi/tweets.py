from dataclasses import dataclass

import requests
import os

TWITTERAPI_API_KEY = os.getenv("TWITTERAPI_API_KEY")

@dataclass(eq=True, frozen=True) 
class TweetAuthor:

	type: str
	user_name: str
	url: str
	twitter_url: str
	author_id: str
	name: str
	is_verified: bool
	is_blue_verified: bool
	profile_picture: str
	cover_picture: str
	description: str
	location: str
	followers: int
	following: int
	status: str
	can_dm: bool
	can_media_tag: bool
	created_at: str
	is_automated: bool

	@classmethod
	def from_dict(cls, data: dict):
		return cls(
			type=data["type"],
			user_name=data["userName"],
			url=data["url"],
			twitter_url=data["twitterUrl"],
			author_id=data["id"],
			name=data["name"],
			is_verified=data["isVerified"],
			is_blue_verified=data["isBlueVerified"],
			profile_picture=data["profilePicture"],
			cover_picture=data["coverPicture"],
			description=data["description"],
			location=data["location"],
			followers=data["followers"],
			following=data["following"],
			status=data["status"],
			can_dm=data["canDm"],
			can_media_tag=data["canMediaTag"],
			created_at=data["createdAt"],
			is_automated=data["isAutomated"],
		)
	
	


@dataclass(eq=True, frozen=True)
class Tweet:
    tweet_id: str
    url: str
    created_at: str
    text: str
    source: str
    retweet_count: int
    reply_count: int
    like_count: int
    quote_count: int
    view_count: int
    bookmark_count: int
    is_reply: bool
    conversation_id: str
    author: TweetAuthor
    in_reply_to_id: str | None = None
    in_reply_to_user_id: str | None = None
    in_reply_to_username: str | None = None

    @classmethod
    def from_dict(cls, data: dict):
            return cls(
                tweet_id=data["id"],
                text=data["text"],
                created_at=data["createdAt"],
                author=TweetAuthor.from_dict(data["author"]),
                url=data["url"],
                source=data["source"],
                retweet_count=data["retweetCount"],
                reply_count=data["replyCount"],
                like_count=data["likeCount"],
                quote_count=data["quoteCount"],
                view_count=data["viewCount"],
                bookmark_count=data["bookmarkCount"],
                is_reply=data["isReply"],
                in_reply_to_id=data["inReplyToId"],
                conversation_id=data["conversationId"],
                in_reply_to_user_id=data["inReplyToUserId"],
                in_reply_to_username=data["inReplyToUsername"],
            )

def twitterapi_get(url):
    try:
        response = requests.get(url, headers={"x-api-key": TWITTERAPI_API_KEY})
        response.raise_for_status()
        return response
        
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        if response.status_code == 429:
            print("Rate limit exceeded. Consider implementing backoff.")
        elif response.status_code == 401:
            print("Authentication error. Check your API key.")
        elif response.status_code == 404:
            print(f"Resourcenot found.")
        return None
        
    except requests.exceptions.RequestException as err:
        print(f"Error occurred while making request: {err}")
        return None
        
    except ValueError as err:  # Includes JSONDecodeError
        print(f"Error parsing JSON response: {err}")
        return None
