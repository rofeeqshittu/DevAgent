import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import subprocess
import shutil

import agent_manager
from safety_hooks import pending_approvals

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent_manager.set_telegram_context(context.bot, update.effective_chat.id)
    await update.message.reply_text("Hello! I am your autonomous DevAgent. I live on your VPS.\n\nUse /help to see what I can do, or just send me a task to begin.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *DevAgent Commands*\n\n"
        "I am an autonomous AI connected directly to your VPS terminal. You can converse with me naturally.\n\n"
        "/start - Wake me up\n"
        "/help - Show this message\n"
        "/status - Check VPS server health (CPU, RAM, Disk)\n\n"
        "*Examples of what you can ask me:*\n"
        "- \"Clone my repo to /opt/my-app\"\n"
        "- \"Find the error in my python script\"\n"
        "- \"Run git pull in the StreamVault folder\"\n\n"
        "If I need to run a critical command or edit a file, I will send you a prompt with Approve/Deny buttons."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Get disk usage
        total, used, free = shutil.disk_usage("/")
        disk_percent = (used / total) * 100
        
        # Get RAM usage using free -m
        ram_output = subprocess.check_output(["free", "-m"]).decode('utf-8').splitlines()[1].split()
        ram_total, ram_used = int(ram_output[1]), int(ram_output[2])
        ram_percent = (ram_used / ram_total) * 100
        
        status_text = (
            "📊 *VPS Server Status*\n\n"
            f"💽 *Disk:* {used // (2**30)}GB / {total // (2**30)}GB ({disk_percent:.1f}%)\n"
            f"🧠 *RAM:* {ram_used}MB / {ram_total}MB ({ram_percent:.1f}%)\n"
            f"✅ *DevAgent Service:* Active & Listening"
        )
        await update.message.reply_text(status_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching status: {e}")

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
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("Starting DevAgent Telegram Bot...")
    app.run_polling()

if __name__ == '__main__':
    main()
