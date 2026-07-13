SELECT
	sales.product_id,
	SUM(sales.total) AS revenue
FROM sales
WHERE sales.shop_id = :shop_id
	AND sales.created_at >= :day_start
	AND sales.created_at < :day_end
GROUP BY sales.product_id
ORDER BY SUM(sales.total) DESC
LIMIT 1
