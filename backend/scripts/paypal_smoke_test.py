"""$1 PayPal Sandbox smoke test: token -> create order -> (try) capture -> invoice.

Run from backend/:  python scripts/paypal_smoke_test.py
Sandbox only: no real money moves.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from services import paypal_client as pp  # noqa: E402

print("base url:", pp.BASE_URL)
pp.get_access_token()
print("token: ok")

order_id, status, approve_url = pp.create_order(1.00, "Smoke test $1", return_url="http://localhost:5173")
print("order:", order_id, status)
print("approve (log in with a SANDBOX personal account):", approve_url)

try:
    pp.capture_order(order_id)
except pp.PayPalError as e:
    print("capture before approval ->", e.name, "(expected)")

try:
    inv_id, inv_status = pp.send_offer_invoice("sb-buyer@example.com", "Test Buyer", "Win-back offer",
                                               50.00, 20, "20% off your next order")
    print("invoice:", inv_id, inv_status)
except pp.PayPalError as e:
    print("invoice ->", e.status, e.name, "(enable 'Invoicing' on the app in developer.paypal.com)")
