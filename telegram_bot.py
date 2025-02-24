from datetime import datetime, timedelta
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
from betting_pool_core import call_langraph_agent, create_pool, generate_tweet_content, generate_twitter_intent_url
from betting_pool_generator import betting_pool_idea_generator_agent

# Load environment variables
load_dotenv()

# Environment variables
HALLUCIBETRBOT_TOKEN = os.getenv('HALLUCIBETRBOT_TOKEN')
FRONTEND_URL_PREFIX = os.getenv('FRONTEND_URL_PREFIX')  
GENERATE_BETTING_POOL_COMMAND = "generate_betting_pool_idea"

async def share_pool(update: Update, context: ContextTypes.DEFAULT_TYPE, pool_id_hex: str):
    try:
        tweet_text = generate_tweet_content(pool_id_hex, FRONTEND_URL_PREFIX)
        
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
    bets_close_at = datetime.now() + timedelta(days=1)
    
    try:
        langgraph_agent_response = await call_langraph_agent(betting_pool_idea_generator_agent, message_text, reply_text)
        betting_pool_data = langgraph_agent_response['betting_pool_idea']
        decision_date = datetime.strptime(betting_pool_data['closure_date'], '%Y-%m-%dT%H:%M:%S')

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
        
        pool_id_hex = create_pool(pool_data)
        await share_pool(update, context, pool_id_hex)

    except Exception as e:
        await update.message.reply_text(str(e))

def main():
    application = Application.builder().token(HALLUCIBETRBOT_TOKEN).build()
    application.add_handler(CommandHandler(GENERATE_BETTING_POOL_COMMAND, create_pool_start))
    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()