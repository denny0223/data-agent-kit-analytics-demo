{{
    config(
        materialized = 'view'
    )
}}

with source as (
    select * from {{ source('cymbal_pets', 'orders') }}
),

renamed as (
    select
        order_id,
        customer_id,
        order_date,
        order_type,
        payment_method,
        promo_code,
        shipping_address_city,
        store_id
    from source
)

select * from renamed
