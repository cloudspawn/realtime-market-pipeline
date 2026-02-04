with source as (
    select * from `bigquery-486314`.`market_data`.`prices`
),

cleaned as (
    select
        coin_id,
        price_usd,
        market_cap_usd,
        volume_24h_usd,
        change_24h_percent,
        timestamp_seconds(last_updated_at) as last_updated_timestamp,
        source,
        ingested_at,
        inserted_at
    from source
)

select * from cleaned