SELECT
    inventory.id,
    inventory.product_id,
    inventory.quantity,
    inventory.low_stock_threshold,
    inventory.last_updated
FROM inventory
WHERE inventory.product_id = :product_id
