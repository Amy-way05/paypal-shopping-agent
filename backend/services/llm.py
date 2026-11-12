"""Gemini wrapper with a model chain and a template fallback, so the demo never breaks.

Order tried: GEMINI_MODEL, then each model in GEMINI_FALLBACK_MODEL (comma
separated), then gemini-flash-lite-latest. A model that errors is skipped for
COOLDOWN seconds. If everything fails, callers get their template text.
"""
import logging
import os
import time

log = logging.getLogger("llm")

LITE_MODEL = "gemini-flash-lite-latest"
TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "12000"))
COOLDOWN = 60
_cooldown_until = {}
_client = None


def _key():
    return os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")


def enabled():
    return bool(_key()) and os.getenv("LLM_MODE", "on").strip().lower() != "off"


def models():
    chain = [os.getenv("GEMINI_MODEL", "")] + os.getenv("GEMINI_FALLBACK_MODEL", "").split(",") + [LITE_MODEL]
    seen, out = set(), []
    for m in (c.strip() for c in chain):
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types
        _client = genai.Client(api_key=_key(),
                               http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    return _client


def _available():
    now = time.time()
    return [m for m in models() if _cooldown_until.get(m, 0) <= now]


def _fail(model, err):
    log.warning("gemini %s failed: %s", model, str(err)[:160])
    _cooldown_until[model] = time.time() + COOLDOWN


def generate(prompt, fallback, max_tokens=200, system=None):
    """Return (text, source) where source is the model name or "template"."""
    if not enabled():
        return fallback, "template"
    from google.genai import types
    cfg = types.GenerateContentConfig(max_output_tokens=max_tokens, system_instruction=system,
                                      temperature=0.6)
    for model in _available():
        try:
            r = client().models.generate_content(model=model, contents=prompt, config=cfg)
            text = (r.text or "").strip()
            if text:
                return text, model
        except Exception as e:  # noqa: BLE001 - any failure means "try the next one"
            _fail(model, e)
    return fallback, "template"


def run_tools(system, history, message, tools):
    """Gemini function calling (the SDK runs the tool loop).
    Returns (reply_text, model, new_history) or None if every model failed."""
    if not enabled():
        return None
    from google.genai import types
    cfg = types.GenerateContentConfig(
        system_instruction=system, tools=tools, temperature=0.3,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=6))
    for model in _available():
        try:
            chat = client().chats.create(model=model, config=cfg, history=list(history))
            r = chat.send_message(message)
            text = (r.text or "").strip()
            if text:
                return text, model, chat.get_history()
        except Exception as e:  # noqa: BLE001
            _fail(model, e)
    return None
