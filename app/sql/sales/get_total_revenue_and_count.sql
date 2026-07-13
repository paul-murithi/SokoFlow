SELECT
	COALESCE(SUM(sales.total), 0) AS revenue,
	COUNT(*) AS transaction_count
FROM sales
WHERE sales.shop_id = :shop_id
	AND sales.created_at >= :day_start
	AND sales.created_at < :day_end
