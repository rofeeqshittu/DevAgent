import uuid
import asyncio
from google.antigravity import types
from google.antigravity.hooks import hooks
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

pending_approvals = {}

@hooks.pre_tool_call_decide
async def pre_tool_call_decide_hook(data: types.ToolCall) -> types.HookResult:
    # List of tools that require user permission
    dangerous_tools = ["run_command", "write_to_file", "multi_replace_file_content", "replace_file_content"]
    
    if data.name not in dangerous_tools:
        return types.HookResult(allow=True)
        
    import agent_manager
    bot, chat_id = agent_manager.get_telegram_context()
    
    if not bot or not chat_id:
        return types.HookResult(allow=True)
        
    call_id = str(uuid.uuid4())[:8]
    future = asyncio.Future()
    pending_approvals[call_id] = future
    
    # Format the tool call nicely for Telegram
    args_str = "\n".join([f"{k}: {v}" for k, v in data.args.items()])
    
    message_text = f"⚠️ *Permission Request*\n\nThe agent wants to execute a critical tool:\n`{data.name}`\n\n*Arguments:*\n```text\n{args_str}\n```\n\nApprove?"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{call_id}"),
            InlineKeyboardButton("❌ Deny", callback_data=f"deny_{call_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the approval message
    await bot.send_message(chat_id=chat_id, text=message_text, reply_markup=reply_markup, parse_mode="Markdown")
    
    # Pause agent execution until a button is clicked
    approved = await future
    del pending_approvals[call_id]
    
    if approved:
        return types.HookResult(allow=True)
    else:
        return types.HookResult(allow=False, error_message="The user explicitly denied permission for this action.")
