WITH product_revenue AS (
    SELECT
        s.product_id,
        p.name AS product_name,
        SUM(s.total) AS total_revenue,
        DENSE_RANK() OVER (ORDER BY SUM(s.total) DESC) AS rank
    FROM sales s
    JOIN products p ON p.id = s.product_id
    WHERE s.shop_id = :shop_id
      AND s.created_at >= :day_start
      AND s.created_at < :day_end
    GROUP BY s.product_id, p.name
)
SELECT
    product_id,
    product_name AS name,
    total_revenue AS revenue
FROM product_revenue
WHERE rank = 1;
