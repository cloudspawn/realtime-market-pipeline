-- Get latest price per coin
with prices as (
    select * from `bigquery-486314`.`market_data`.`stg_prices`
),

ranked as (
    select
        *,
        row_number() over (partition by coin_id order by last_updated_timestamp desc) as rn
    from prices
),

latest as (
    select
        coin_id,
        price_usd,
        market_cap_usd,
        volume_24h_usd,
        change_24h_percent,
        last_updated_timestamp
    from ranked
    where rn = 1
)

select * from latest