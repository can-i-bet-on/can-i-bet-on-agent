from datetime import datetime, timedelta
from web3 import Web3
import os
import json
import urllib.parse
from dotenv import load_dotenv
from db.redis import get_redis_client
import requests
from twitter_post import post_tweet_using_redis_token
from eth_account import Account

# Load environment variables
load_dotenv()

# Environment variables
WEB3_NODE_URL = os.getenv("WEB3_NODE_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
GAS_LIMIT = int(os.getenv("GAS_LIMIT", 3000000))
SUBGRAPH_URL = os.getenv("SUBGRAPH_URL")

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(WEB3_NODE_URL))

# Load contract ABI from JSON file
with open("BettingPools.json", "r") as abi_file:
    abi_data = json.load(abi_file)
    CONTRACT_ABI = abi_data["abi"]

# Initialize contract
CONTRACT = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
ACCOUNT = w3.eth.account.from_key(PRIVATE_KEY)


def generate_twitter_intent_url(text):
    encoded_text = urllib.parse.quote(text)
    return f"https://twitter.com/intent/tweet?text={encoded_text}"


async def call_langgraph_agent(agent, message_text=None, original_text=None):
    message = {"role": "user", "content": "Generate a betting pool for me."}
    if original_text:
        message["content"] += f"\n<original_text>{original_text}</original_text>"
    if message_text:
        message["content"] += f"\n<text>{message_text}</text>"

    try:
        agent_response = agent.invoke(
            {
                "messages": [message],
                "prefer_fast_response": True,
            }
        )
        return agent_response
    except Exception as e:
        raise Exception(f"Error fetching data from Langraph: {str(e)}")


def create_pool(pool_data):
    pool_id = None
    try:
        tx = CONTRACT.functions.createPool(
            (
                pool_data["question"],
                pool_data["options"],
                pool_data["betsCloseAt"],
                pool_data["decisionDate"],
                pool_data["imageUrl"],
                pool_data["category"],
                pool_data["creatorName"],
                pool_data["creatorId"],
                pool_data["closureCriteria"],
                pool_data["closureInstructions"],
            )
        ).build_transaction(
            {
                "from": ACCOUNT.address,
                "nonce": w3.eth.get_transaction_count(ACCOUNT.address),
                "gas": GAS_LIMIT,
                "gasPrice": w3.eth.gas_price,
            }
        )

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(
            f"Pool successfully created. Transaction hash: {tx_hash.hex()}, Transaction receipt: {receipt}"
        )

        if receipt["logs"]:
            data = receipt["logs"][0]["data"]
            pool_id = int.from_bytes(data[:32], byteorder="big")

            print(f"Pool created with ID: {pool_id}")
        else:
            print("No logs found in receipt")

        return pool_id

    except Exception as e:
        raise Exception(f"Error creating pool: {str(e)}")

def generate_market_creation_tweet_content(pool_id, pool_data, frontend_url_prefix):
    if pool_id is not None:
                # Convert to hex, remove '0x' prefix, ensure even length with zero padding, then add '0x' back
        # hex_without_prefix = hex(pool_id)[2:]  # Remove '0x' prefix
        # if len(hex_without_prefix) % 2 != 0:
        #     hex_without_prefix = '0' + hex_without_prefix
        pool_id_hex = get_pool_id_hex(pool_id)
        full_url = f"{frontend_url_prefix}{pool_id_hex}"

        # Format the tweet using the passed pool_data
        tweet_text = (
            f"🎲 New Prediction Pool!\n\n"
            f"Q: {pool_data['question']}\n"
            f"A) {pool_data['options'][0]}\n"
            f"B) {pool_data['options'][1]}\n\n"
            f"Place your bets: {full_url}"
        )

        return tweet_text
    else:
        return None


def generate_market_close_tweet_content(
    pool_id, pool_data, frontend_url_prefix, original_tweet_id, grade_result
):
    """
    Generate tweet content for market closure, quoting the original tweet.

    Args:
        pool_id (int): The pool ID
        pool_data (dict): Pool data containing question and options
        frontend_url_prefix (str): URL prefix for the frontend
        original_tweet_id (str): ID of the original market creation tweet
        grade_result (dict): Result from grading containing the outcome

    Returns:
        str: Formatted tweet content
    """

    if pool_id is not None:
        # Convert to hex, remove '0x' prefix, ensure even length with zero padding, then add '0x' back
        # hex_without_prefix = hex(pool_id)[2:]  # Remove '0x' prefix
        # if len(hex_without_prefix) % 2 != 0:
        #     hex_without_prefix = '0' + hex_without_prefix
        pool_id_hex = get_pool_id_hex(pool_id)
        full_url = f"{frontend_url_prefix}{pool_id_hex}"

        # Get the result text
        result_text = ""
        if grade_result["result"] == "option A":
            result_text = f"Option A wins: {pool_data['options'][0]}"
        elif grade_result["result"] == "option B":
            result_text = f"Option B wins: {pool_data['options'][1]}"
        elif grade_result["result"] == "push":
            result_text = "Market resulted in a push"
        else:
            return None

        # Format the tweet
        tweet_text = (
            f"🎯 Market Closed!\n\n"
            f"Q: {pool_data['question']}\n"
            f"Result: {result_text}\n\n"
            f"View details: {full_url}\n\n"
            f"https://twitter.com/user/status/{original_tweet_id}"
        )

        return tweet_text
    else:
        return None


def post_close_market_tweets(graded_pools_with_results, frontend_url_prefix):
    for pool_id, grade_result in graded_pools_with_results.items():
        pool_data = grade_result["pool_data"]
        if int(pool_data["totalBets"]) > 0:
            original_tweet_id = pool_data["xPostId"]
            tweet_text = generate_market_close_tweet_content(
                pool_id, pool_data, frontend_url_prefix, original_tweet_id, grade_result
            )
            post_tweet_using_redis_token(tweet_text)
            print("Posted closed market tweet for pool {pool_id}")


def create_pool_data(langgraph_agent_response, creator_name, creator_id):
    betting_pool_data = langgraph_agent_response["betting_pool_idea"]
    try:
        decision_date = datetime.strptime(
            betting_pool_data["closure_date"], "%Y-%m-%dT%H:%M:%S"
        )
    except ValueError:
        decision_date = datetime.strptime(
            betting_pool_data["closure_date"], "%Y-%m-%dT%H:%M:%SZ"
        )

    # Set bets_close_at to one day before the decision_date
    bets_close_at = datetime.now() + timedelta(days=1)
    if bets_close_at > decision_date:
        bets_close_at = decision_date - timedelta(seconds=5)

    pool_data = {
        "question": betting_pool_data["betting_pool_idea"],
        "options": [betting_pool_data["options"][0], betting_pool_data["options"][1]],
        "betsCloseAt": int(bets_close_at.timestamp()),
        "decisionDate": int(decision_date.timestamp()),
        # 'imageUrl': langgraph_agent_response['image_results'][0]['url'] if langgraph_agent_response['image_results'] else "",
        "imageUrl": "",
        "category": betting_pool_data["category"],
        "creatorName": creator_name,
        "creatorId": creator_id,
        "closureCriteria": betting_pool_data["closure_summary"],
        "closureInstructions": betting_pool_data["closure_instructions"],
    }

    print(f"Pool data: {pool_data}")

    return pool_data


def set_twitter_post_id(pool_id, tweet_id):
    try:
        # Build the transaction
        tx = CONTRACT.functions.setTwitterPostId(pool_id, tweet_id).build_transaction(
            {
                "from": ACCOUNT.address,
                "nonce": w3.eth.get_transaction_count(ACCOUNT.address),
                "gas": GAS_LIMIT,
                "gasPrice": w3.eth.gas_price,
            }
        )

        # Sign the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)

        # Send the transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for the transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        print(
            f"Setting twitter transaction successful with hash: {tx_hash.hex()}, receipt: {receipt}"
        )
        return receipt
    except Exception as e:
        raise Exception(f"Error setting Twitter post ID: {str(e)}")


def fetch_pending_pools():
    """
    Fetches pending pools from the GraphQL endpoint and prints their details.
    """
    query = """
    query {
      pools(where: {status: "PENDING"}) {
        id
        poolIntId
        status
        question
        options
        betsCloseAt
        decisionDate
        closureCriteria
        closureInstructions
        totalBets
        totalBetsByOption
        xPostId
      }
    }
    """

    try:
        # Send the POST request
        print(f"SUBGRAPH_URL: {SUBGRAPH_URL}")
        response = requests.post(SUBGRAPH_URL, json={"query": query})
        response.raise_for_status()

        # Parse the JSON response
        data = response.json()

        # Return the pools (already filtered by the query)
        return data["data"]["pools"]
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if response is not None:
            print(f"Response content: {response.content}")
        return []


def grade_pool_with_langgraph_agent(agent, pool):
    pool_idea = {}
    pool_idea["betting_pool_idea"] = pool["question"]
    pool_idea["closure_criteria"] = pool["closureCriteria"]
    pool_idea["closure_instructions"] = pool["closureInstructions"]
    pool_idea["closure_datetime"] = int(pool["decisionDate"])
    pool_idea["options"] = pool["options"]
    pool_idea["current_datetime"] = datetime.now().timestamp()

    idea_grade = agent.invoke(
        {
            "betting_pool_idea": pool_idea,
        }
    )

    result = idea_grade["betting_pool_idea_result"]

    # Consider both time period analysis and decision date
    if result.get("time_period_analysis", {}).get(
        "period_has_passed", False
    ) and result.get("time_period_analysis", {}).get(
        "official_results_available", False
    ):
        # If the period has passed and we have official results, use them
        return result
    elif datetime.fromtimestamp(pool_idea["closure_datetime"]) > datetime.now():
        # If the decision date hasn't passed, stick with "not resolved yet"
        result["result"] = "not resolved yet"
        result["probabilities"] = {option: 0 for option in pool["options"]}

    return result


def store_pool_grade(pool_id_str, grade):
    redis_client = get_redis_client()
    print(
        f"Setting pool grade for {pool_id_str} to {grade} with redis_client {redis_client}"
    )
    redis_client.set(f"POOL_GRADE:{pool_id_str}", grade)
    redis_client.close()


def call_grade_pool_contract(pool_id, grade_result):
    try:
        # Build the transaction
        tx = CONTRACT.functions.gradeBet(pool_id, grade_result).build_transaction(
            {
                "from": ACCOUNT.address,
                "nonce": w3.eth.get_transaction_count(ACCOUNT.address),
                "gas": GAS_LIMIT,
                "gasPrice": w3.eth.gas_price,
            }
        )

        # Sign the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)

        # Send the transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for the transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        print(
            f"Grading pool transaction successful with hash: {tx_hash.hex()}, receipt: {receipt}"
        )
        return receipt
    except Exception as e:
        raise Exception(f"Error calling gradeBet contract: {str(e)}")


def call_payout_bets_contract(bet_ids):
    try:
        # Build the transaction
        tx = CONTRACT.functions.claimPayouts(bet_ids).build_transaction(
            {
                "from": ACCOUNT.address,
                "nonce": w3.eth.get_transaction_count(ACCOUNT.address),
                "gas": GAS_LIMIT,
                "gasPrice": w3.eth.gas_price,
            }
        )

        # Sign the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)

        # Send the transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for the transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        print(
            f"Grading pool transaction successful with hash: {tx_hash.hex()}, receipt: {receipt}"
        )
        return receipt
    except Exception as e:
        raise Exception(f"Error calling gradeBet contract: {str(e)}")


def fetch_bets_for_pool(pool_id):
    """
    Fetches bets for a specific pool from the GraphQL endpoint.

    Args:
        pool_id (int): The pool ID to fetch bets for

    Returns:
        list: List of bets for the specified pool
    """
    query = """
    query($poolId: Int!) {
      bets(where: {poolIntId: $poolId}) {
        id
        betIntId
        poolIntId
        payoutClaimed
      }
    }
    """

    variables = {"poolId": pool_id}

    try:
        # Send the POST request
        print(f"Fetching bets for pool {pool_id}")
        response = requests.post(
            SUBGRAPH_URL, json={"query": query, "variables": variables}
        )
        response.raise_for_status()

        # Parse the JSON response
        data = response.json()

        # Return the bets
        return data["data"]["bets"]
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if response is not None:
            print(f"Response content: {response.content}")
        return []

## the following functions are for bot auto-betting 
## commented out for now as we don't need it

# def fetch_pending_pools_with_unbalanced_liquidity():
#     """Fetches pending betting pools that have liquidity on only one side"""
    
#     try:
#         pools = fetch_pending_pools()
        
#         # Filter for pools with liquidity on only one side
#         unbalanced_pools = []
#         for pool in pools:
#             total_bets_by_option = pool['totalBetsByOption']
#             if any(int(amount) > 0 for amount in total_bets_by_option) and any(int(amount) == 0 for amount in total_bets_by_option):
#                 unbalanced_pools.append(pool)

#         if unbalanced_pools:
#             unbalanced_pools = sorted(unbalanced_pools, key=lambda x: -1 * int(x['totalBets']))
        
#         return unbalanced_pools
#     except Exception as e:
#         print(f"Error fetching pending pools with unbalanced liquidity: {e}")
#         return []


# def generate_wallet_from_private_key(private_key):
#     """
#     Generates a wallet address from a private key.
    
#     Args:
#         private_key (str): The private key with or without '0x' prefix
        
#     Returns:
#         tuple: (account, wallet_address) where account is the Account object and 
#                wallet_address is the public address string
#     """
#     try:
#         # Add 0x prefix if not present
#         if not private_key.startswith('0x'):
#             private_key = '0x' + private_key
            
#         # Get the account from the private key
#         account = Account.from_key(private_key)
        
#         # Get the wallet address
#         wallet_address = account.address
        
#         return wallet_address
#     except Exception as e:
#         raise Exception(f"Error generating wallet from private key: {str(e)}")

# def get_signing_props(chain_id: int, pool_id: str, option_index: int, amount: str, user_wallet_address: str):
#     """
#     Gets signing properties from the API for placing a bet.
#     """
#     try:
#         # Get base URL from environment variable, with fallback
#         url = os.getenv('WALLET_SIGNING_PROPS_URL')
        
#         payload = {
#             "chainId": chain_id,
#             "poolId": pool_id,
#             "optionIndex": option_index,
#             "amount": amount,
#             "userWalletAddress": user_wallet_address
#         }
        
#         headers = {
#             'Content-Type': 'application/json'
#         }
        
#         print(f"Getting signing parameters: {payload}")
#         response = requests.post(url, json=payload, headers=headers)
#         response.raise_for_status()
        
#         signing_data = response.json()
#         print("Received signing parameters:", signing_data)
#         return signing_data
        
#     except requests.exceptions.RequestException as e:
#         raise Exception(f"Failed to get signing props: {str(e)}")
    

# from web3 import Web3
# from eth_account.messages import encode_typed_data
# from eth_account import Account
# import time

# def sign_usdc_permit(
#     private_key: str,
#     chain_id: int,
#     usdc_address: str,
#     spender_address: str,
#     amount: str,
#     usdc_nonce: int,
#     usdc_name: str
# ):
#     """
#     Signs a USDC permit using EIP-712
    
#     Args:
#         private_key: The private key to sign with
#         chain_id: The chain ID
#         usdc_address: The USDC contract address
#         spender_address: The address allowed to spend the tokens
#         amount: The amount to approve
#         usdc_nonce: The current nonce for the user in the USDC contract
#         usdc_name: The name of the USDC token
        
#     Returns:
#         A tuple containing the signature components and deadline
#     """
#     # Create account from private key
#     account = Account.from_key(private_key)
#     wallet_address = account.address
    
#     # Set deadline to 1 hour from now
#     usdc_permit_deadline = int(time.time()) + 3600
    
#     # Define the domain separator
#     domain_data = {
#         "name": usdc_name,
#         "version": "1",
#         "chainId": chain_id,
#         "verifyingContract": usdc_address
#     }
    
#     # Define the types for EIP-2612 permit
#     types = {
#         "Permit": [
#             {"name": "owner", "type": "address"},
#             {"name": "spender", "type": "address"},
#             {"name": "value", "type": "uint256"},
#             {"name": "nonce", "type": "uint256"},
#             {"name": "deadline", "type": "uint256"}
#         ]
#     }
    
#     # Define the message to sign
#     message = {
#         "owner": wallet_address,
#         "spender": spender_address,
#         "value": amount,
#         "nonce": usdc_nonce,
#         "deadline": usdc_permit_deadline
#     }
    
#     print("Permit data to sign:", {
#         "domain": domain_data,
#         "types": types,
#         "message": message
#     })
    
#     # Create the structured data for signing
#     structured_data = {
#         "types": types,
#         "domain": domain_data,
#         "primaryType": "Permit",
#         "message": message
#     }
    
#     # Encode and sign the data
#     encoded_data = encode_typed_data(structured_data)
#     signed_message = account.sign_message(encoded_data)
    
#     # Extract signature components
#     signature = {
#         "v": signed_message.v,
#         "r": signed_message.r.hex(),
#         "s": signed_message.s.hex()
#     }
    
#     return {
#         "signature": signature,
#         "deadline": usdc_permit_deadline
#     }