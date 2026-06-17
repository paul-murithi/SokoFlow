from typing import Any


class ResourceNotFoundException(Exception):
    def __init__(self, entity_name: str, identifier: Any):
        self.entity_name = entity_name
        self.identifier = identifier
        self.message = f"{entity_name} with identifier '{identifier}' was not found."
        super().__init__(self.message)


class InsufficientStockError(Exception):
    def __init__(self, name: str, internal_code: int):
        self.name = name
        self.internal_code = internal_code


class ResourceAlreadyExistsException(Exception):
    def __init__(self, entity_name: str, field_name: str, value: Any):
        self.entity_name = entity_name
        self.field_name = field_name
        self.value = value
        self.message = f"{entity_name} with {field_name} '{value}' already exists."
        super().__init__(self.message)


class InvalidPriceException(Exception):
    def __init__(
        self, price: float, message: str = "Product price cannot be negative."
    ):
        self.price = price
        self.message = f"{message} Provided: KES {price}"
        super().__init__(self.message)


class InsufficientStockException(Exception):
    def __init__(self, product_id: str, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        self.message = (
            f"Cannot deduct {requested} units. Only {available} units available."
        )
        super().__init__(self.message)


class InvalidThresholdException(Exception):
    def __init__(self, threshold: int):
        self.threshold = threshold
        self.message = (
            f"Low stock threshold must be greater than or equal to 0. Got: {threshold}"
        )
        super().__init__(self.message)


class InvalidSaleQuantityException(Exception):
    def __init__(self, quantity: int):
        self.quantity = quantity
        self.message = f"Sale quantity must be at least 1 unit. Provided: {quantity}"
        super().__init__(self.message)


class InvalidAggregationDateException(Exception):
    def __init__(
        self,
        provided_date: str,
        message: str = "Cannot aggregate sales data for future dates.",
    ):
        self.provided_date = provided_date
        self.message = f"{message} Received: {provided_date}"
        super().__init__(self.message)
