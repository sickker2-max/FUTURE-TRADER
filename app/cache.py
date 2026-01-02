"""
Redis Cache Manager Implementation

This module provides a Redis-based caching solution with support for
common cache operations including set, get, delete, increment, decrement,
expire, ttl, and clear_all methods.
"""

import redis
from typing import Any, Optional, Union
from datetime import timedelta
import json
import logging

logger = logging.getLogger(__name__)


class RedisCache:
    """
    A Redis cache manager that provides a simple interface for caching operations.
    
    This class wraps Redis client functionality and provides convenient methods
    for managing cached data with optional serialization support.
    """
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
        socket_connect_timeout: int = 5,
        socket_keepalive: bool = True,
        health_check_interval: int = 30,
    ):
        """
        Initialize Redis cache connection.
        
        Args:
            host: Redis server hostname (default: 'localhost')
            port: Redis server port (default: 6379)
            db: Redis database number (default: 0)
            password: Redis authentication password (optional)
            decode_responses: Whether to decode responses as strings (default: True)
            socket_connect_timeout: Socket connection timeout in seconds (default: 5)
            socket_keepalive: Enable socket keepalive (default: True)
            health_check_interval: Health check interval in seconds (default: 30)
        """
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=decode_responses,
                socket_connect_timeout=socket_connect_timeout,
                socket_keepalive=socket_keepalive,
                health_check_interval=health_check_interval,
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Successfully connected to Redis at {host}:{port}")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def set(
        self,
        key: str,
        value: Any,
        ex: Optional[Union[int, timedelta]] = None,
        px: Optional[Union[int, timedelta]] = None,
        nx: bool = False,
        xx: bool = False,
        serialize: bool = True,
    ) -> bool:
        """
        Set a key-value pair in the cache.
        
        Args:
            key: Cache key
            value: Value to cache (can be any JSON-serializable object)
            ex: Expiration time in seconds (optional)
            px: Expiration time in milliseconds (optional)
            nx: Only set if key does not exist (default: False)
            xx: Only set if key exists (default: False)
            serialize: Whether to JSON serialize the value (default: True)
        
        Returns:
            True if the operation was successful, False otherwise
        """
        try:
            if serialize and not isinstance(value, (str, bytes)):
                value = json.dumps(value)
            
            result = self.redis_client.set(
                key,
                value,
                ex=ex,
                px=px,
                nx=nx,
                xx=xx,
            )
            logger.debug(f"Set cache key '{key}' with expiration: {ex or px}")
            return result
        except Exception as e:
            logger.error(f"Error setting cache key '{key}': {e}")
            raise
    
    def get(self, key: str, deserialize: bool = True) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            deserialize: Whether to JSON deserialize the value (default: True)
        
        Returns:
            The cached value, or None if the key does not exist
        """
        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            
            if deserialize:
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # If deserialization fails, return the raw value
                    return value
            return value
        except Exception as e:
            logger.error(f"Error getting cache key '{key}': {e}")
            raise
    
    def delete(self, *keys: str) -> int:
        """
        Delete one or more keys from the cache.
        
        Args:
            *keys: One or more cache keys to delete
        
        Returns:
            Number of keys that were deleted
        """
        try:
            if not keys:
                return 0
            
            count = self.redis_client.delete(*keys)
            logger.debug(f"Deleted {count} cache key(s)")
            return count
        except Exception as e:
            logger.error(f"Error deleting cache keys: {e}")
            raise
    
    def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment the value of a numeric key.
        
        Args:
            key: Cache key
            amount: Amount to increment by (default: 1)
        
        Returns:
            The new value after incrementing
        """
        try:
            result = self.redis_client.incrby(key, amount)
            logger.debug(f"Incremented cache key '{key}' by {amount}, new value: {result}")
            return result
        except redis.ResponseError as e:
            logger.error(f"Error incrementing cache key '{key}': {e}")
            raise ValueError(f"Cannot increment non-integer value at key '{key}'")
        except Exception as e:
            logger.error(f"Error incrementing cache key '{key}': {e}")
            raise
    
    def decrement(self, key: str, amount: int = 1) -> int:
        """
        Decrement the value of a numeric key.
        
        Args:
            key: Cache key
            amount: Amount to decrement by (default: 1)
        
        Returns:
            The new value after decrementing
        """
        try:
            result = self.redis_client.decrby(key, amount)
            logger.debug(f"Decremented cache key '{key}' by {amount}, new value: {result}")
            return result
        except redis.ResponseError as e:
            logger.error(f"Error decrementing cache key '{key}': {e}")
            raise ValueError(f"Cannot decrement non-integer value at key '{key}'")
        except Exception as e:
            logger.error(f"Error decrementing cache key '{key}': {e}")
            raise
    
    def expire(self, key: str, time: Union[int, timedelta]) -> bool:
        """
        Set an expiration time on a key.
        
        Args:
            key: Cache key
            time: Expiration time in seconds (int) or timedelta object
        
        Returns:
            True if the timeout was set, False if the key does not exist
        """
        try:
            if isinstance(time, timedelta):
                time = int(time.total_seconds())
            
            result = self.redis_client.expire(key, time)
            logger.debug(f"Set expiration for cache key '{key}': {time} seconds")
            return result
        except Exception as e:
            logger.error(f"Error setting expiration for cache key '{key}': {e}")
            raise
    
    def ttl(self, key: str) -> int:
        """
        Get the remaining time to live of a key in seconds.
        
        Args:
            key: Cache key
        
        Returns:
            TTL in seconds, -1 if key has no expiration, -2 if key does not exist
        """
        try:
            result = self.redis_client.ttl(key)
            logger.debug(f"TTL for cache key '{key}': {result} seconds")
            return result
        except Exception as e:
            logger.error(f"Error getting TTL for cache key '{key}': {e}")
            raise
    
    def clear_all(self) -> bool:
        """
        Clear all keys from the current Redis database.
        
        WARNING: This operation will delete all data in the current database.
        Use with caution.
        
        Returns:
            True if the operation was successful
        """
        try:
            self.redis_client.flushdb()
            logger.warning("Cleared all cache keys from the current database")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            raise
    
    def exists(self, *keys: str) -> int:
        """
        Check if one or more keys exist in the cache.
        
        Args:
            *keys: One or more cache keys to check
        
        Returns:
            Number of keys that exist
        """
        try:
            if not keys:
                return 0
            
            count = self.redis_client.exists(*keys)
            logger.debug(f"Cache key existence check: {count} key(s) exist")
            return count
        except Exception as e:
            logger.error(f"Error checking cache key existence: {e}")
            raise
    
    def keys(self, pattern: str = '*') -> list:
        """
        Get all keys matching a pattern.
        
        Args:
            pattern: Key pattern to match (default: '*' for all keys)
        
        Returns:
            List of matching keys
        """
        try:
            keys_list = self.redis_client.keys(pattern)
            logger.debug(f"Found {len(keys_list)} cache key(s) matching pattern '{pattern}'")
            return keys_list
        except Exception as e:
            logger.error(f"Error getting cache keys matching pattern '{pattern}': {e}")
            raise
    
    def mget(self, *keys: str) -> list:
        """
        Get multiple values from the cache.
        
        Args:
            *keys: One or more cache keys
        
        Returns:
            List of values (None for non-existent keys)
        """
        try:
            if not keys:
                return []
            
            values = self.redis_client.mget(*keys)
            logger.debug(f"Retrieved {len(values)} value(s) from cache")
            return values
        except Exception as e:
            logger.error(f"Error getting multiple cache values: {e}")
            raise
    
    def mset(self, mapping: dict) -> bool:
        """
        Set multiple key-value pairs in the cache.
        
        Args:
            mapping: Dictionary of key-value pairs to set
        
        Returns:
            True if successful
        """
        try:
            if not mapping:
                return True
            
            serialized_mapping = {}
            for key, value in mapping.items():
                if isinstance(value, (str, bytes)):
                    serialized_mapping[key] = value
                else:
                    serialized_mapping[key] = json.dumps(value)
            
            self.redis_client.mset(serialized_mapping)
            logger.debug(f"Set {len(serialized_mapping)} cache key(s)")
            return True
        except Exception as e:
            logger.error(f"Error setting multiple cache values: {e}")
            raise
    
    def close(self) -> None:
        """
        Close the Redis connection.
        """
        try:
            self.redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
            raise
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Singleton instance for application-wide cache access
_cache_instance: Optional[RedisCache] = None


def get_cache(
    host: str = 'localhost',
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
) -> RedisCache:
    """
    Get or create a singleton Redis cache instance.
    
    Args:
        host: Redis server hostname
        port: Redis server port
        db: Redis database number
        password: Redis authentication password
    
    Returns:
        RedisCache instance
    """
    global _cache_instance
    
    if _cache_instance is None:
        _cache_instance = RedisCache(
            host=host,
            port=port,
            db=db,
            password=password,
        )
    
    return _cache_instance
