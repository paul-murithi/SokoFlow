SELECT
	products.id,
	products.shop_id,
	products.name,
	products.name_lower,
	products.sku,
	products.price,
	products.created_at,
	products.updated_at
FROM products
WHERE products.shop_id = :shop_id
ORDER BY products.created_at DESC, products.id DESC
