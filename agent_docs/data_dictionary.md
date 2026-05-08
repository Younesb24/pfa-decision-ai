# Olist Data Dictionary — Source of Truth

> **READ THIS BEFORE WRITING ANY SQL OR DBT MODEL.**
> All column names below are exact. Do NOT invent columns that aren't listed here.

## Dataset: Brazilian E-Commerce by Olist (Kaggle)

- **Source:** https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- **Period:** September 2016 – October 2018
- **Geography:** Brazil (all 27 states)
- **Volume:** ~100K orders, ~112K order items, ~99K reviews

---

## 1. olist_orders_dataset.csv → `bronze.orders`

| Column | Type (Bronze) | Type (Silver) | Description |
|--------|--------------|---------------|-------------|
| order_id | TEXT | TEXT (PK) | Unique order identifier |
| customer_id | TEXT | TEXT (FK→customers) | Customer who placed the order |
| order_status | TEXT | TEXT | delivered, shipped, canceled, unavailable, invoiced, processing, created, approved |
| order_purchase_timestamp | TEXT | TIMESTAMP | When the customer clicked "buy" |
| order_approved_at | TEXT | TIMESTAMP | When payment was approved (nullable) |
| order_delivered_carrier_date | TEXT | TIMESTAMP | When seller handed to carrier (nullable) |
| order_delivered_customer_date | TEXT | TIMESTAMP | When customer received it (nullable) |
| order_estimated_delivery_date | TEXT | TIMESTAMP | Estimated delivery date shown at purchase |

**Computed in Silver:** `delivery_delay_days` (FLOAT), `is_late` (BOOLEAN)

## 2. olist_order_items_dataset.csv → `bronze.order_items`

| Column | Type (Bronze) | Type (Silver) | Description |
|--------|--------------|---------------|-------------|
| order_id | TEXT | TEXT (FK→orders) | Order this item belongs to |
| order_item_id | TEXT | INTEGER | Sequential number (1, 2, 3...) within order |
| product_id | TEXT | TEXT (FK→products) | Product purchased |
| seller_id | TEXT | TEXT (FK→sellers) | Seller fulfilling this item |
| shipping_limit_date | TEXT | TIMESTAMP | Deadline for seller to ship |
| price | TEXT | NUMERIC(10,2) | Item price in BRL |
| freight_value | TEXT | NUMERIC(10,2) | Freight cost in BRL |

**Grain:** One row per item per order. Composite PK = (order_id, order_item_id).

## 3. olist_order_payments_dataset.csv → `bronze.order_payments`

| Column | Type (Bronze) | Type (Silver) | Description |
|--------|--------------|---------------|-------------|
| order_id | TEXT | TEXT (FK→orders) | Order this payment applies to |
| payment_sequential | TEXT | INTEGER | Sequential payment number (1, 2...) |
| payment_type | TEXT | TEXT | credit_card, boleto, voucher, debit_card |
| payment_installments | TEXT | INTEGER | Number of installments chosen |
| payment_value | TEXT | NUMERIC(10,2) | Amount paid in BRL |

**Note:** One order can have multiple payment rows (split payments).

## 4. olist_order_reviews_dataset.csv → `bronze.order_reviews`

| Column | Type (Bronze) | Type (Silver) | Description |
|--------|--------------|---------------|-------------|
| review_id | TEXT | TEXT (PK) | Unique review identifier |
| order_id | TEXT | TEXT (FK→orders) | Order being reviewed |
| review_score | TEXT | INTEGER | 1 to 5 (1=worst, 5=best) |
| review_comment_title | TEXT | TEXT | Optional title (nullable, Portuguese) |
| review_comment_message | TEXT | TEXT | Free text comment (nullable, Portuguese) |
| review_creation_date | TEXT | TIMESTAMP | When review was submitted |
| review_answer_timestamp | TEXT | TIMESTAMP | When seller/platform responded |

**Warning:** ~58K reviews have empty comment_message. Score is always present.

## 5. olist_products_dataset.csv → `bronze.products`

| Column | Type (Bronze) | Type (Silver) | Description |
|--------|--------------|---------------|-------------|
| product_id | TEXT | TEXT (PK) | Unique product identifier |
| product_category_name | TEXT | TEXT | Category in Portuguese (nullable for ~610 products) |
| product_name_lenght | TEXT | INTEGER | Length of product name (NOTE: Olist typo "lenght") |
| product_description_lenght | TEXT | INTEGER | Length of description (NOTE: same typo) |
| product_photos_qty | TEXT | INTEGER | Number of photos |
| product_weight_g | TEXT | NUMERIC | Weight in grams |
| product_length_cm | TEXT | NUMERIC | Package length in cm |
| product_height_cm | TEXT | NUMERIC | Package height in cm |
| product_width_cm | TEXT | NUMERIC | Package width in cm |

**Note:** Column names have typo "lenght" — preserve in bronze, can rename in silver.

## 6. olist_sellers_dataset.csv → `bronze.sellers`

| Column | Type (Bronze) | Type (Silver) | Description |
|--------|--------------|---------------|-------------|
| seller_id | TEXT | TEXT (PK) | Unique seller identifier |
| seller_zip_code_prefix | TEXT | TEXT | 5-digit zip prefix |
| seller_city | TEXT | TEXT | City name (lowercase, may have inconsistencies) |
| seller_state | TEXT | TEXT | 2-letter state code (SP, RJ, MG, etc.) |

## 7. olist_customers_dataset.csv → `bronze.customers`

| Column | Type (Bronze) | Type (Silver) | Description |
|--------|--------------|---------------|-------------|
| customer_id | TEXT | TEXT (PK) | Order-level customer ID (unique per order) |
| customer_unique_id | TEXT | TEXT | True unique customer (for cross-order dedup) |
| customer_zip_code_prefix | TEXT | TEXT | 5-digit zip prefix |
| customer_city | TEXT | TEXT | City name |
| customer_state | TEXT | TEXT | 2-letter state code |

**Important:** `customer_id` is unique per row but NOT per real person. Use `customer_unique_id` for customer-level analysis.

## 8. olist_geolocation_dataset.csv → `bronze.geolocation`

| Column | Type (Bronze) | Type (Silver) | Description |
|--------|--------------|---------------|-------------|
| geolocation_zip_code_prefix | TEXT | TEXT | 5-digit zip prefix |
| geolocation_lat | TEXT | NUMERIC | Latitude |
| geolocation_lng | TEXT | NUMERIC | Longitude |
| geolocation_city | TEXT | TEXT | City name |
| geolocation_state | TEXT | TEXT | 2-letter state code |

**Warning:** Multiple rows per zip code (different lat/lng). Deduplicate in silver (avg or first).

## 9. product_category_name_translation.csv → `bronze.product_category_name_translation`

| Column | Type (Bronze) | Type (Silver) | Description |
|--------|--------------|---------------|-------------|
| product_category_name | TEXT | TEXT (PK) | Portuguese category name |
| product_category_name_english | TEXT | TEXT | English translation |

**71 categories total.**

---

## Key Relationships (FK Map)

```
orders.customer_id        → customers.customer_id
order_items.order_id      → orders.order_id
order_items.product_id    → products.product_id
order_items.seller_id     → sellers.seller_id
order_payments.order_id   → orders.order_id
order_reviews.order_id    → orders.order_id
products.product_category → product_category_name_translation.product_category_name
customers.zip_code_prefix → geolocation.zip_code_prefix
sellers.zip_code_prefix   → geolocation.zip_code_prefix
```

## Known Data Quality Issues

1. **~610 products** have NULL `product_category_name`
2. **Review comments** are in Portuguese — ~41% are empty
3. **Geolocation** has duplicate zip codes — must aggregate
4. **Column typo** in products: `product_name_lenght` (not "length")
5. **~1.1K orders** have no delivery dates (not yet delivered at dataset cutoff)
6. **`customer_id`** ≠ unique customer — use `customer_unique_id` for dedup
