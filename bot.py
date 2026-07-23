import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

import agent_manager
from safety_hooks import pending_approvals

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent_manager.set_telegram_context(context.bot, update.effective_chat.id)
    await update.message.reply_text("Hello! I am your autonomous DevAgent. I live on your VPS. Send me a task to begin.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent_manager.set_telegram_context(context.bot, update.effective_chat.id)
    user_text = update.message.text
    
    # Let user know we are thinking
    status_msg = await update.message.reply_text("🤔 Thinking...")
    
    try:
        final_text = await agent_manager.chat_with_agent(user_text)
        
        # Telegram has a 4096 char limit, chunk it if needed
        if len(final_text) > 4000:
            final_text = final_text[:4000] + "\n\n...[truncated]"
            
        await status_msg.edit_text(final_text, parse_mode="Markdown")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    # data format: "approve_123" or "deny_123"
    action, call_id = data.split("_", 1)
    
    if call_id in pending_approvals:
        future = pending_approvals[call_id]
        if not future.done():
            future.set_result(action == "approve")
            
        if action == "approve":
            await query.edit_message_text(f"{query.message.text}\n\n✅ *Action Approved by User*", parse_mode="Markdown")
        else:
            await query.edit_message_text(f"{query.message.text}\n\n❌ *Action Denied by User*", parse_mode="Markdown")

def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is missing in .env")
        return
        
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("Starting DevAgent Telegram Bot...")
    app.run_polling()

if __name__ == '__main__':
    main()
