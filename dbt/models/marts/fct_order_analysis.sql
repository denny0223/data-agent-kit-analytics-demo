{{
    config(
        materialized = 'table',
        partition_by = {
            "field": "order_date",
            "data_type": "date",
            "granularity": "month"
        },
        cluster_by = ["order_type", "customer_type"]
    )
}}

with orders as (
    select * from {{ ref('stg_orders') }}
),

order_items_aggregated as (
    select
        order_id,
        sum(price) as order_amount,
        sum(quantity) as total_quantity,
        count(order_item_id) as total_items
    from {{ ref('stg_order_items') }}
    group by order_id
),

customers as (
    select
        customer_id,
        customer_type
    from {{ ref('stg_customers') }}
),

customer_pets_aggregated as (
    select
        customer_id,
        string_agg(distinct pet_type, ', ' order by pet_type) as pet_type,
        string_agg(distinct dietary_needs, ', ' order by dietary_needs) as dietary_needs
    from {{ ref('stg_pet_profiles') }}
    group by customer_id
),

final as (
    select
        o.order_id,
        o.customer_id,
        o.order_date,
        format_date('%Y-%m', o.order_date) as order_month,
        o.order_type,
        o.payment_method,
        o.promo_code,
        coalesce(oi.order_amount, 0) as order_amount,
        coalesce(oi.total_quantity, 0) as total_quantity,
        coalesce(oi.total_items, 0) as total_items,
        c.customer_type,
        cp.pet_type,
        cp.dietary_needs
    from orders o
    left join order_items_aggregated oi
        on o.order_id = oi.order_id
    left join customers c
        on o.customer_id = c.customer_id
    left join customer_pets_aggregated cp
        on o.customer_id = cp.customer_id
)

select * from final
