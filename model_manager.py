"""
Auto-fallback model manager for DevAgent.

When the active model hits a quota/billing error, this module:
  1. Marks it as exhausted in model_state.json
  2. Advances to the next model in the priority chain
  3. Returns the new model name so the caller can notify the user and retry

All models confirmed available on the user's QwenCloud free tier with 100% quota.
Ordered best capability → safe fallback.
"""
import os
import json
import logging

MODEL_CHAIN = [
    "qwen3.8-max",          # newest Qwen, best reasoning
    "qwen3.7-max",          # proven strong
    "qwen3-max",            # solid max tier
    "qwen3.7-plus",         # plus tier, fast
    "qwen-plus-latest",     # always-updated plus
    "qwen3.7-flash",        # fast flash fallback
    "qwen3.5-plus",         # older but reliable
    "qwen-plus",            # original, 88% remaining
    "deepseek-v4-pro-0813", # last resort, great for coding
]

# Strings in API error responses that indicate quota exhaustion
EXHAUSTION_SIGNALS = [
    "AllocationQuota.FreeTierOnly",
    "free quota has been exhausted",
    "quota has been exhausted",
    "InsufficientBalance",
    "Arrearage",
]

STATE_FILE = os.path.join(os.path.dirname(__file__), "model_state.json")


def _load() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_index": 0, "exhausted": []}


def _save(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_current_model() -> str:
    """Return whichever model is currently active."""
    # QWEN_MODEL env var overrides everything (manual override)
    if os.getenv("QWEN_MODEL"):
        return os.getenv("QWEN_MODEL")
    state = _load()
    idx = state.get("current_index", 0)
    return MODEL_CHAIN[min(idx, len(MODEL_CHAIN) - 1)]


def is_quota_error(error_text: str) -> bool:
    """Return True if the error string looks like a quota/billing exhaustion."""
    for signal in EXHAUSTION_SIGNALS:
        if signal.lower() in error_text.lower():
            return True
    return False


def mark_exhausted(model_name: str) -> str | None:
    """
    Mark a model as exhausted and advance to the next in the chain.
    Returns the new model name, or None if all models are exhausted.
    """
    # Skip if manual override is active
    if os.getenv("QWEN_MODEL"):
        return None

    state = _load()
    exhausted = state.get("exhausted", [])

    if model_name not in exhausted:
        exhausted.append(model_name)
    state["exhausted"] = exhausted

    # Find next non-exhausted model
    for i, m in enumerate(MODEL_CHAIN):
        if m not in exhausted:
            state["current_index"] = i
            _save(state)
            logging.warning(f"[ModelManager] {model_name} exhausted → switching to {m}")
            return m

    _save(state)
    logging.error("[ModelManager] ALL models exhausted.")
    return None


def reset():
    """Clear all exhausted state (call when quota is refilled)."""
    _save({"current_index": 0, "exhausted": []})
    logging.info("[ModelManager] Reset — starting fresh from qwen3.8-max")
