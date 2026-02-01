from pydantic import BaseModel, EmailStr, UUID4
from typing import Optional

class FintechWalletCreateSchema(BaseModel):
    payment_method_id: UUID4
    provider: str  # Should be "MercadoPago"
    username: EmailStr  # The MercadoPago email
    wallet_id: str  # The card token or wallet token
