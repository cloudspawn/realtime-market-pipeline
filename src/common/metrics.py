"""
Prometheus metrics exposition.

Defines and exposes metrics for monitoring the pipeline.
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server

from src.common.config import get_settings
from src.common.logging import get_logger

logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Producer metrics
# -----------------------------------------------------------------------------

MESSAGES_PRODUCED = Counter(
    "producer_messages_produced_total",
    "Total messages produced to Kafka",
    ["topic", "source"],
)

PRODUCER_ERRORS = Counter(
    "producer_errors_total",
    "Total producer errors",
    ["source", "error_type"],
)

WEBSOCKET_CONNECTIONS = Gauge(
    "producer_websocket_connections",
    "Current number of active WebSocket connections",
    ["source"],
)

# -----------------------------------------------------------------------------
# Consumer metrics (for later)
# -----------------------------------------------------------------------------

MESSAGES_CONSUMED = Counter(
    "consumer_messages_consumed_total",
    "Total messages consumed from Kafka",
    ["topic"],
)

MESSAGES_INSERTED = Counter(
    "consumer_messages_inserted_total",
    "Total messages inserted into BigQuery",
    ["table"],
)

CONSUMER_LAG = Gauge(
    "consumer_lag_seconds",
    "Consumer lag in seconds",
    ["topic", "partition"],
)

CONSUMER_ERRORS = Counter(
    "consumer_errors_total",
    "Total consumer errors",
    ["error_type"],
)

# -----------------------------------------------------------------------------
# Processing metrics
# -----------------------------------------------------------------------------

PROCESSING_TIME = Histogram(
    "processing_duration_seconds",
    "Time spent processing messages",
    ["component"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)


def start_metrics_server() -> None:
    """
    Start Prometheus metrics HTTP server.
    
    Exposes metrics at http://localhost:{port}/metrics
    """
    settings = get_settings()
    port = settings.prometheus_port
    
    start_http_server(port)
    logger.info("metrics_server_started", port=port)