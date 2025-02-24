from datetime import datetime, timedelta
from web3 import Web3
import os
import urllib.parse
from dotenv import load_dotenv
from twitter_post import post_tweet_using_redis_token

# Load environment variables
load_dotenv()

# Environment variables
WEB3_NODE_URL = os.getenv('WEB3_NODE_URL')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
GAS_LIMIT = int(os.getenv('GAS_LIMIT', 3000000))

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(WEB3_NODE_URL))

# Example contract ABI - modify according to your contract
CONTRACT_ABI = [
    {
        "inputs": [{
            "components": [
                {"internalType": "string", "name": "question", "type": "string"},
                {"internalType": "string[2]", "name": "options", "type": "string[2]"},
                {"internalType": "uint40", "name": "betsCloseAt", "type": "uint40"},
                {"internalType": "uint40", "name": "decisionDate", "type": "uint40"},
                {"internalType": "string", "name": "imageUrl", "type": "string"},
                {"internalType": "string", "name": "category", "type": "string"},
                {"internalType": "string", "name": "creatorName", "type": "string"},
                {"internalType": "string", "name": "creatorId", "type": "string"},
                {"internalType": "string", "name": "closureCriteria", "type": "string"},
                {"internalType": "string", "name": "closureInstructions", "type": "string"}
            ],
            "internalType": "struct PoolCreationParams",
            "name": "params",
            "type": "tuple"
        }],
        "name": "createPool",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "poolId", "type": "uint256"},
            {"internalType": "string", "name": "twitterPostId", "type": "string"}
        ],
        "name": "setTwitterPostId",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# Initialize contract
CONTRACT = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
ACCOUNT = w3.eth.account.from_key(PRIVATE_KEY)

def generate_twitter_intent_url(text):
    encoded_text = urllib.parse.quote(text)
    return f"https://twitter.com/intent/tweet?text={encoded_text}"

async def call_langgraph_agent(agent, message_text=None, reply_text=None):
    message = {
        "role": "user", 
        "content": "Generate a betting pool for me."
    }
    if message_text:
        message["content"] += f"\n<text>{message_text}</text>"
    if reply_text:
        message["content"] += f"\n<reply_text>{reply_text}</reply_text>"

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
        tx = CONTRACT.functions.createPool((
            pool_data['question'],
            pool_data['options'],
            pool_data['betsCloseAt'],
            pool_data['decisionDate'],
            pool_data['imageUrl'],
            pool_data['category'],
            pool_data['creatorName'],
            pool_data['creatorId'],
            pool_data['closureCriteria'],
            pool_data['closureInstructions']
        )).build_transaction({
            'from': ACCOUNT.address,
            'nonce': w3.eth.get_transaction_count(ACCOUNT.address),
            'gas': GAS_LIMIT,
            'gasPrice': w3.eth.gas_price
        })
        
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Pool successfully created. Transaction hash: {tx_hash.hex()}, Transaction receipt: {receipt}")

        if receipt['logs']:
            data = receipt['logs'][0]['data']
            pool_id = int.from_bytes(data[:32], byteorder='big')

            print(f"Pool created with ID: {pool_id}")
        else:
            print("No logs found in receipt")

        return pool_id

    except Exception as e:
        raise Exception(f"Error creating pool: {str(e)}")

def generate_tweet_content(pool_id, pool_data, frontend_url_prefix):
    if pool_id is not None:
        pool_id_hex = hex(pool_id)
        full_url = f"{frontend_url_prefix}{pool_id_hex}"
        
        # Format the tweet using the passed pool_data
        tweet_text = (
            f"🎲 New Prediction Pool!\n\n"
            f"Q: {pool_data['question']}\n"
            f"A) {pool_data['options'][0]}\n"
            f"B) {pool_data['options'][1]}\n\n"
            f"Place your bets: {full_url}"
        )
        
        # Post the tweet using the existing method
        tweet_id = post_tweet_using_redis_token(tweet_text)
        if tweet_id is None:
            return None

        # Set the Twitter post ID in the contract
        set_twitter_post_id(pool_id, tweet_id)
        
        return tweet_text
    else:
        return None

def create_pool_data(langgraph_agent_response, creator_name, creator_id):
    betting_pool_data = langgraph_agent_response['betting_pool_idea']
    decision_date = datetime.strptime(betting_pool_data['closure_date'], '%Y-%m-%dT%H:%M:%S')

    # Set bets_close_at to one day before the decision_date
    bets_close_at = datetime.now() + timedelta(days=1)
    if bets_close_at > decision_date:
        bets_close_at = decision_date - timedelta(seconds=5)

    pool_data = {
        'question': betting_pool_data['betting_pool_idea'],
        'options': [betting_pool_data['options'][0], betting_pool_data['options'][1]],
        'betsCloseAt': int(bets_close_at.timestamp()),
        'decisionDate': int(decision_date.timestamp()),
        'imageUrl': langgraph_agent_response['image_results'][0]['url'] if langgraph_agent_response['image_results'] else "",
        'category': betting_pool_data['category'],
        'creatorName': creator_name,
        'creatorId': creator_id,
        'closureCriteria': betting_pool_data['closure_summary'],
        'closureInstructions': betting_pool_data['closure_instructions']
    }

    print(f"Pool data: {pool_data}")
    
    return pool_data 

def set_twitter_post_id(pool_id, tweet_id):
    try:
        # Build the transaction
        tx = CONTRACT.functions.setTwitterPostId(
            pool_id,
            tweet_id
        ).build_transaction({
            'from': ACCOUNT.address,
            'nonce': w3.eth.get_transaction_count(ACCOUNT.address),
            'gas': GAS_LIMIT,
            'gasPrice': w3.eth.gas_price
        })

        # Sign the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)

        # Send the transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for the transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        print(f"Setting twitter transaction successful with hash: {tx_hash.hex()}, receipt: {receipt}")
        return receipt
    except Exception as e:
        raise Exception(f"Error setting Twitter post ID: {str(e)}")
