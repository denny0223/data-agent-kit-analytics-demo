{{
    config(
        materialized = 'view'
    )
}}

with source as (
    select * from external_query(
        'us.cymbal-pets-cloudsql',
        'select customer_id, first_name, last_name, email, gender, address_city, address_state, loyalty_member, customer_type, signup_date from customers'
    )
),

renamed as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        gender,
        address_city,
        address_state,
        loyalty_member,
        customer_type,
        signup_date
    from source
)

select * from renamed
