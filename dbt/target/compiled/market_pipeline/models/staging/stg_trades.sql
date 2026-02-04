with source as (
    select * from `bigquery-486314`.`market_data`.`trades`
),

cleaned as (
    select
        symbol,
        price,
        quantity,
        price * quantity as trade_value,
        trade_id,
        timestamp_millis(trade_time) as trade_timestamp,
        buyer_is_maker,
        source,
        ingested_at,
        inserted_at
    from source
)

select * from cleaned