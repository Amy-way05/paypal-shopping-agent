import os
import sys

# Tests never call PayPal or Gemini: orders are simulated, messages use templates.
os.environ["PAYPAL_MODE"] = "off"
os.environ["LLM_MODE"] = "off"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
