from fastapi import APIRouter, Request, HTTPException, Depends
from app.auth.dependencies import oauth2_scheme
import httpx
import os

MERCADOPAGO_CLIENT_ID = os.getenv("MERCADOPAGO_CLIENT_ID")
MERCADOPAGO_CLIENT_SECRET = os.getenv("MERCADOPAGO_CLIENT_SECRET")
MERCADOPAGO_REDIRECT_URI = os.getenv("MERCADOPAGO_REDIRECT_URI")  # Same you configured in MP app

router = APIRouter(
    prefix="/mercado-pago",
    tags=["Mercado Pago"],
    dependencies=[Depends(oauth2_scheme)],
    include_in_schema=False,  # Stub — not production-ready; hidden until Mercado Pago integration is implemented
)

@router.get("/mercadopago/callback")
async def mercadopago_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.mercadopago.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": MERCADOPAGO_CLIENT_ID,
                "client_secret": MERCADOPAGO_CLIENT_SECRET,
                "code": code,
                "redirect_uri": MERCADOPAGO_REDIRECT_URI
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        token_data = response.json()

        # Here you save user access_token, refresh_token, user_id etc. to your DB
        # For now just return it
        return token_data
