"""PayPal REST client: SANDBOX ONLY.

The base URL is hardcoded to the sandbox on purpose: this project never
touches live money. Credentials come from .env (PAYPAL_CLIENT_ID / PAYPAL_SECRET).

Set PAYPAL_MODE=off (used by the tests) to skip PayPal entirely; callers then
fall back to simulated IDs and say so in the response.
"""
import os
import time

import requests

BASE_URL = "https://api-m.sandbox.paypal.com"  # sandbox only, never live
TIMEOUT = 20

_token = {"value": None, "expires_at": 0.0}


class PayPalError(Exception):
    def __init__(self, status, name, message, debug_id=None):
        super().__init__(f"{status} {name}: {message}")
        self.status, self.name, self.message, self.debug_id = status, name, message, debug_id


def _env(name):
    # tolerate copy-paste whitespace / quotes in .env or the Render dashboard
    return os.getenv(name, "").strip().strip('"').strip("'")


def enabled():
    return (os.getenv("PAYPAL_MODE", "sandbox").lower() != "off"
            and bool(_env("PAYPAL_CLIENT_ID") and _env("PAYPAL_SECRET")))


def _request(method, url, **kw):
    """requests call where network failures become a PayPalError (-> 502), never an unhandled 500."""
    try:
        return requests.request(method, url, timeout=TIMEOUT, **kw)
    except requests.Timeout:
        raise PayPalError(504, "PAYPAL_TIMEOUT", "PayPal Sandbox didn't answer in time. Try again.")
    except requests.RequestException:
        raise PayPalError(503, "PAYPAL_UNREACHABLE", "Can't reach PayPal Sandbox right now. Try again.")


def get_access_token():
    """OAuth2 client-credentials token, cached until 60s before expiry."""
    if _token["value"] and time.time() < _token["expires_at"] - 60:
        return _token["value"]
    r = _request("POST", f"{BASE_URL}/v1/oauth2/token",
                 auth=(_env("PAYPAL_CLIENT_ID"), _env("PAYPAL_SECRET")),
                 data={"grant_type": "client_credentials"})
    if r.status_code != 200:
        raise PayPalError(r.status_code, "AUTH_FAILED",
                          "PayPal rejected the Client ID / Secret (check they're the SANDBOX app's keys)")
    try:
        j = r.json()
        _token.update(value=j["access_token"], expires_at=time.time() + j.get("expires_in", 3000))
    except (ValueError, KeyError):
        raise PayPalError(502, "AUTH_FAILED", "Unexpected token response from PayPal")
    return _token["value"]


def _call(method, path, body=None, extra_headers=None):
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    headers.update(extra_headers or {})
    r = _request(method, f"{BASE_URL}{path}", json=body, headers=headers)
    if r.status_code >= 400:
        try:
            j = r.json()
        except ValueError:
            j = {}
        detail = (j.get("details") or [{}])[0]
        raise PayPalError(r.status_code, detail.get("issue") or j.get("name", "PAYPAL_ERROR"),
                          detail.get("description") or j.get("message", r.text[:200]), j.get("debug_id"))
    return r.json() if r.content else {}


def _money(amount):
    return {"currency_code": "USD", "value": f"{amount:.2f}"}


def _link(resource, rel):
    return next((l["href"] for l in resource.get("links", []) if l["rel"] in (rel, "payer-action")), None)


# ------------------------------------------------------------------ orders

def create_order(amount, description, custom_id=None, return_url=None, cancel_url=None):
    """Create a CAPTURE order. Returns (order_id, status, approve_url)."""
    unit = {"amount": _money(amount), "description": description[:127]}
    if custom_id:
        unit["custom_id"] = custom_id[:127]
    body = {"intent": "CAPTURE", "purchase_units": [unit]}
    if return_url:  # application_context keeps status CREATED + an "approve" link
        body["application_context"] = {"return_url": return_url, "cancel_url": cancel_url or return_url,
                                       "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING",
                                       "brand_name": "PayPal Shopping Agent"}
    o = _call("POST", "/v2/checkout/orders", body)
    return o["id"], o["status"], _link(o, "approve")


def get_order(order_id):
    return _call("GET", f"/v2/checkout/orders/{order_id}")


def capture_order(order_id):
    """Capture an approved order. Returns (status, capture_id). Raises PayPalError
    with name ORDER_NOT_APPROVED if the buyer hasn't approved yet."""
    o = _call("POST", f"/v2/checkout/orders/{order_id}/capture", {})
    cap = o["purchase_units"][0]["payments"]["captures"][0]
    return o["status"], cap["id"]


def refund_capture(capture_id, amount, note):
    """Partial (or full) refund of a capture. Returns (refund_id, status)."""
    r = _call("POST", f"/v2/payments/captures/{capture_id}/refund",
              {"amount": _money(amount), "note_to_payer": note[:255]})
    return r["id"], r["status"]


# ---------------------------------------------------------------- invoicing

def send_offer_invoice(customer_email, customer_name, item_name, amount, discount_pct, note):
    """Draft + send a PayPal invoice carrying the win-back discount. Returns (invoice_id, status)."""
    body = {
        "detail": {"currency_code": "USD", "note": note[:4000], "payment_term": {"term_type": "NET_10"}},
        "primary_recipients": [{"billing_info": {"email_address": customer_email,
                                                 "name": {"full_name": customer_name}}}],
        "items": [{"name": item_name[:200], "quantity": "1", "unit_amount": _money(amount),
                   "discount": {"percent": str(discount_pct)}}],
    }
    inv = _call("POST", "/v2/invoicing/invoices", body)
    invoice_id = inv.get("id") or inv.get("href", "").rstrip("/").split("/")[-1]
    _call("POST", f"/v2/invoicing/invoices/{invoice_id}/send", {"send_to_recipient": False})
    return invoice_id, "SENT"
