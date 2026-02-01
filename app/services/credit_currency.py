from uuid import UUID
import psycopg2.extensions
from app.dto.models import CreditCurrencyDTO, PlateDTO
from app.services.crud_service import credit_currency_service, plate_service, get_plates_by_credit_currency_id
from app.services.plate import recalculate_plate_credits
from app.utils.log import log_info

def update_credit_value_and_recalculate_plates(credit_currency_id: UUID, new_credit_value: float, db: psycopg2.extensions.connection):
    # Update the credit_value
    credit_currency_service.update(credit_currency_id, {"credit_value": new_credit_value}, db)
    log_info(f"Updated credit_value for currency {credit_currency_id} to {new_credit_value}")
    # Recalculate credits for all plates using this currency
    plates = get_plates_by_credit_currency_id(credit_currency_id, db)
    for plate in plates:
        recalculate_plate_credits(plate.plate_id, db)
    log_info(f"Recalculated credits for all plates using currency {credit_currency_id}")
