"""
BigQuery + GCS consumer.

Consumes messages from Kafka and:
- Inserts into BigQuery (data warehouse)
- Writes Parquet files to GCS (data lake)

Features:
- Multi-topic consumption
- Batch inserts
- Dead Letter Queue for failed messages
- Automatic table creation
- Parquet export to GCS
- Prometheus metrics
"""

import io
import json
import signal
import time
from datetime import datetime, timezone
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from confluent_kafka import Consumer, KafkaError, KafkaException
from google.cloud import bigquery, storage
from google.oauth2 import service_account

from src.common.config import get_settings
from src.common.logging import setup_logging, get_logger
from src.common.kafka_client import KafkaProducerClient
from src.common.metrics import (
    MESSAGES_CONSUMED,
    MESSAGES_INSERTED,
    CONSUMER_ERRORS,
    start_metrics_server,
)

logger = get_logger(__name__)


# BigQuery schemas for each table
SCHEMAS = {
    "trades": [
        bigquery.SchemaField("symbol", "STRING"),
        bigquery.SchemaField("price", "FLOAT"),
        bigquery.SchemaField("quantity", "FLOAT"),
        bigquery.SchemaField("trade_id", "INTEGER"),
        bigquery.SchemaField("trade_time", "INTEGER"),
        bigquery.SchemaField("buyer_is_maker", "BOOLEAN"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
        bigquery.SchemaField("inserted_at", "TIMESTAMP"),
    ],
    "prices": [
        bigquery.SchemaField("coin_id", "STRING"),
        bigquery.SchemaField("price_usd", "FLOAT"),
        bigquery.SchemaField("market_cap_usd", "FLOAT"),
        bigquery.SchemaField("volume_24h_usd", "FLOAT"),
        bigquery.SchemaField("change_24h_percent", "FLOAT"),
        bigquery.SchemaField("last_updated_at", "INTEGER"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
        bigquery.SchemaField("inserted_at", "TIMESTAMP"),
    ],
}

# PyArrow schemas for Parquet
PARQUET_SCHEMAS = {
    "trades": pa.schema([
        ("symbol", pa.string()),
        ("price", pa.float64()),
        ("quantity", pa.float64()),
        ("trade_id", pa.int64()),
        ("trade_time", pa.int64()),
        ("buyer_is_maker", pa.bool_()),
        ("source", pa.string()),
        ("ingested_at", pa.string()),
        ("inserted_at", pa.string()),
    ]),
    "prices": pa.schema([
        ("coin_id", pa.string()),
        ("price_usd", pa.float64()),
        ("market_cap_usd", pa.float64()),
        ("volume_24h_usd", pa.float64()),
        ("change_24h_percent", pa.float64()),
        ("last_updated_at", pa.int64()),
        ("source", pa.string()),
        ("ingested_at", pa.string()),
        ("inserted_at", pa.string()),
    ]),
}


class BigQueryConsumer:
    """
    Kafka consumer that writes to BigQuery and GCS.
    """

    def __init__(self):
        """Initialize consumer with settings."""
        self.settings = get_settings()
        self.running = False
        
        # Kafka consumer config
        self._consumer_config = {
            "bootstrap.servers": self.settings.kafka_bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": self.settings.kafka_api_key,
            "sasl.password": self.settings.kafka_api_secret,
            "group.id": "bigquery-consumer-group",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
        
        self._consumer = Consumer(self._consumer_config)
        
        # Kafka producer for DLQ
        self._dlq_producer = KafkaProducerClient()
        
        # GCP credentials
        credentials = service_account.Credentials.from_service_account_file(
            self.settings.gcp_credentials_path
        )
        
        # BigQuery client
        self._bq_client = bigquery.Client(
            project=self.settings.gcp_project_id,
            credentials=credentials,
        )
        
        # GCS client
        self._gcs_client = storage.Client(
            project=self.settings.gcp_project_id,
            credentials=credentials,
        )
        self._gcs_bucket = self._gcs_client.bucket(self.settings.gcs_bucket) if self.settings.gcs_bucket else None
        
        # Topic to table mapping
        self._topic_table_map = {
            self.settings.kafka_topic_trades: "trades",
            self.settings.kafka_topic_prices: "prices",
        }
        
        # Batch buffers per table
        self._batches: dict[str, list[dict]] = {
            "trades": [],
            "prices": [],
        }
        
        self._batch_size = self.settings.consumer_batch_size
        self._flush_timeout = self.settings.consumer_flush_timeout_seconds
        self._last_flush_time = time.time()
        
        logger.info(
            "consumer_initialized",
            topics=list(self._topic_table_map.keys()),
            batch_size=self._batch_size,
            gcs_enabled=self._gcs_bucket is not None,
        )

    def _ensure_tables_exist(self) -> None:
        """Create BigQuery tables if they don't exist."""
        dataset_id = f"{self.settings.gcp_project_id}.{self.settings.bq_dataset}"
        
        for table_name, schema in SCHEMAS.items():
            table_id = f"{dataset_id}.{table_name}"
            table = bigquery.Table(table_id, schema=schema)
            
            try:
                self._bq_client.create_table(table)
                logger.info("table_created", table=table_id)
            except Exception as e:
                if "Already Exists" in str(e):
                    logger.debug("table_exists", table=table_id)
                else:
                    raise

    def _transform_trade_message(self, msg: dict) -> dict:
        """Transform trade message for BigQuery."""
        return {
            "symbol": msg.get("symbol"),
            "price": msg.get("price"),
            "quantity": msg.get("quantity"),
            "trade_id": msg.get("trade_id"),
            "trade_time": msg.get("trade_time"),
            "buyer_is_maker": msg.get("buyer_is_maker"),
            "source": msg.get("source"),
            "ingested_at": msg.get("ingested_at"),
            "inserted_at": datetime.now(timezone.utc).isoformat(),
        }

    def _transform_price_message(self, msg: dict) -> dict:
        """Transform price message for BigQuery."""
        return {
            "coin_id": msg.get("coin_id"),
            "price_usd": msg.get("price_usd"),
            "market_cap_usd": msg.get("market_cap_usd"),
            "volume_24h_usd": msg.get("volume_24h_usd"),
            "change_24h_percent": msg.get("change_24h_percent"),
            "last_updated_at": msg.get("last_updated_at"),
            "source": msg.get("source"),
            "ingested_at": msg.get("ingested_at"),
            "inserted_at": datetime.now(timezone.utc).isoformat(),
        }

    def _send_to_dlq(self, message: bytes, error: str, source_topic: str) -> None:
        """Send failed message to Dead Letter Queue."""
        dlq_message = {
            "original_message": message.decode("utf-8"),
            "error": error,
            "source_topic": source_topic,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self._dlq_producer.produce(
            topic=self.settings.kafka_topic_dlq,
            value=dlq_message,
        )
        
        logger.warning(
            "message_sent_to_dlq",
            source_topic=source_topic,
            error=error,
        )

    def _write_parquet_to_gcs(self, table_name: str, batch: list[dict]) -> None:
        """Write batch as Parquet file to GCS."""
        if not self._gcs_bucket or not batch:
            return
        
        try:
            # Create PyArrow table
            schema = PARQUET_SCHEMAS[table_name]
            table = pa.Table.from_pylist(batch, schema=schema)
            
            # Write to buffer
            buffer = io.BytesIO()
            pq.write_table(table, buffer)
            buffer.seek(0)
            
            # Generate path: raw/trades/2026/02/04/trades_20260204_143022_abc123.parquet
            now = datetime.now(timezone.utc)
            date_path = now.strftime("%Y/%m/%d")
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            filename = f"{table_name}_{timestamp}_{len(batch)}.parquet"
            
            blob_path = f"{self.settings.gcs_parquet_prefix}/{table_name}/{date_path}/{filename}"
            
            # Upload
            blob = self._gcs_bucket.blob(blob_path)
            blob.upload_from_file(buffer, content_type="application/octet-stream")
            
            logger.info(
                "parquet_uploaded",
                path=blob_path,
                rows=len(batch),
                table=table_name,
            )
            
        except Exception as e:
            logger.error(
                "parquet_upload_error",
                table=table_name,
                error=str(e),
            )
            CONSUMER_ERRORS.labels(error_type="gcs_upload").inc()

    def _flush_batch(self, table_name: str) -> None:
        """Flush batch to BigQuery and GCS."""
        batch = self._batches[table_name]
        
        if not batch:
            return
        
        table_id = f"{self.settings.gcp_project_id}.{self.settings.bq_dataset}.{table_name}"
        
        try:
            # Insert to BigQuery
            errors = self._bq_client.insert_rows_json(table_id, batch)
            
            if errors:
                logger.error(
                    "bigquery_insert_errors",
                    table=table_name,
                    errors=errors[:5],
                )
                CONSUMER_ERRORS.labels(error_type="bigquery_insert").inc(len(errors))
            else:
                MESSAGES_INSERTED.labels(table=table_name).inc(len(batch))
                logger.info(
                    "batch_inserted",
                    table=table_name,
                    count=len(batch),
                )
            
            # Write to GCS as Parquet
            self._write_parquet_to_gcs(table_name, batch)
            
            self._batches[table_name] = []
            
        except Exception as e:
            logger.error(
                "bigquery_flush_error",
                table=table_name,
                error=str(e),
            )
            CONSUMER_ERRORS.labels(error_type="bigquery_flush").inc()
            raise

    def _flush_all_batches(self) -> None:
        """Flush all batches to BigQuery and GCS."""
        for table_name in self._batches:
            self._flush_batch(table_name)
        self._last_flush_time = time.time()

    def _should_flush(self) -> bool:
        """Check if we should flush based on size or time."""
        for batch in self._batches.values():
            if len(batch) >= self._batch_size:
                return True
        
        if time.time() - self._last_flush_time >= self._flush_timeout:
            return True
        
        return False

    def _process_message(self, msg) -> None:
        """Process a single Kafka message."""
        topic = msg.topic()
        
        try:
            value = json.loads(msg.value().decode("utf-8"))
            table_name = self._topic_table_map.get(topic)
            
            if not table_name:
                logger.warning("unknown_topic", topic=topic)
                return
            
            if table_name == "trades":
                transformed = self._transform_trade_message(value)
            else:
                transformed = self._transform_price_message(value)
            
            self._batches[table_name].append(transformed)
            MESSAGES_CONSUMED.labels(topic=topic).inc()
            
        except json.JSONDecodeError as e:
            self._send_to_dlq(msg.value(), str(e), topic)
            CONSUMER_ERRORS.labels(error_type="json_decode").inc()
            
        except Exception as e:
            self._send_to_dlq(msg.value(), str(e), topic)
            CONSUMER_ERRORS.labels(error_type="transform").inc()

    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info("shutdown_signal_received", signal=signum)
        self.running = False

    def run(self) -> None:
        """Main entry point - start consuming."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        self._ensure_tables_exist()
        
        topics = list(self._topic_table_map.keys())
        self._consumer.subscribe(topics)
        
        self.running = True
        logger.info("consumer_starting", topics=topics)
        
        try:
            while self.running:
                msg = self._consumer.poll(1.0)
                
                if msg is None:
                    if self._should_flush():
                        self._flush_all_batches()
                        self._consumer.commit()
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("kafka_error", error=msg.error())
                    CONSUMER_ERRORS.labels(error_type="kafka").inc()
                    continue
                
                self._process_message(msg)
                
                if self._should_flush():
                    self._flush_all_batches()
                    self._consumer.commit()
                    
        except KafkaException as e:
            logger.error("kafka_exception", error=str(e))
            raise
            
        finally:
            self._flush_all_batches()
            self._consumer.commit()
            self._consumer.close()
            self._dlq_producer.flush()
            logger.info("consumer_stopped")


def main() -> None:
    """Entry point for the BigQuery consumer."""
    setup_logging(json_format=True, level="INFO")
    start_metrics_server()
    
    consumer = BigQueryConsumer()
    consumer.run()


if __name__ == "__main__":
    main()