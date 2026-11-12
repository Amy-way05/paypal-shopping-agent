"""Startup validation of credentials and settings.

Runs once at startup and is shown on /health, so a bad key or a wrong URL shows up
as a clear message instead of a broken demo. Never logs or returns a secret value.
The app always starts: anything wrong falls back (simulated PayPal / template replies).
"""
import logging
import os
import re
from urllib.parse import urlparse

from services import llm
from services import paypal_client as pp

log = logging.getLogger("config")
RESULT = {"paypal": "not checked", "gemini": "not checked", "warnings": []}

_PLACEHOLDER = re.compile(r"^(|x+|your[_-].*|changeme|<.*>|\.\.\.)$", re.I)


def _env(name):
    return os.getenv(name, "").strip().strip('"').strip("'")


def _check_secret(name, warnings, min_len):
    raw, val = os.getenv(name, ""), _env(name)
    if raw != val:
        warnings.append(f"{name} has spaces or quotes around it (ignored, but clean it up)")
    if _PLACEHOLDER.match(val):
        return f"{name} is missing"
    if len(val) < min_len or re.search(r"\s", val):
        return f"{name} doesn't look like a real key (too short or has spaces inside)"
    return None


def _check_url(name, value, warnings):
    u = urlparse(value)
    if u.scheme not in ("http", "https") or not u.netloc:
        warnings.append(f"{name}='{value}' is not a valid http(s) URL")
        return None
    if u.path not in ("", "/"):
        warnings.append(f"{name}='{value}' should be just the origin (no path)")
    return f"{u.scheme}://{u.netloc}"


def check_paypal(warnings):
    if os.getenv("PAYPAL_MODE", "sandbox").strip().lower() == "off":
        return "off (simulated orders)"
    problems = [p for p in (_check_secret("PAYPAL_CLIENT_ID", warnings, 20),
                            _check_secret("PAYPAL_SECRET", warnings, 20)) if p]
    if problems:
        return "error: " + "; ".join(problems) + " -> orders will be simulated"
    if _env("PAYPAL_CLIENT_ID") == _env("PAYPAL_SECRET"):
        return "error: PAYPAL_CLIENT_ID and PAYPAL_SECRET are the same value"
    try:
        pp.get_access_token()  # sandbox OAuth: proves the pair is valid and the network works
        return "ok (sandbox token received)"
    except pp.PayPalError as e:
        return f"error: {e.message}"


def check_gemini(warnings):
    if os.getenv("LLM_MODE", "on").strip().lower() == "off":
        return "off (template replies)"
    problem = _check_secret("GEMINI_API_KEY", warnings, 30)
    if problem:
        return f"error: {problem} -> chat uses template replies"
    if not _env("GEMINI_MODEL"):
        warnings.append("GEMINI_MODEL is empty; using the fallback models only")
    return "ok (key present; model chain: " + " -> ".join(llm.models()) + " -> template)"


def run():
    warnings = []
    frontend = _check_url("FRONTEND_URL", _env("FRONTEND_URL") or "http://localhost:5173", warnings)
    origins = [o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    for o in origins:
        _check_url("CORS_ORIGINS", o, warnings)
    if frontend and frontend not in origins and "*" not in origins:
        warnings.append(f"FRONTEND_URL origin {frontend} is not in CORS_ORIGINS: the browser will block API calls")
    RESULT.update(paypal=check_paypal(warnings), gemini=check_gemini(warnings), warnings=warnings)
    for k in ("paypal", "gemini"):
        (log.info if RESULT[k].startswith(("ok", "off")) else log.error)("%s: %s", k, RESULT[k])
    for w in warnings:
        log.warning(w)
    return RESULT
