import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
# from web3 import Web3
from dotenv import load_dotenv
import urllib.parse

# Load environment variables
load_dotenv()

# Environment variables
HALLUCIBETRBOT_TOKEN = os.getenv('HALLUCIBETRBOT_TOKEN')
ETHEREUM_NODE_URL = os.getenv('ETHEREUM_NODE_URL')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
URL_PREFIX = os.getenv('URL_PREFIX')  
LANGRAPH_ENDPOINT = os.getenv('LANGRAPH_ENDPOINT')  # Add this for the Langraph endpoint

# Command name variable
GENERATE_BETTING_POOL_COMMAND = "generate_betting_pool_idea"

# Initialize Web3
# w3 = Web3(Web3.HTTPProvider(ETHEREUM_NODE_URL))

# Example contract ABI - modify according to your contract
CONTRACT_ABI = [
    {
        "inputs": [],
        "name": "getAddress",
        "outputs": [{"type": "address", "name": ""}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Initialize contract
# CONTRACT = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

# Define states for conversation
QUESTION, OPTIONS, BETS_CLOSE_AT, DECISION_DATE, IMAGE_URL, CATEGORY, CREATOR_NAME, CREATOR_ID, CLOSURE_CRITERIA, CLOSURE_INSTRUCTIONS = range(10)

def generate_twitter_intent_url(text):
    # Encode the tweet text for URL
    encoded_text = urllib.parse.quote(text)
    return f"https://twitter.com/intent/tweet?text={encoded_text}"

def call_langraph_agent(additional_text):
    # Prepare data to send to Langraph
    data = {'additional_text': additional_text} if additional_text else {}

    # Call the Langraph endpoint
    try:
        response = requests.post(LANGRAPH_ENDPOINT, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error fetching data from Langraph: {str(e)}")

def create_market(pool_data):
    try:
        # Call the createPool function on the contract
        tx = CONTRACT.functions.createPool(
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
        ).transact({'from': w3.eth.default_account})

        return tx.hex()
    except Exception as e:
        raise Exception(f"Error creating market: {str(e)}")

async def share_market(update: Update, context: ContextTypes.DEFAULT_TYPE, tx_hash: str):
    try:
        # Generate the full URL using the transaction hash
        full_url = f"{URL_PREFIX}{tx_hash}"
        
        # Create tweet text
        tweet_text = f"New market created! Check it out: {full_url}"
        
        # Generate Twitter intent URL
        twitter_url = generate_twitter_intent_url(tweet_text)
        
        # Create inline keyboard with the Twitter link
        keyboard = [[InlineKeyboardButton("Share on Twitter", url=twitter_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send message with button
        await update.message.reply_text(
            f"Market created successfully!\nURL: {full_url}\n\nClick below to share on Twitter:",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await update.message.reply_text(f"Error occurred: {str(e)}")

async def create_pool_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generating betting idea...")
    
    # Extract additional message text
    user_prompt = update.message.text.replace(f'/{GENERATE_BETTING_POOL_COMMAND}', '').strip()
    
    try:
        # Call the Langraph agent
        # pool_data = call_langraph_agent(user_prompt)
        
        # Create the market and get the transaction hash
        # tx_hash = create_market(pool_data)
        tx_hash = "0x1234567890123456789012345678901234567890"
        # Share the market using the transaction hash
        await share_market(update, context, tx_hash)

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