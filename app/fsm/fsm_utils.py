import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.utils.errors import InvalidInputError

from .models import UserSession

TRUE_VALUES = frozenset({"yes", "y", "ndio", "1"})
FALSE_VALUES = frozenset({"no", "n", "zii", "2"})


def encode_session(session: UserSession) -> str:
    return session.model_dump_json()


def decode_session(data: str) -> UserSession:
    return UserSession.model_validate_json(data)


def parse_product_name(raw_text: str) -> str:
    cleaned = raw_text.strip()
    length = len(cleaned)

    if length < 2 or length > 100:
        raise InvalidInputError("Product name must be between 2 and 100 characters.")

    return cleaned


def parse_price(raw_text: str) -> Decimal:
    cleaned = raw_text.strip().upper()
    cleaned = re.sub(r"^(KES|KSH)\.?\s*", "", cleaned)
    cleaned = re.sub(r"/=$", "", cleaned)
    cleaned = cleaned.replace(",", "").strip()

    try:
        price = Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:  # pyright: ignore[] # TODO: Log error
        raise InvalidInputError(
            "Please enter a valid price, e.g. '150', 'KES 150', or '150/='."
        )

    if price <= 0:
        raise InvalidInputError("Price must be greater than 0")

    return price


def parse_quantity(raw_text: str) -> int:
    cleaned = raw_text.strip()

    try:
        quantity = int(cleaned)
    except ValueError:
        raise InvalidInputError("Please enter a whole number, e.g. 0, 1, or 25.")

    if quantity < 0:
        raise InvalidInputError("Quantity cannot be negative.")

    return quantity


def parse_confirmation(raw_text: str) -> bool:
    cleaned = raw_text.strip().lower()

    if cleaned in TRUE_VALUES:
        return True

    if cleaned in FALSE_VALUES:
        return False

    raise InvalidInputError("Please reply with Yes/Y/Ndio/1 or No/N/Zii/2.")
