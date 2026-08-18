"""
Manages persistent conversation history for DevAgent.
Saves to chat_history.json so it survives restarts.
Auto-trims to last MAX_TURNS exchanges to stay within token limits.
"""
import json
import os

HISTORY_FILE = "chat_history.json"
MAX_TURNS = 15  # keep last 15 user+bot pairs in context

def load_history() -> list[dict]:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(history: list[dict]):
    # Trim to MAX_TURNS before saving
    if len(history) > MAX_TURNS * 2:
        history = history[-(MAX_TURNS * 2):]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def add_turn(user_msg: str, bot_reply: str):
    history = load_history()
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": bot_reply})
    save_history(history)

def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

def build_context_message(user_text: str) -> str:
    """
    Prepend recent conversation history to the current user message
    so the agent has full context on every request.
    """
    history = load_history()
    if not history:
        return user_text

    lines = ["[Conversation history — use this context to answer the current message]"]
    for msg in history:
        role = "Rofeeq" if msg["role"] == "user" else "DevAgent"
        # Truncate very long messages in history to save tokens
        content = msg["content"]
        if len(content) > 400:
            content = content[:400] + "...[truncated]"
        lines.append(f"{role}: {content}")

    lines.append("")
    lines.append(f"[Current message from Rofeeq]\n{user_text}")
    return "\n".join(lines)
