SELECT
    products.id,
    products.shop_id,
    products.name,
    products.sku,
    products.price,
    similarity(name_lower, :search_term) AS similarity_score
FROM products
WHERE shop_id = :shop_id
  AND name_lower % :search_term
ORDER BY similarity(name_lower, :search_term) DESC
LIMIT :limit;
