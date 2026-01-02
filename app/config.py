"""
Configuration module for the Future Trader application.
Contains settings for database, Redis, Kafka, and API configurations.
"""

from typing import Optional
from pydantic import BaseSettings


class Settings(BaseSettings):
    """
    Application settings and configurations.
    
    This class manages all configuration parameters for:
    - Database connections
    - Redis cache/session storage
    - Kafka message streaming
    - API endpoints and credentials
    """
    
    # Application Settings
    app_name: str = "Future Trader"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    # Database Configuration
    database_url: str = "postgresql://user:password@localhost:5432/future_trader"
    database_echo: bool = False
    database_pool_size: int = 20
    database_max_overflow: int = 0
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_ssl: bool = False
    redis_timeout: int = 5
    redis_connection_pool_size: int = 10
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_prefix: str = "future_trader"
    kafka_group_id: str = "future_trader_group"
    kafka_auto_offset_reset: str = "earliest"
    kafka_max_poll_records: int = 500
    kafka_session_timeout_ms: int = 30000
    kafka_request_timeout_ms: int = 60000
    
    # API Configuration
    api_base_url: str = "http://localhost:8000"
    api_version: str = "v1"
    api_timeout: int = 30
    api_max_retries: int = 3
    api_retry_delay: int = 1
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    
    # Trading API Configuration (External Services)
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    binance_testnet: bool = True
    
    # Logging Configuration
    log_level: str = "INFO"
    log_file: str = "logs/future_trader.log"
    log_max_bytes: int = 10485760  # 10MB
    log_backup_count: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def redis_url(self) -> str:
        """Generate Redis URL from configuration."""
        scheme = "rediss" if self.redis_ssl else "redis"
        password = f":{self.redis_password}@" if self.redis_password else ""
        return f"{scheme}://{password}{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    @property
    def kafka_brokers(self) -> list:
        """Parse Kafka bootstrap servers into a list."""
        return [server.strip() for server in self.kafka_bootstrap_servers.split(",")]
    
    def get_database_url(self) -> str:
        """Get the database connection URL."""
        return self.database_url
    
    def get_redis_url(self) -> str:
        """Get the Redis connection URL."""
        return self.redis_url


# Create a singleton instance of settings
settings = Settings()
