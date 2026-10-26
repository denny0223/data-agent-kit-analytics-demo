{{
    config(
        materialized = 'view'
    )
}}

with source as (
    select * from external_query(
        'us.cymbal-pets-cloudsql',
        'select pet_id, customer_id, pet_name, pet_type, age, weight, activity_level, dietary_needs from pet_profiles'
    )
),

renamed as (
    select
        pet_id,
        customer_id,
        pet_name,
        pet_type,
        age,
        weight,
        activity_level,
        dietary_needs
    from source
)

select * from renamed
