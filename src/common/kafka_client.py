"""
Kafka producer client wrapper.

Provides a reusable, configured Kafka producer with:
- Confluent Cloud authentication
- Delivery callbacks
- Graceful shutdown
"""

import json
from typing import Any, Callable

from confluent_kafka import Producer, KafkaError

from src.common.config import get_settings
from src.common.logging import get_logger

logger = get_logger(__name__)


class KafkaProducerClient:
    """
    Wrapper around confluent_kafka.Producer.
    
    Usage:
        client = KafkaProducerClient()
        client.produce("topic", {"key": "value"})
        client.flush()  # On shutdown
    """

    def __init__(self, on_delivery: Callable | None = None):
        """
        Initialize Kafka producer with Confluent Cloud config.
        
        Args:
            on_delivery: Optional callback for delivery reports.
        """
        settings = get_settings()
        
        self._config = {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": settings.kafka_api_key,
            "sasl.password": settings.kafka_api_secret,
            # Performance tuning
            "linger.ms": 5,
            "batch.num.messages": 100,
            "compression.type": "snappy",
        }
        
        self._producer = Producer(self._config)
        self._on_delivery = on_delivery or self._default_delivery_callback
        
        logger.info(
            "kafka_producer_initialized",
            bootstrap_servers=settings.kafka_bootstrap_servers,
        )

    def _default_delivery_callback(self, err: KafkaError | None, msg) -> None:
        """Default callback for delivery reports."""
        if err:
            logger.error(
                "kafka_delivery_failed",
                error=str(err),
                topic=msg.topic(),
            )
        else:
            logger.debug(
                "kafka_delivered",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )

    def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
    ) -> None:
        """
        Send a message to Kafka.
        
        Args:
            topic: Target topic name.
            value: Message payload (will be JSON serialized).
            key: Optional message key for partitioning.
        """
        try:
            self._producer.produce(
                topic=topic,
                value=json.dumps(value).encode("utf-8"),
                key=key.encode("utf-8") if key else None,
                callback=self._on_delivery,
            )
            self._producer.poll(0)
        except Exception as e:
            logger.error(
                "kafka_produce_error",
                error=str(e),
                topic=topic,
            )
            raise

    def flush(self, timeout: float = 10.0) -> int:
        """
        Wait for all messages to be delivered.
        
        Args:
            timeout: Max seconds to wait.
            
        Returns:
            Number of messages still in queue (0 = all delivered).
        """
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            logger.warning(
                "kafka_flush_incomplete",
                remaining_messages=remaining,
            )
        else:
            logger.info("kafka_flush_complete")
        return remaining

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - flush on close."""
        self.flush()