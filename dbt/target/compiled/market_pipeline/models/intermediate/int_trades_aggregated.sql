-- Aggregate trades by symbol and hour
with trades as (
    select * from `bigquery-486314`.`market_data`.`stg_trades`
),

aggregated as (
    select
        symbol,
        timestamp_trunc(trade_timestamp, HOUR) as trade_hour,
        count(*) as trade_count,
        sum(quantity) as total_quantity,
        sum(trade_value) as total_value,
        avg(price) as avg_price,
        min(price) as min_price,
        max(price) as max_price
    from trades
    group by symbol, trade_hour
)

select * from aggregated