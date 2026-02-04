"""
CoinGecko API producer.

Polls CoinGecko API for market data and produces to Kafka.
Features:
- Configurable polling interval
- Rate limit handling
- Retry with backoff
- Prometheus metrics
"""

import signal
import time
from datetime import datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.common.config import get_settings
from src.common.logging import setup_logging, get_logger
from src.common.kafka_client import KafkaProducerClient
from src.common.metrics import (
    MESSAGES_PRODUCED,
    PRODUCER_ERRORS,
    start_metrics_server,
)

logger = get_logger(__name__)


class CoinGeckoProducer:
    """
    Producer for CoinGecko market data.
    
    Polls the API at regular intervals and sends data to Kafka.
    """

    def __init__(self):
        """Initialize producer with settings."""
        self.settings = get_settings()
        self.kafka_client = KafkaProducerClient()
        self.running = False
        
        self.base_url = self.settings.coingecko_api_url
        self.coins = self.settings.coingecko_coins_list
        self.poll_interval = self.settings.coingecko_poll_interval_seconds

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _fetch_prices(self) -> dict:
        """
        Fetch current prices from CoinGecko API.
        
        Returns:
            Dict with coin prices and market data.
        
        Raises:
            requests.RequestException: On API error after retries.
        """
        url = f"{self.base_url}/simple/price"
        params = {
            "ids": ",".join(self.coins),
            "vs_currencies": "usd",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
            "include_last_updated_at": "true",
        }
        
        logger.debug("coingecko_fetching", coins_count=len(self.coins))
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        return response.json()

    def _transform_to_messages(self, data: dict) -> list[dict]:
        """
        Transform CoinGecko response into normalized messages.
        
        Args:
            data: Raw API response.
            
        Returns:
            List of normalized price messages.
        """
        messages = []
        ingested_at = datetime.now(timezone.utc).isoformat()
        
        for coin_id, values in data.items():
            message = {
                "coin_id": coin_id,
                "price_usd": values.get("usd"),
                "market_cap_usd": values.get("usd_market_cap"),
                "volume_24h_usd": values.get("usd_24h_vol"),
                "change_24h_percent": values.get("usd_24h_change"),
                "last_updated_at": values.get("last_updated_at"),
                "source": "coingecko",
                "ingested_at": ingested_at,
            }
            messages.append(message)
        
        return messages

    def _produce_messages(self, messages: list[dict]) -> None:
        """
        Send messages to Kafka.
        
        Args:
            messages: List of normalized price messages.
        """
        topic = self.settings.kafka_topic_prices
        
        for message in messages:
            self.kafka_client.produce(
                topic=topic,
                value=message,
                key=message["coin_id"],
            )
            
            MESSAGES_PRODUCED.labels(topic=topic, source="coingecko").inc()
        
        logger.info(
            "coingecko_produced",
            count=len(messages),
            topic=topic,
        )

    def _poll_once(self) -> None:
        """Execute one poll cycle."""
        try:
            data = self._fetch_prices()
            messages = self._transform_to_messages(data)
            self._produce_messages(messages)
            
        except requests.RequestException as e:
            logger.error("coingecko_fetch_error", error=str(e))
            PRODUCER_ERRORS.labels(source="coingecko", error_type="fetch").inc()
            
        except Exception as e:
            logger.error("coingecko_error", error=str(e))
            PRODUCER_ERRORS.labels(source="coingecko", error_type="unknown").inc()

    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info("shutdown_signal_received", signal=signum)
        self.running = False

    def run(self) -> None:
        """
        Main entry point - start the producer.
        
        Polls CoinGecko at regular intervals until shutdown.
        """
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        self.running = True
        logger.info(
            "producer_starting",
            coins=self.coins,
            poll_interval=self.poll_interval,
        )

        try:
            while self.running:
                self._poll_once()
                
                # Sleep in small increments to allow quick shutdown
                for _ in range(self.poll_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
        finally:
            self.kafka_client.flush()
            logger.info("producer_stopped")


def main() -> None:
    """Entry point for the CoinGecko producer."""
    setup_logging(json_format=True, level="INFO")
    start_metrics_server()
    
    producer = CoinGeckoProducer()
    producer.run()


if __name__ == "__main__":
    main()