# realtime-market-pipeline

> ⚠️ **Work in Progress** — Production-grade version of [realtime-crypto-elt](https://github.com/cloudspawn/realtime-crypto-elt)

[![Status](https://img.shields.io/badge/status-in%20development-yellow)]()
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![Kafka](https://img.shields.io/badge/Kafka-Confluent-black?logo=apachekafka&logoColor=white)](https://confluent.io)
[![BigQuery](https://img.shields.io/badge/BigQuery-Google%20Cloud-4285F4?logo=googlebigquery&logoColor=white)](https://cloud.google.com/bigquery)
[![dbt](https://img.shields.io/badge/dbt-1.9-FF694B?logo=dbt&logoColor=white)](https://getdbt.com)
[![Airflow](https://img.shields.io/badge/Airflow-2.x-017CEE?logo=apacheairflow&logoColor=white)](https://airflow.apache.org)

Production-grade real-time market data pipeline: multi-source ingestion → Kafka → BigQuery → dbt, with Airflow orchestration and Prometheus/Grafana monitoring.

## Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                         INGESTION                               │
├─────────────────────────────────────────────────────────────────┤
│  Binance WebSocket ──┐                                          │
│  CoinGecko API ──────┼──▶ Producers ──▶ Kafka (multi-topics)   │
│                      │         │                                │
│                      │    retry + reconnection                  │
└──────────────────────┴──────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                         PROCESSING                              │
├─────────────────────────────────────────────────────────────────┤
│  Kafka ──▶ Consumer ──▶ BigQuery (raw)                         │
│                │                                                │
│                ├── Batch insert                                 │
│                ├── Dead Letter Queue                            │
│                └── Idempotent writes                            │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TRANSFORMATION                             │
├─────────────────────────────────────────────────────────────────┤
│  Airflow ──▶ dbt run (scheduled)                               │
│                 │                                               │
│                 ├── staging                                     │
│                 ├── intermediate                                │
│                 └── marts                                       │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       MONITORING                                │
├─────────────────────────────────────────────────────────────────┤
│  Prometheus ◀── metrics (throughput, latency, errors)          │
│       │                                                         │
│       ▼                                                         │
│  Grafana ──▶ dashboards + alerting                             │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### Implemented ✅
- **Multi-source ingestion**: Binance WebSocket (real-time trades) + CoinGecko API (market data)
- **20 cryptocurrencies**: BTC, ETH, SOL, ADA, DOT, AVAX, LINK, MATIC, XRP, BNB, DOGE, SHIB, LTC, ATOM, NEAR, APT, ARB, OP, INJ, SUI
- **Kafka streaming**: Multi-topic architecture with partitioning by symbol
- **Production patterns**: Retry with exponential backoff, automatic reconnection, graceful shutdown
- **Observability**: Prometheus metrics (throughput, errors, connections)
- **Structured logging**: JSON logs for easy parsing

### Coming soon 🚧
- BigQuery consumer with batch inserts and DLQ
- dbt transformations (staging → intermediate → marts)
- Airflow orchestration
- Grafana dashboards

## Project Structure
```
realtime-market-pipeline/
├── src/
│   ├── producers/
│   │   ├── binance_ws.py       # WebSocket real-time trades
│   │   └── coingecko.py        # API polling for market data
│   ├── consumers/
│   │   └── (coming soon)
│   └── common/
│       ├── config.py           # Pydantic settings
│       ├── logging.py          # Structured logging
│       ├── kafka_client.py     # Kafka producer wrapper
│       └── metrics.py          # Prometheus metrics
├── dbt/
│   └── models/                 # (coming soon)
├── airflow/
│   └── dags/                   # (coming soon)
├── monitoring/
│   └── grafana/                # (coming soon)
├── tests/
├── docs/
└── README.md
```

## Quick Start
```bash
# Clone
git clone https://github.com/cloudspawn/realtime-market-pipeline.git
cd realtime-market-pipeline

# Install dependencies
uv sync

# Configure
cp .env.example .env
# Edit .env with your credentials

# Run producers
uv run python -m src.producers.binance_ws   # Terminal 1
uv run python -m src.producers.coingecko    # Terminal 2
```

## Configuration

See `.env.example` for all available settings.

Required:
- Confluent Cloud credentials (Kafka)
- GCP credentials (BigQuery)

## Metrics

Prometheus metrics exposed at `http://localhost:8000/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `producer_messages_produced_total` | Counter | Messages sent to Kafka |
| `producer_errors_total` | Counter | Producer errors by type |
| `producer_websocket_connections` | Gauge | Active WebSocket connections |

## License

MIT