from pydantic import BaseModel, UUID4
from datetime import datetime
from app.config import Status

class FintechWalletAuthCreateSchema(BaseModel):
    fintech_wallet_id: UUID4
    access_token: str
    refresh_token: str
    token_expiry: datetime

class FintechWalletAuthResponseSchema(BaseModel):
    fintech_wallet_auth_id: UUID4
    fintech_wallet_id: UUID4
    token_expiry: datetime
    created_date: datetime
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID4
    modified_date: datetime
    
    class Config:
        orm_mode = True