from datetime import datetime
from web3 import Web3
import os
import urllib.parse
from dotenv import load_dotenv

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
]

# Initialize contract
CONTRACT = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
ACCOUNT = w3.eth.account.from_key(PRIVATE_KEY)

def generate_twitter_intent_url(text):
    encoded_text = urllib.parse.quote(text)
    return f"https://twitter.com/intent/tweet?text={encoded_text}"

async def call_langraph_agent(agent, message_text=None, reply_text=None):
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
    pool_id_hex = None
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

        if receipt['logs']:
            data = receipt['logs'][0]['data']
            pool_id = int.from_bytes(data[:32], byteorder='big')
            pool_id_hex = hex(pool_id)

            print(f"Pool created with ID: {pool_id_hex}")
        else:
            print("No logs found in receipt")

        return pool_id_hex

    except Exception as e:
        raise Exception(f"Error creating pool: {str(e)}")

def generate_tweet_content(pool_id_hex, frontend_url_prefix):
    if pool_id_hex:
        full_url = f"{frontend_url_prefix}{pool_id_hex}"
        tweet_text = f"New pool created! Check it out: {full_url}"
        return tweet_text
    else:
        return None 