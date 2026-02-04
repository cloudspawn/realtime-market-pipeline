"""
Centralized configuration management using Pydantic Settings.

Loads environment variables from .env file and validates them.
Single source of truth for all configuration across the project.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Main settings class - loads all config from .env
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Kafka
    kafka_bootstrap_servers: str
    kafka_api_key: str
    kafka_api_secret: str
    kafka_topic_trades: str = "market.trades.raw"
    kafka_topic_prices: str = "market.prices.enriched"
    kafka_topic_dlq: str = "market.dlq"

    # GCP
    gcp_project_id: str
    gcp_credentials_path: str

    # BigQuery
    bq_dataset: str = "market_data"

    # Binance
    binance_ws_url: str = "wss://stream.binance.com:9443"
    binance_symbols: str = "btcusdt,ethusdt,solusdt"

    # CoinGecko
    coingecko_api_url: str = "https://api.coingecko.com/api/v3"
    coingecko_poll_interval_seconds: int = 60
    coingecko_coins: str = "bitcoin,ethereum,solana"

    # Consumer
    consumer_batch_size: int = 100
    consumer_flush_timeout_seconds: int = 10

    # Monitoring
    prometheus_port: int = 8000

    # GCS
    gcs_bucket: str = ""
    gcs_parquet_prefix: str = "raw"    

    @property
    def binance_symbols_list(self) -> list[str]:
        """Parse comma-separated symbols into a list."""
        return [s.strip().lower() for s in self.binance_symbols.split(",")]

    @property
    def coingecko_coins_list(self) -> list[str]:
        """Parse comma-separated coins into a list."""
        return [c.strip().lower() for c in self.coingecko_coins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to avoid reloading .env on every call.
    """
    return Settings()