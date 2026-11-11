"""Demo helpers (API.md section 9)."""
from fastapi import APIRouter

import mock_data as m

router = APIRouter(prefix="/api/demo", tags=["Demo"])


@router.post("/reset")
def reset():
    m.reset_state()
    return {"status": "reset", "buyer_id": m.DEMO_BUYER, "merchant_id": m.DEMO_MERCHANT}
