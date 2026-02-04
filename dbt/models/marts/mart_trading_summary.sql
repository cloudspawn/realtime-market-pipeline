-- Final trading summary mart
with trades as (
    select * from {{ ref('int_trades_aggregated') }}
),

latest_prices as (
    select * from {{ ref('int_prices_latest') }}
),

-- Map symbol to coin_id (BTCUSDT -> bitcoin)
symbol_mapping as (
    select 'BTCUSDT' as symbol, 'bitcoin' as coin_id union all
    select 'ETHUSDT', 'ethereum' union all
    select 'SOLUSDT', 'solana' union all
    select 'ADAUSDT', 'cardano' union all
    select 'DOTUSDT', 'polkadot' union all
    select 'AVAXUSDT', 'avalanche-2' union all
    select 'LINKUSDT', 'chainlink' union all
    select 'MATICUSDT', 'polygon-ecosystem-token' union all
    select 'XRPUSDT', 'ripple' union all
    select 'BNBUSDT', 'binancecoin' union all
    select 'DOGEUSDT', 'dogecoin' union all
    select 'SHIBUSDT', 'shiba-inu' union all
    select 'LTCUSDT', 'litecoin' union all
    select 'ATOMUSDT', 'cosmos' union all
    select 'NEARUSDT', 'near' union all
    select 'APTUSDT', 'aptos' union all
    select 'ARBUSDT', 'arbitrum' union all
    select 'OPUSDT', 'optimism' union all
    select 'INJUSDT', 'injective-protocol' union all
    select 'SUIUSDT', 'sui'
),

summary as (
    select
        t.symbol,
        t.trade_hour,
        t.trade_count,
        t.total_quantity,
        t.total_value,
        t.avg_price,
        t.min_price,
        t.max_price,
        p.market_cap_usd,
        p.volume_24h_usd,
        p.change_24h_percent
    from trades t
    left join symbol_mapping m on t.symbol = m.symbol
    left join latest_prices p on m.coin_id = p.coin_id
)

select * from summary