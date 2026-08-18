import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import subprocess
import shutil

import agent_manager
from safety_hooks import pending_approvals
from chat_history import clear_history
from reminders import add_reminder, remove_reminder, get_pending_reminders

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Nigeria is UTC+1. All user-facing times will be shown in WAT.
USER_TZ_OFFSET = timedelta(hours=1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent_manager.set_telegram_context(context.bot, update.effective_chat.id)
    await update.message.reply_text("Hello! I am your autonomous DevAgent. I live on your VPS.\n\nUse /help to see what I can do, or just send me a task to begin.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *DevAgent Commands*\n\n"
        "I am an autonomous AI connected directly to your VPS terminal. You can converse with me naturally.\n\n"
        "/start - Wake me up\n"
        "/help - Show this message\n"
        "/status - Check VPS server health (CPU, RAM, Disk)\n"
        "/restart - Pull latest code from GitHub and restart the bot\n"
        "/clear - Wipe conversation memory and start fresh\n"
        "/remind <time> <message> - Set a reminder\n"
        "/reminders - List all pending reminders\n"
        "/cancel\\_reminder <ID> - Cancel a reminder by ID\n\n"
        "*Reminder examples:*\n"
        "- /remind tomorrow at 5pm call John\n"
        "- /remind in 2 hours check server logs\n"
        "- /remind next Monday 9am standup meeting\n\n"
        "*Task examples:*\n"
        "- \"Research the best Python web frameworks\"\n"
        "- \"Find the error in my python script\"\n\n"
        "If I need to run a critical command or edit a file, I will send you Approve/Deny buttons."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Pulling latest code and restarting... I'll go quiet for a few seconds.")
    try:
        pull_result = subprocess.check_output(
            ["git", "pull"],
            cwd="/opt/DevAgent",
            stderr=subprocess.STDOUT
        ).decode("utf-8").strip()

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ *Git pull done:*\n```\n{pull_result[:500]}\n```\nRestarting now...",
            parse_mode="Markdown"
        )
    except subprocess.CalledProcessError as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ Git pull failed:\n```\n{e.output.decode()[:400]}\n```\nRestarting anyway...",
            parse_mode="Markdown"
        )

    subprocess.Popen(
        ["bash", "-c", "sleep 2 && nohup python3 /opt/DevAgent/bot.py >> /opt/DevAgent/devagent.log 2>&1 &"],
        cwd="/opt/DevAgent"
    )
    await asyncio.sleep(1)
    import signal
    os.kill(os.getpid(), signal.SIGTERM)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_history()
    import agent_manager as am
    if os.path.exists(am.CONV_ID_FILE):
        os.remove(am.CONV_ID_FILE)
    await update.message.reply_text(
        "🧹 *Memory cleared.* I have no recollection of any previous conversation. Start fresh!",
        parse_mode="Markdown"
    )

# ─── REMINDER FIRE CALLBACK ───────────────────────────────────────────────────
async def fire_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data
    try:
        await context.bot.send_message(
            chat_id=data["chat_id"],
            text=f"⏰ *Reminder:* {data['message']}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Failed to fire reminder: {e}")
    finally:
        # Remove from persistent store
        remove_reminder(data["id"])

# ─── REMIND COMMAND ───────────────────────────────────────────────────────────
async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/remind <time> <message>`\n\n"
            "Examples:\n"
            "• `/remind tomorrow at 5pm call John`\n"
            "• `/remind in 2 hours check server`\n"
            "• `/remind next Monday 9am standup`",
            parse_mode="Markdown"
        )
        return

    try:
        import dateparser
    except ImportError:
        await update.message.reply_text("❌ dateparser not installed. Run: `pip install dateparser`", parse_mode="Markdown")
        return

    full_text = " ".join(context.args)

    # Normalize: add space between digits and letters ("3minutes" → "3 minutes", "2hrs" → "2 hrs")
    import re
    full_text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', full_text)
    full_text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', full_text)

    words = full_text.split()

    # Try parsing progressively longer prefixes (longest first) to find the time part
    parsed_time = None
    message_start = 1  # at minimum, 1 word is the time

    for i in range(len(words), 0, -1):
        candidate = " ".join(words[:i])
        parsed = dateparser.parse(
            candidate,
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": True,
                "TIMEZONE": "Africa/Lagos",
                "TO_TIMEZONE": "UTC",
            }
        )
        if parsed and parsed > datetime.now(timezone.utc):
            parsed_time = parsed
            message_start = i
            break

    if not parsed_time:
        await update.message.reply_text(
            "❌ Couldn't understand the time. Try:\n"
            "`/remind tomorrow at 5pm call John`\n"
            "`/remind in 30 minutes check logs`",
            parse_mode="Markdown"
        )
        return

    reminder_msg = " ".join(words[message_start:]).strip()
    if not reminder_msg:
        await update.message.reply_text("❌ Please add a message after the time.\nExample: `/remind tomorrow 5pm call John`", parse_mode="Markdown")
        return

    delay_seconds = (parsed_time - datetime.now(timezone.utc)).total_seconds()

    # Save and schedule
    reminder_id = add_reminder(update.effective_chat.id, parsed_time, reminder_msg)
    context.job_queue.run_once(
        fire_reminder,
        when=delay_seconds,
        data={"chat_id": update.effective_chat.id, "message": reminder_msg, "id": reminder_id},
        name=reminder_id
    )

    # Show time in WAT (UTC+1)
    local_time = parsed_time + USER_TZ_OFFSET
    await update.message.reply_text(
        f"✅ *Reminder set!*\n"
        f"🆔 ID: `{reminder_id}`\n"
        f"📅 {local_time.strftime('%a, %b %d at %I:%M %p')} (WAT)\n"
        f"💬 {reminder_msg}",
        parse_mode="Markdown"
    )

# ─── LIST REMINDERS ───────────────────────────────────────────────────────────
async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = get_pending_reminders()
    chat_id = update.effective_chat.id
    mine = [r for r in pending if r["chat_id"] == chat_id]

    if not mine:
        await update.message.reply_text("📭 You have no pending reminders.")
        return

    lines = ["⏰ *Pending Reminders:*\n"]
    for r in mine:
        fire_time = datetime.fromisoformat(r["fire_time"])
        if fire_time.tzinfo is None:
            fire_time = fire_time.replace(tzinfo=timezone.utc)
        local_time = fire_time + USER_TZ_OFFSET
        lines.append(
            f"• `{r['id']}` — {local_time.strftime('%a %b %d, %I:%M %p')} WAT\n"
            f"  💬 {r['message']}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ─── CANCEL REMINDER ──────────────────────────────────────────────────────────
async def cancel_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/cancel_reminder <ID>`\nGet IDs from /reminders", parse_mode="Markdown")
        return

    reminder_id = context.args[0].upper()

    # Cancel the JobQueue job
    current_jobs = context.job_queue.get_jobs_by_name(reminder_id)
    for job in current_jobs:
        job.schedule_removal()

    # Remove from disk
    removed = remove_reminder(reminder_id)
    if removed or current_jobs:
        await update.message.reply_text(f"✅ Reminder `{reminder_id}` cancelled.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ No reminder found with ID `{reminder_id}`.", parse_mode="Markdown")

# ─── STATUS ───────────────────────────────────────────────────────────────────
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        total, used, free = shutil.disk_usage("/")
        disk_percent = (used / total) * 100
        ram_output = subprocess.check_output(["free", "-m"]).decode('utf-8').splitlines()[1].split()
        ram_total, ram_used = int(ram_output[1]), int(ram_output[2])
        ram_percent = (ram_used / ram_total) * 100

        pending = get_pending_reminders()
        reminder_count = len([r for r in pending if True])  # all of them for this user

        status_text = (
            "📊 *VPS Server Status*\n\n"
            f"💽 *Disk:* {used // (2**30)}GB / {total // (2**30)}GB ({disk_percent:.1f}%)\n"
            f"🧠 *RAM:* {ram_used}MB / {ram_total}MB ({ram_percent:.1f}%)\n"
            f"⏰ *Pending Reminders:* {reminder_count}\n"
            f"✅ *DevAgent Service:* Active & Listening"
        )
        await update.message.reply_text(status_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching status: {e}")

# ─── MESSAGES ─────────────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent_manager.set_telegram_context(context.bot, update.effective_chat.id)
    user_text = update.message.text
    status_msg = await update.message.reply_text("🤔 Thinking...")

    try:
        final_text = await agent_manager.chat_with_agent(user_text)
        if len(final_text) > 4000:
            final_text = final_text[:4000] + "\n\n...[truncated]"
        await status_msg.edit_text(final_text, parse_mode="Markdown")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    action, call_id = data.split("_", 1)

    if call_id in pending_approvals:
        future = pending_approvals[call_id]
        if not future.done():
            future.set_result(action == "approve")

        if action == "approve":
            await query.edit_message_text("✅ *Action Approved by User*", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ *Action Denied by User*", parse_mode="Markdown")

# ─── STARTUP: RELOAD REMINDERS FROM DISK ─────────────────────────────────────
async def reload_reminders_on_startup(app):
    """Re-schedule any reminders that were saved before the last restart."""
    pending = get_pending_reminders()
    now = datetime.now(timezone.utc)
    reloaded = 0
    for r in pending:
        fire_time = datetime.fromisoformat(r["fire_time"])
        if fire_time.tzinfo is None:
            fire_time = fire_time.replace(tzinfo=timezone.utc)
        delay = (fire_time - now).total_seconds()
        if delay > 0:
            app.job_queue.run_once(
                fire_reminder,
                when=delay,
                data={"chat_id": r["chat_id"], "message": r["message"], "id": r["id"]},
                name=r["id"]
            )
            reloaded += 1
    if reloaded:
        logging.info(f"Reloaded {reloaded} pending reminder(s) from disk.")

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is missing in .env")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("cancel_reminder", cancel_reminder_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message, block=False))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Reload saved reminders after startup
    app.job_queue.run_once(
        lambda ctx: asyncio.ensure_future(reload_reminders_on_startup(app)),
        when=2  # 2 seconds after start
    )

    print("Starting DevAgent Telegram Bot...")
    app.run_polling()

if __name__ == '__main__':
    main()
