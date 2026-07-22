from enum import StrEnum


class ProductSQL(StrEnum):
    LIST_BY_SHOP = "products/list_by_shop.sql"


class InventorySQL(StrEnum):
    GET_BY_PRODUCT_ID = "inventory/get_by_product_id.sql"
    ADD_STOCK = "inventory/add_stock.sql"


class SalesSQL(StrEnum):
    GET_TOTAL_REVENUE_AND_COUNT = "sales/get_total_revenue_and_count.sql"
    GET_PRODUCTS_WITH_LOW_STOCK = "sales/get_products_with_low_stock.sql"
    GET_TOP_MOVING_PRODUCTS_BY_UNITS = "sales/get_top_moving_products_by_units.sql"
    GET_TOP_MOVING_PRODUCTS_BY_REVENUE = "sales/get_top_moving_products_by_revenue.sql"
