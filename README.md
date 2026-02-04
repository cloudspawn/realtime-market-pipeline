# realtime-market-pipeline

> ⚠️ **Work in Progress** — Production-grade version of [realtime-crypto-elt](https://github.com/cloudspawn/realtime-crypto-elt)

[![Status](https://img.shields.io/badge/status-in%20development-yellow)]()
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![Kafka](https://img.shields.io/badge/Kafka-Confluent-black?logo=apachekafka&logoColor=white)](https://confluent.io)
[![BigQuery](https://img.shields.io/badge/BigQuery-Google%20Cloud-4285F4?logo=googlebigquery&logoColor=white)](https://cloud.google.com/bigquery)
[![dbt](https://img.shields.io/badge/dbt-1.9-FF694B?logo=dbt&logoColor=white)](https://getdbt.com)
[![Airflow](https://img.shields.io/badge/Airflow-2.10-017CEE?logo=apacheairflow&logoColor=white)](https://airflow.apache.org)

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
│  Kafka ──▶ Consumer ──▶ BigQuery (raw) + GCS (parquet)         │
│                │                                                │
│                ├── Batch insert                                 │
│                ├── Dead Letter Queue                            │
│                └── Dual-write (DWH + Data Lake)                │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TRANSFORMATION                             │
├─────────────────────────────────────────────────────────────────┤
│  Airflow ──▶ dbt run (every 10 min)                            │
│                 │                                               │
│                 ├── staging (views)                             │
│                 ├── intermediate (views)                        │
│                 └── marts (tables)                              │
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
- **Dual-write consumer**: BigQuery (data warehouse) + GCS Parquet (data lake)
- **Data lake**: Parquet files partitioned by date (`raw/trades/YYYY/MM/DD/`)
- **dbt transformations**: staging → intermediate → marts
- **Airflow orchestration**: DAG with dbt run/test every 10 minutes
- **PostgreSQL**: Production-ready Airflow metadata database
- **Docker Compose**: Full orchestration with one command
- **Production patterns**: Retry with exponential backoff, automatic reconnection, graceful shutdown, Dead Letter Queue
- **Observability**: Prometheus metrics (throughput, errors, connections)
- **Structured logging**: JSON logs for easy parsing

### Coming soon 🚧
- Grafana dashboards (public)

## Project Structure
```
realtime-market-pipeline/
├── src/
│   ├── producers/
│   │   ├── binance_ws.py       # WebSocket real-time trades
│   │   └── coingecko.py        # API polling for market data
│   ├── consumers/
│   │   └── bigquery_consumer.py # Dual-write to BigQuery + GCS
│   └── common/
│       ├── config.py           # Pydantic settings
│       ├── logging.py          # Structured logging
│       ├── kafka_client.py     # Kafka producer wrapper
│       └── metrics.py          # Prometheus metrics
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
│       ├── staging/            # stg_trades, stg_prices
│       ├── intermediate/       # int_trades_aggregated, int_prices_latest
│       └── marts/              # mart_trading_summary
├── airflow/
│   ├── Dockerfile              # Custom Airflow image with dbt
│   └── dags/
│       └── dbt_dag.py          # DAG for dbt orchestration
├── docker-compose.yml          # Full orchestration
├── Dockerfile                  # App image for producers/consumer
└── README.md
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Confluent Cloud account (Kafka)
- GCP account (BigQuery, GCS)

### Setup
```bash
# Clone
git clone https://github.com/cloudspawn/realtime-market-pipeline.git
cd realtime-market-pipeline

# Configure
cp .env.example .env
# Edit .env with your credentials

# Add GCP service account key
cp /path/to/your/key.json secrets/gcp-key.json

# Start everything
docker compose up -d
```

### Access

| Service | URL |
|---------|-----|
| Airflow | http://localhost:8080 |
| Prometheus (producer-binance) | http://localhost:8000/metrics |
| Prometheus (consumer) | http://localhost:8001/metrics |
| Prometheus (producer-coingecko) | http://localhost:8002/metrics |

### Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f producer-binance
docker compose logs -f consumer
docker compose logs -f airflow-scheduler
```

### Stop
```bash
docker compose down
```

## Configuration

See `.env.example` for all available settings.

Required:
- Confluent Cloud credentials (Kafka)
- GCP credentials (BigQuery, GCS)
- Airflow admin credentials
- PostgreSQL password

## Metrics

Prometheus metrics exposed on each service:

| Metric | Type | Description |
|--------|------|-------------|
| `producer_messages_produced_total` | Counter | Messages sent to Kafka |
| `producer_errors_total` | Counter | Producer errors by type |
| `producer_websocket_connections` | Gauge | Active WebSocket connections |
| `consumer_messages_consumed_total` | Counter | Messages consumed from Kafka |
| `consumer_messages_inserted_total` | Counter | Messages inserted into BigQuery |

## License

MIT