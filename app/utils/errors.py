class ResourceNotFound(Exception):
    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id
