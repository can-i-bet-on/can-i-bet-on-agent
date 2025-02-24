from datetime import datetime, timedelta
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
from betting_pool_core import call_langraph_agent, create_pool, generate_tweet_content, generate_twitter_intent_url, create_pool_data
from betting_pool_generator import betting_pool_idea_generator_agent

# Load environment variables
load_dotenv()

# Environment variables
HALLUCIBETRBOT_TOKEN = os.getenv('HALLUCIBETRBOT_TOKEN')
FRONTEND_URL_PREFIX = os.getenv('FRONTEND_URL_PREFIX')  
LOCAL_DEV_IDENTIFIER=os.getenv('LOCAL_DEV_IDENTIFIER', "")
GENERATE_BETTING_POOL_COMMAND = f"generate_betting_pool_idea{LOCAL_DEV_IDENTIFIER}"

async def share_pool(update: Update, context: ContextTypes.DEFAULT_TYPE, pool_id: str, pool_data: dict):
    try:
        tweet_text = generate_tweet_content(pool_id, pool_data, FRONTEND_URL_PREFIX)
        
        if tweet_text:
            twitter_url = generate_twitter_intent_url(tweet_text)
            keyboard = [[InlineKeyboardButton("Share on Twitter", url=twitter_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"Market pool created successfully!\n{tweet_text}\n\nClick below to share on Twitter:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("Error creating pool. Please try again.")
    except Exception as e:
        await update.message.reply_text(f"Error occurred: {str(e)}")

async def create_pool_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generating betting idea...")
    message_text = update.message.text.replace(f'/{GENERATE_BETTING_POOL_COMMAND}', '').strip()
    reply_text = update.message.reply_to_message.text if update.message.reply_to_message else None
    creator_name = update.message.from_user.username
    creator_id = str(update.message.from_user.id)
    
    try:
        langgraph_agent_response = await call_langraph_agent(betting_pool_idea_generator_agent, message_text, reply_text)
        
        # Use the new function to create pool_data
        pool_data = create_pool_data(langgraph_agent_response, creator_name, creator_id)
        
        pool_id = create_pool(pool_data)
        await share_pool(update, context, pool_id, pool_data)

    except Exception as e:
        await update.message.reply_text(str(e))

def main():
    application = Application.builder().token(HALLUCIBETRBOT_TOKEN).build()
    application.add_handler(CommandHandler(GENERATE_BETTING_POOL_COMMAND, create_pool_start))
    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
