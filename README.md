# realtime-market-pipeline

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
│                      │    retry + circuit breaker               │
└──────────────────────┴──────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                         PROCESSING                              │
├─────────────────────────────────────────────────────────────────┤
│  Kafka ──▶ Consumer ──▶ BigQuery (raw)                         │
│                │                                                │
│                ├── Batch insert (configurable)                  │
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

- **Multi-source ingestion**: Binance WebSocket (real-time) + CoinGecko API (enrichment)
- **Decoupled architecture**: Kafka as buffer with partitioning by asset
- **Production patterns**: retry with backoff, circuit breaker, dead letter queue
- **Batch processing**: configurable batch size with flush timeout
- **Idempotent writes**: deduplication on BigQuery
- **Orchestration**: Airflow DAGs with scheduling and alerting
- **Observability**: Prometheus metrics + Grafana dashboards
- **3-layer dbt models**: staging → intermediate → marts

## Project Structure

```
realtime-market-pipeline/
├── src/
│   ├── producers/
│   │   ├── binance_ws.py       # WebSocket real-time trades
│   │   └── coingecko.py        # API polling for metadata
│   ├── consumers/
│   │   └── bigquery_consumer.py
│   └── common/
│       ├── retry.py            # Retry logic with backoff
│       ├── metrics.py          # Prometheus metrics
│       └── config.py           # Configuration management
├── dbt/
│   └── models/
│       ├── staging/
│       ├── intermediate/
│       └── marts/
├── airflow/
│   └── dags/
│       └── market_pipeline_dag.py
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── dashboards/
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   └── (screenshots)
├── docker-compose.yml
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

# Run (development)
uv run python src/producers/binance_ws.py
uv run python src/consumers/bigquery_consumer.py

# Run (production with Docker)
docker-compose up -d
```

## Configuration

Create `.env` at root:

```
# Kafka (Confluent Cloud)
KAFKA_BOOTSTRAP_SERVERS=
KAFKA_API_KEY=
KAFKA_API_SECRET=

# GCP
GCP_PROJECT_ID=
GCP_CREDENTIALS_PATH=
BQ_DATASET=market_data

# Binance
BINANCE_WS_URL=wss://stream.binance.com:9443/ws
```

## Monitoring

Grafana dashboards available at `http://localhost:3000`:

- **Throughput**: messages/second by source
- **Latency**: end-to-end pipeline latency
- **Errors**: error rate by component
- **Consumer lag**: Kafka consumer lag

## License

MIT
