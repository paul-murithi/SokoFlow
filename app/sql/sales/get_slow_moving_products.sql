SELECT
    products.id AS product_id,
    products.name AS product_name,
    products.price AS unit_price,
    COALESCE(SUM(sales.quantity), 0) AS units_sold,
    COALESCE(inventory.quantity, 0) AS current_stock
FROM products
LEFT JOIN sales
    ON sales.product_id = products.id
    AND sales.shop_id = :shop_id
    AND sales.created_at >= :day_start
    AND sales.created_at < :day_end
LEFT JOIN inventory
    ON inventory.product_id = products.id
WHERE products.shop_id = :shop_id
GROUP BY
    products.id,
    products.name,
    products.price,
    inventory.quantity
HAVING COALESCE(SUM(sales.quantity), 0) <= :max_sales_count
ORDER BY units_sold ASC, product_name ASC
LIMIT :limit
