import logging
import logging.handlers
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra'):
            log_data['extra'] = record.extra
        
        return json.dumps(log_data)


def setup_logger(
    name: str,
    log_dir: str = 'logs',
    log_level: int = logging.INFO,
    enable_console: bool = True,
    enable_file: bool = True,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Configure and return a logger with JSON formatter and rotating file handlers.
    
    Args:
        name: Logger name
        log_dir: Directory for log files
        log_level: Logging level (default: INFO)
        enable_console: Enable console output (default: True)
        enable_file: Enable file output (default: True)
        max_bytes: Max size for log file before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Create logs directory if it doesn't exist
    if enable_file:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Console handler with JSON formatter
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        json_formatter = JSONFormatter()
        console_handler.setFormatter(json_formatter)
        logger.addHandler(console_handler)
    
    # Rotating file handler with JSON formatter
    if enable_file:
        log_file = Path(log_dir) / f'{name}.log'
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(log_level)
        json_formatter = JSONFormatter()
        file_handler.setFormatter(json_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Module-level logger
logger = setup_logger('future-trader')


if __name__ == '__main__':
    # Example usage
    test_logger = setup_logger('test-app')
    test_logger.info('This is an info message')
    test_logger.warning('This is a warning message')
    test_logger.error('This is an error message')
    
    try:
        1 / 0
    except ZeroDivisionError:
        test_logger.exception('An exception occurred')
