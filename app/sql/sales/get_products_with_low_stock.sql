SELECT
	products.id,
	products.name,
	inventory.quantity,
	inventory.low_stock_threshold
FROM products
INNER JOIN inventory
	ON inventory.product_id = products.id
WHERE products.shop_id = :shop_id
	AND inventory.quantity <= inventory.low_stock_threshold
