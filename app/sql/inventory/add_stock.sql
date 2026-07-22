INSERT INTO inventory (
	product_id,
	quantity
)
VALUES (
	:product_id,
	:quantity
)
ON CONFLICT (product_id)
DO UPDATE SET
	quantity = inventory.quantity + EXCLUDED.quantity,
	last_updated = now()
RETURNING
	inventory.id,
	inventory.product_id,
	inventory.quantity,
	inventory.low_stock_threshold,
	inventory.last_updated
