{{
    config(
        materialized = 'view'
    )
}}

with source as (
    select * from {{ source('cymbal_pets', 'order_items') }}
),

renamed as (
    select
        order_item_id,
        order_id,
        product_id,
        quantity,
        price
    from source
)

select * from renamed
