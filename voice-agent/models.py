from pydantic import BaseModel, Field
from typing import List


class TransferContext(BaseModel):
    room_name: str
    session_id: str
    transfer_call_to: List[str]
    load_number: str


class TransferMessage(BaseModel):
    load_number: str
    reason_of_transfer: str
    price_asked_by_carrier: float | None = None
    best_price_offered_by_bot: float | None = None


class TransferRequest(BaseModel):
    load_number: str
    reason: str = Field(default="customer requested transfer")
    price_asked_by_carrier: float | None = None
    best_price_offered_by_bot: float | None = None