"""Enum display labels by locale; canonical values match app.config.enums."""

from typing import Dict

# Enum display labels by locale — codes are canonical (DB); labels are display-only
ENUM_LABELS: Dict[str, Dict[str, Dict[str, str]]] = {
    "en": {
        "bill_resolution": {
            "Pending": "Pending",
            "Paid": "Paid",
            "Rejected": "Rejected",
            "Failed": "Failed",
        },
        "bill_payout_status": {
            "Pending": "Pending",
            "Completed": "Completed",
            "Failed": "Failed",
        },
        "street_type": {
            "St": "Street",
            "Ave": "Avenue",
            "Blvd": "Boulevard",
            "Rd": "Road",
            "Dr": "Drive",
            "Ln": "Lane",
            "Way": "Way",
            "Ct": "Court",
            "Pl": "Place",
            "Cir": "Circle",
        },
        "address_type": {
            "Restaurant": "Restaurant",
            "Entity Billing": "Entity Billing",
            "Entity Address": "Entity Address",
            "Customer Home": "Customer Home",
            "Customer Billing": "Customer Billing",
            "Customer Employer": "Customer Employer",
        },
    },
    "es": {
        "bill_resolution": {
            "Pending": "Pendiente",
            "Paid": "Pagada",
            "Rejected": "Rechazada",
            "Failed": "Fallida",
        },
        "bill_payout_status": {
            "Pending": "Pendiente",
            "Completed": "Completado",
            "Failed": "Fallido",
        },
        "street_type": {
            "St": "Calle",
            "Ave": "Avenida",
            "Blvd": "Bulevar",
            "Dr": "Calle",
            "Rd": "Camino",
            "Ln": "Pasaje",
            "Way": "Pasaje",
            "Ct": "Corte",
            "Pl": "Plaza",
            "Cir": "Círculo",
        },
        "address_type": {
            "Restaurant": "Restaurante",
            "Entity Billing": "Facturación de entidad",
            "Entity Address": "Dirección de entidad",
            "Customer Home": "Domicilio",
            "Customer Billing": "Facturación del cliente",
            "Customer Employer": "Empleador del cliente",
        },
    },
    "pt": {
        "bill_resolution": {
            "Pending": "Pendente",
            "Paid": "Paga",
            "Rejected": "Rejeitada",
            "Failed": "Falha",
        },
        "bill_payout_status": {
            "Pending": "Pendente",
            "Completed": "Concluído",
            "Failed": "Falho",
        },
        "street_type": {
            "St": "Rua",
            "Ave": "Avenida",
            "Blvd": "Bulevar",
            "Dr": "Rua",
            "Rd": "Estrada",
            "Ln": "Travessa",
            "Way": "Viela",
            "Ct": "Pátio",
            "Pl": "Praça",
            "Cir": "Circular",
        },
        "address_type": {
            "Restaurant": "Restaurante",
            "Entity Billing": "Faturamento da entidade",
            "Entity Address": "Endereço da entidade",
            "Customer Home": "Residência",
            "Customer Billing": "Faturamento do cliente",
            "Customer Employer": "Empregador do cliente",
        },
    },
}

LABELED_ENUM_TYPES = frozenset({"street_type", "address_type", "bill_resolution", "bill_payout_status"})


def get_label(enum_type: str, code: str, locale: str = "en") -> str:
    """Display label for enum code: requested locale -> English -> raw code."""
    return (
        ENUM_LABELS.get(locale, {}).get(enum_type, {}).get(code)
        or ENUM_LABELS.get("en", {}).get(enum_type, {}).get(code)
        or code
    )


def labels_for_values(enum_type: str, values: list[str], locale: str) -> Dict[str, str]:
    """Build code -> label map for a list of canonical values."""
    return {v: get_label(enum_type, v, locale) for v in values}
