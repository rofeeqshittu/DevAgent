import os
import asyncio
from google.antigravity import Agent, LocalAgentConfig
from safety_hooks import pre_tool_call_decide_hook

_bot = None
_chat_id = None
CONV_ID_FILE = "conversation_id.txt"
SAVE_DIR = "agent_state"

os.makedirs(SAVE_DIR, exist_ok=True)

def set_telegram_context(bot, chat_id):
    global _bot, _chat_id
    _bot = bot
    _chat_id = chat_id

def get_telegram_context():
    return _bot, _chat_id

def get_conversation_id():
    if os.path.exists(CONV_ID_FILE):
        with open(CONV_ID_FILE, "r") as f:
            return f.read().strip()
    return None

def save_conversation_id(cid):
    with open(CONV_ID_FILE, "w") as f:
        f.write(cid)

async def chat_with_agent(text):
    cid = get_conversation_id()
    
    config = LocalAgentConfig(
        conversation_id=cid,
        save_dir=SAVE_DIR,
        hooks=[pre_tool_call_decide_hook],
        system_instruction=(
            "You are an autonomous DevAgent running on a Linux VPS. "
            "You can execute commands, edit files, and build software. "
            "Always be highly technical, concise, and professional. "
            "You have full access to tools like run_command, write_to_file, etc. "
            "If the user asks you to modify a project, use your tools to navigate the filesystem, "
            "edit the files, and run terminal commands to verify."
        )
    )
    
    async with Agent(config) as agent:
        if not cid:
            save_conversation_id(agent.conversation_id)
        response = await agent.chat(text)
        return await response.text()
