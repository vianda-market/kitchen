# app/schemas/types.py
"""
Shared schema type aliases.

MoneyDecimal / NullableMoneyDecimal
------------------------------------
Pydantic v2 serialises ``Decimal`` values as strings by default, which breaks
JSON consumers that expect a JSON number (e.g. i18next pluralisation in the
mobile app).  Apply these aliases to every *response* schema field that must
arrive on the wire as a JSON ``number``.  Leave *input* schema fields as plain
``Decimal`` — Pydantic's lenient coercion of string → Decimal is desirable for
precision on inbound data.

Usage::

    from app.schemas.types import MoneyDecimal, NullableMoneyDecimal

    class MyResponseSchema(BaseModel):
        balance: MoneyDecimal          # required number
        fee: NullableMoneyDecimal      # optional number, null when absent
"""

from decimal import Decimal
from typing import Annotated

from pydantic.functional_serializers import PlainSerializer

# Serialise Decimal → float (JSON number) on the way out.
# ``return_type=float`` propagates the correct JSON Schema type ("number") to
# the generated OpenAPI spec so frontend codegen picks up the right type.
MoneyDecimal = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]

NullableMoneyDecimal = Annotated[
    Decimal | None,
    PlainSerializer(lambda v: float(v) if v is not None else None, return_type=float | None),
]
