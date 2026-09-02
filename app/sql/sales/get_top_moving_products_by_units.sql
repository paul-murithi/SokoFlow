WITH product_sales AS (
    SELECT
        s.product_id,
        p.name AS product_name,
        SUM(s.quantity) AS total_units_sold,
        DENSE_RANK() OVER (ORDER BY SUM(s.quantity) DESC) AS rank
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
    total_units_sold AS units_sold
FROM product_sales
WHERE rank = 1;
