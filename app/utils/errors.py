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
