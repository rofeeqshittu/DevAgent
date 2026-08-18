"""
Reminder manager for DevAgent.
Persists reminders to reminders.json so they survive restarts.
"""
import json
import os
import uuid
from datetime import datetime, timezone

REMINDERS_FILE = "reminders.json"

def load_reminders() -> list[dict]:
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_reminders(reminders: list[dict]):
    with open(REMINDERS_FILE, "w") as f:
        json.dump(reminders, f, indent=2)

def add_reminder(chat_id: int, fire_time: datetime, message: str) -> str:
    reminders = load_reminders()
    reminder_id = str(uuid.uuid4())[:6].upper()
    reminders.append({
        "id": reminder_id,
        "chat_id": chat_id,
        "fire_time": fire_time.isoformat(),
        "message": message
    })
    save_reminders(reminders)
    return reminder_id

def remove_reminder(reminder_id: str) -> bool:
    reminders = load_reminders()
    new_list = [r for r in reminders if r["id"] != reminder_id.upper()]
    if len(new_list) == len(reminders):
        return False
    save_reminders(new_list)
    return True

def get_pending_reminders() -> list[dict]:
    """Return only reminders that haven't fired yet."""
    now = datetime.now(timezone.utc)
    reminders = load_reminders()
    pending = []
    for r in reminders:
        fire_time = datetime.fromisoformat(r["fire_time"])
        # Make naive datetimes UTC-aware for comparison
        if fire_time.tzinfo is None:
            fire_time = fire_time.replace(tzinfo=timezone.utc)
        if fire_time > now:
            pending.append(r)
    # Overwrite file keeping only pending ones
    save_reminders(pending)
    return pending
