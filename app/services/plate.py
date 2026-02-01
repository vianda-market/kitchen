from uuid import UUID
import psycopg2.extensions
from app.dto.models import PlateDTO, CreditCurrencyDTO
from app.services.crud_service import plate_service, credit_currency_service
from app.utils.log import log_info, log_error

def recalculate_plate_credits(plate_id: UUID, db: psycopg2.extensions.connection):
    plate = plate_service.get_by_id(plate_id, db)
    if not plate:
        raise Exception("Plate not found")
    credit_currency = credit_currency_service.get_by_id(plate.credit_currency_id, db)
    if not credit_currency:
        raise Exception("Credit currency not found")
    credits = round(float(plate.price) / float(credit_currency.credit_value))
    plate_service.update(plate_id, {"credit": credits}, db)
    log_info(f"Updated plate {plate_id} credits to {credits} (price: {plate.price}, credit_value: {credit_currency.credit_value})")
