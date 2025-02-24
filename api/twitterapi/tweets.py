from dataclasses import dataclass


@dataclass(eq=True, frozen=True) 
class TweetAuthor:
	# match the following json but using snake case
	# {
                # "type": "user",
                # "userName": "BetbugDev",
                # "url": "https://x.com/BetbugDev",
                # "twitterUrl": "https://twitter.com/BetbugDev",
                # "id": "1523650788802711553",
                # "name": "Betbug Dev",
                # "isVerified": false,
                # "isBlueVerified": false,
                # "profilePicture": "https://pbs.twimg.com/profile_images/1523651527239380992/Csg_FNIj_normal.jpg",
                # "coverPicture": "",
                # "description": "",
            #     "location": "",
            #     "followers": 10,
            #     "following": 152,
            #     "status": "",
            #     "canDm": false,
            #     "canMediaTag": true,
            #     "createdAt": "Mon May 09 13:09:28 +0000 2022",
            #     "entities": {
            #         "description": {
            #             "urls": []
            #         },
            #         "url": {}
            #     },
            #     "fastFollowersCount": 0,
            #     "favouritesCount": 50,
            #     "hasCustomTimelines": true,
            #     "isTranslator": false,
            #     "mediaCount": 2,
            #     "statusesCount": 105,
            #     "withheldInCountries": [],
            #     "affiliatesHighlightedLabel": {},
            #     "possiblySensitive": false,
            #     "pinnedTweetIds": [],
            #     "profile_bio": {
            #         "description": "Coding at the forefront of a swiftly changing society",
            #         "entities": {
            #             "description": {}
            #         }
            #     },
            #     "isAutomated": false,
            #     "automatedBy": null
            # }
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
			# create a methods that converts the following json
			#{
			#             "type": "tweet",
			# "id": "1894125452937269400",
			# "url": "https://x.com/BetbugDev/status/1894125452937269400",
			# "text": "@CanIBetOn will an AI agent launch this week?",
			# "source": "Twitter for iPhone",
			# "retweetCount": 0,
			# "replyCount": 0,
			# "likeCount": 0,
			# "quoteCount": 0,
			# "viewCount": 0,
			# "createdAt": "Mon Feb 24 20:41:13 +0000 2025",
			# "lang": "en",
			# "bookmarkCount": 0,
			# "isReply": false,
			# "inReplyToId": null,
			# "conversationId": "1894125452937269400",
			# "inReplyToUserId": "1423703185496199168",
			# "inReplyToUsername": "CanIBetOn",
			# }
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
