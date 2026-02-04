"""
Binance WebSocket producer.

Connects to Binance WebSocket streams and produces trade events to Kafka.
Features:
- Multi-symbol streaming
- Automatic reconnection
- Graceful shutdown
- Prometheus metrics
"""

import asyncio
import json
import signal
from datetime import datetime, timezone

import websockets
from websockets.exceptions import ConnectionClosed

from src.common.config import get_settings
from src.common.logging import setup_logging, get_logger
from src.common.kafka_client import KafkaProducerClient
from src.common.metrics import (
    MESSAGES_PRODUCED,
    PRODUCER_ERRORS,
    WEBSOCKET_CONNECTIONS,
    start_metrics_server,
)

logger = get_logger(__name__)


class BinanceWebSocketProducer:
    """
    WebSocket producer for Binance trade streams.
    
    Connects to multiple symbol streams and forwards trades to Kafka.
    """

    def __init__(self):
        """Initialize producer with settings."""
        self.settings = get_settings()
        self.kafka_client = KafkaProducerClient()
        self.running = False
        self._ws = None

    def _build_stream_url(self) -> str:
        """
        Build combined WebSocket stream URL for all symbols.
        
        Returns:
            WebSocket URL for multiple trade streams.
        """
        symbols = self.settings.binance_symbols_list
        streams = "/".join([f"{s}@trade" for s in symbols])
        url = f"{self.settings.binance_ws_url}/stream?streams={streams}"
        
        logger.info(
            "stream_url_built",
            symbols_count=len(symbols),
            url=url[:100] + "...",
        )
        return url

    def _parse_trade_message(self, raw_message: str) -> dict | None:
        """
        Parse Binance trade message into normalized format.
        
        Args:
            raw_message: Raw JSON string from WebSocket.
            
        Returns:
            Normalized trade dict or None if invalid.
        """
        try:
            data = json.loads(raw_message)
            
            if "data" in data:
                trade = data["data"]
            else:
                trade = data

            if trade.get("e") != "trade":
                return None

            return {
                "symbol": trade["s"].upper(),
                "price": float(trade["p"]),
                "quantity": float(trade["q"]),
                "trade_id": trade["t"],
                "trade_time": trade["T"],
                "buyer_is_maker": trade["m"],
                "source": "binance",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(
                "parse_error",
                error=str(e),
                raw_message=raw_message[:200],
            )
            PRODUCER_ERRORS.labels(source="binance", error_type="parse").inc()
            return None

    async def _handle_message(self, message: str) -> None:
        """
        Handle incoming WebSocket message.
        
        Args:
            message: Raw message string.
        """
        trade = self._parse_trade_message(message)
        
        if trade:
            topic = self.settings.kafka_topic_trades
            
            self.kafka_client.produce(
                topic=topic,
                value=trade,
                key=trade["symbol"],
            )
            
            MESSAGES_PRODUCED.labels(topic=topic, source="binance").inc()
            
            logger.debug(
                "trade_produced",
                symbol=trade["symbol"],
                price=trade["price"],
            )

    async def _connect_and_stream(self) -> None:
        """
        Connect to WebSocket and process messages.
        
        Handles reconnection on connection loss.
        """
        url = self._build_stream_url()
        retry_delay = 1

        while self.running:
            try:
                logger.info("websocket_connecting", url=url[:80])
                
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    WEBSOCKET_CONNECTIONS.labels(source="binance").set(1)
                    logger.info("websocket_connected")
                    
                    retry_delay = 1

                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(message)

            except ConnectionClosed as e:
                WEBSOCKET_CONNECTIONS.labels(source="binance").set(0)
                logger.warning(
                    "websocket_closed",
                    code=e.code,
                    reason=e.reason,
                )
            except Exception as e:
                WEBSOCKET_CONNECTIONS.labels(source="binance").set(0)
                PRODUCER_ERRORS.labels(source="binance", error_type="connection").inc()
                logger.error("websocket_error", error=str(e))

            if self.running:
                logger.info("websocket_reconnecting", delay_seconds=retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info("shutdown_signal_received", signal=signum)
        self.running = False

    async def run(self) -> None:
        """
        Main entry point - start the producer.
        
        Sets up signal handlers and runs the WebSocket loop.
        """
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        self.running = True
        logger.info(
            "producer_starting",
            symbols=self.settings.binance_symbols_list,
        )

        try:
            await self._connect_and_stream()
        finally:
            WEBSOCKET_CONNECTIONS.labels(source="binance").set(0)
            self.kafka_client.flush()
            logger.info("producer_stopped")


def main() -> None:
    """Entry point for the Binance WebSocket producer."""
    setup_logging(json_format=True, level="INFO")
    start_metrics_server()
    
    producer = BinanceWebSocketProducer()
    asyncio.run(producer.run())


if __name__ == "__main__":
    main()