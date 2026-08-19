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
    # ── TIER 1: MAX (best reasoning & coding) ────────────────────────────────
    "qwen3.8-max",
    "qwen3.7-max",
    "qwen3.7-max-2026-06-08",
    "qwen3.7-max-2026-05-20",
    "qwen3.7-max-2026-05-17",
    "qwen3.7-max-preview",
    "qwen3-max",
    "qwen3-max-preview",
    "qwen3-max-2026-01-23",
    "qwen3-max-2025-09-23",
    "qwen3.6-max-preview",

    # ── TIER 2: PLUS (fast + capable) ────────────────────────────────────────
    "qwen3.7-plus",
    "qwen3.7-plus-2026-05-26",
    "qwen3.6-plus",
    "qwen3.6-plus-2026-04-02",
    "qwen3.5-plus",
    "qwen3.5-plus-2026-04-20",
    "qwen3.5-plus-2026-02-15",
    "qwen-plus-latest",
    "qwen-plus-2025-12-01",
    "qwen-plus-2025-09-11",
    "qwen-plus-2025-07-28",
    "qwen-plus-2025-07-14",
    "qwen-plus-2025-04-28",
    "qwen-plus",              # 88% remaining, expiring Sep 1

    # ── TIER 3: OPEN-WEIGHT LARGE (massive context, great quality) ───────────
    "qwen3.5-397b-a17b",      # 397B MoE — largest available
    "qwen3.5-122b-a10b",      # 122B MoE
    "qwen3.6-35b-a3b",
    "qwen3.5-35b-a3b",
    "qwen3.6-27b",
    "qwen3.5-27b",

    # ── TIER 4: DEEPSEEK (excellent for coding tasks) ─────────────────────────
    "deepseek-v4-pro-0813",   # latest DeepSeek, 86 days remaining
    "deepseek-v4-pro",
    "deepseek-v3.2",
    "deepseek-v4-flash",

    # ── TIER 5: GLM ──────────────────────────────────────────────────────────
    "glm-5.2",
    "glm-5.1",

    # ── TIER 6: FLASH (fastest, lower capability) ─────────────────────────────
    "qwen3.7-flash",
    "qwen3.7-flash-2026-07-15",
    "qwen3.6-flash",
    "qwen3.6-flash-2026-04-16",
    "qwen3.5-flash",
    "qwen3.5-flash-2026-02-23",

    # ── TIER 7: VISION-LANGUAGE (text-capable, last resort) ──────────────────
    "qwen3-vl-plus",
    "qwen3-vl-plus-2025-12-19",
    "qwen3-vl-plus-2025-09-23",
    "qwen3-vl-flash",
    "qwen3-vl-flash-2026-01-22",
    "qwen3-vl-flash-2025-10-15",
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
