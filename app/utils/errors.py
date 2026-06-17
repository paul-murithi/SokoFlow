class ResourceNotFound(Exception):
    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id


class InsufficientStockError(Exception):
    def __init__(self, name: str, internal_code: int):
        self.name = name
        self.internal_code = internal_code
