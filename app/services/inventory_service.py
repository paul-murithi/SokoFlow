from uuid import UUID


class InventoryService:
    def add_stock(self, product_id: UUID, quantity: int) -> None:
        # Check if the product exist. If exists, update. If not, add.
        pass

    def remove_stock(self) -> None:
        pass

    def get_stock(self) -> None:
        pass

    def is_low_stock(self) -> None:
        pass

    def update_threshold(self) -> None:
        pass
