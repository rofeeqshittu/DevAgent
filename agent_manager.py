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
            cid = f.read().strip()
            if cid:
                return cid
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
            "You have full access to tools like run_command, list_dir, view_file, and write_to_file "
            "which allow you to navigate folders, view code diffs, run git commits, and execute scripts.\n\n"
            "CRITICAL DIRECTIVES:\n"
            "1. NO EMOTION, JUST FACTS: Provide direct, concise, and highly technical responses. Avoid preamble and conversational filler.\n"
            "2. BOIL THE OCEAN: The standard isn't 'good enough' - it's 'holy shit, that's done'. Never offer to 'table this for later' when a permanent solve is within reach. Never leave dangling threads.\n"
            "3. READ GEMINI.md: Before starting any major task, you MUST use view_file to read the GEMINI.md file in the project root to understand the core rules of engagement.\n"
            "4. NEVER guess. If you can't walk the failure modes out loud, you are guessing. Write tests, verify functionality via run_command, and ship the complete thing."
        )
    )
    
    async with Agent(config) as agent:
        # Add robust retry logic for 503 Server Overload errors from Google
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await agent.chat(text)
                if not cid and agent.conversation_id:
                    save_conversation_id(str(agent.conversation_id))
                return await response.text()
            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg and attempt < max_retries - 1:
                    await asyncio.sleep(2 * (attempt + 1)) # Exponential backoff: 2s, 4s
                    continue
                raise e
