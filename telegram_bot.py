from datetime import datetime, timedelta
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from web3 import Web3
from dotenv import load_dotenv
import urllib.parse

from betting_pool_generator import betting_pool_idea_generator_agent

# Load environment variables
load_dotenv()

# Environment variables
HALLUCIBETRBOT_TOKEN = os.getenv('HALLUCIBETRBOT_TOKEN')
WEB3_NODE_URL = os.getenv('WEB3_NODE_URL')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FRONTEND_URL_PREFIX = os.getenv('FRONTEND_URL_PREFIX')  

GAS_LIMIT = os.getenv('GAS_LIMIT', 3000000)
GENERATE_BETTING_POOL_COMMAND = "generate_betting_pool_idea"

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

    # PoolCreated event
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "poolId", "type": "uint256"},
            {"indexed": True, "internalType": "string", "name": "creatorId", "type": "string"},
            {
                "components": [
                    {"internalType": "string", "name": "question", "type": "string"},
                    {"internalType": "string[2]", "name": "options", "type": "string[2]"},
                    {"internalType": "uint40", "name": "betsCloseAt", "type": "uint40"},
                    {"internalType": "uint40", "name": "decisionDate", "type": "uint40"},
                    {"internalType": "string", "name": "imageUrl", "type": "string"},
                    {"internalType": "string", "name": "category", "type": "string"},
                    {"internalType": "string", "name": "creatorName", "type": "string"},
                    {"internalType": "string", "name": "closureCriteria", "type": "string"},
                    {"internalType": "string", "name": "closureInstructions", "type": "string"}
                ],
                "internalType": "struct PoolCreatedEvent",
                "name": "poolDetails",
                "type": "tuple"
            }
        ],
        "name": "PoolCreated",
        "type": "event"
    }
]

# Initialize contract
CONTRACT = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

ACCOUNT = w3.eth.account.from_key(PRIVATE_KEY)
# w3.eth.default_account = ACCOUNT


def generate_twitter_intent_url(text):
    # Encode the tweet text for URL
    encoded_text = urllib.parse.quote(text)
    return f"https://twitter.com/intent/tweet?text={encoded_text}"

async def call_langgraph_agent(user_prompt):
    # Initialize the Langraph client and remote graph
    betting_pool_idea_generator_agent
    
    message = {"role": "user", "content": "Generate a betting pool for me"}
    if user_prompt:
        message["content"] = user_prompt

    # Call the Langraph endpoint asynchronously
    try:
        # response_data = []
        # async for chunk in remote_graph.astream(
        #     {
        #         "messages": messages,
        #         "prefer_fast_response": True,
        #     }
        # ):
        #     response_data.append(chunk)
        #     print(chunk)  # You can remove this print statement if not needed

        agent_response = betting_pool_idea_generator_agent.invoke(
            {
                "messages": [message],
                "prefer_fast_response": True,
            }   
        )

        return agent_response
    except Exception as e:
        raise Exception(f"Error fetching data from Langraph: {str(e)}")

async def share_pool(update: Update, context: ContextTypes.DEFAULT_TYPE, pool_id_hex: str):
    try:
        # Generate the full URL using the transaction hash
        full_url = f"{FRONTEND_URL_PREFIX}{pool_id_hex}"
        
        # Create tweet text
        tweet_text = f"New pool created! Check it out: {full_url}"
        
        # Generate Twitter intent URL
        twitter_url = generate_twitter_intent_url(tweet_text)
        
        # Create inline keyboard with the Twitter link
        keyboard = [[InlineKeyboardButton("Share on Twitter", url=twitter_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send message with button
        await update.message.reply_text(
            f"Market pool created successfully!\nURL: {full_url}\n\nClick below to share on Twitter:",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await update.message.reply_text(f"Error occurred: {str(e)}")

def create_pool(pool_data):
    try:
        # Call the createPool function on the contract
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
        # )).transact({'from': ACCOUNT.address})
        )).build_transaction({
            'from': ACCOUNT.address,  # Use the actual address from account
            'nonce': w3.eth.get_transaction_count(ACCOUNT.address),
            'gas': GAS_LIMIT,
            'gasPrice': w3.eth.gas_price
        })
        
        # Sign and send the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        print(f"signed_tx: {signed_tx}")
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"tx_hash: {tx_hash}")

        # Wait for transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"receipt: {receipt}")

        # pool_created_events = CONTRACT.events.PoolCreated().process_receipt(receipt)
        # print(f"pool_created_events: {pool_created_events}")

        # pool_created_event = pool_created_events[0]
        # print(f"pool_created_event: {pool_created_event}")
        # pool_id = pool_created_event['args']['poolId']  # or pool_created_event.args.poolId
        # print(f"pool_id: {pool_id}")

        # The logs contain the event data
        print(f"Receipt logs: {receipt['logs']}")
        
        # The first log should contain our event
        # poolId should be in topics[1] since it's the first indexed parameter
        data = receipt['logs'][0]['data']
        pool_id = int.from_bytes(data[:32], byteorder='big')
        print(f"pool_id: {pool_id}")

        # Convert pool_id to hexadecimal string
        pool_id_hex = hex(pool_id)
        print(f"pool_id_hex: {pool_id_hex}")

        return pool_id_hex

    except Exception as e:
        raise Exception(f"Error creating pool: {str(e)}")

async def create_pool_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generating betting idea...")
    
    # Extract additional message text
    user_prompt = update.message.text.replace(f'/{GENERATE_BETTING_POOL_COMMAND}', '').strip()
    creator_name = update.message.from_user.username
    creator_id = str(update.message.from_user.id)
    bets_close_at = datetime.now() + timedelta(days=1)
    
    try:
        # Call the Langraph agent
        langgraph_agent_response = await call_langgraph_agent(user_prompt)
        print(f"langgraph_agent_response: {langgraph_agent_response}")

        betting_pool_data = langgraph_agent_response['betting_pool_idea']
        decision_date = datetime.strptime(betting_pool_data['closure_date'], '%Y-%m-%dT%H:%M:%S')

        pool_data = {
            'question': betting_pool_data['betting_pool_idea'],
            # Convert to binary choice
            'options': [
                betting_pool_data['options'][0],
                betting_pool_data['options'][1],
            ],
            'betsCloseAt': int(bets_close_at.timestamp()),
            'decisionDate': int(decision_date.timestamp()),
            'imageUrl': langgraph_agent_response['image_results'][0]['url'] if langgraph_agent_response['image_results'] else "",
            'category': betting_pool_data['category'],
            'creatorName': creator_name,
            'creatorId': creator_id,
            'closureCriteria': betting_pool_data['closure_summary'],
            'closureInstructions': betting_pool_data['closure_instructions']
        }
        
        print(f"pool_data: {pool_data}")
        # Create the pool and get the transaction hash
        pool_id_hex = create_pool(pool_data)

        # Share the pool using the transaction hash
        await share_pool(update, context, pool_id_hex)

    except Exception as e:
        await update.message.reply_text(str(e))

def main():
    # Initialize the Telegram bot
    application = Application.builder().token(HALLUCIBETRBOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler(GENERATE_BETTING_POOL_COMMAND, create_pool_start))
    
    # Start the bot
    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()