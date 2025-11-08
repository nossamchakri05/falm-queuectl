"""Utility functions for queuectl."""
import uuid
import logging
from datetime import datetime
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_job_id() -> str:
    """Generate a unique job ID."""
    return str(uuid.uuid4())


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + 'Z'


def parse_timestamp(timestamp: str) -> datetime:
    """Parse ISO format timestamp."""
    return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))


def calculate_backoff_delay(attempts: int, base: float = 2.0) -> float:
    """Calculate exponential backoff delay in seconds.
    
    Args:
        attempts: Number of attempts (0-indexed)
        base: Base delay in seconds (default: 2.0)
    
    Returns:
        Delay in seconds
    """
    return base ** attempts


def validate_job_data(job_data: dict) -> tuple[bool, Optional[str]]:
    """Validate job data structure.
    
    Args:
        job_data: Job data dictionary
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['command']
    
    for field in required_fields:
        if field not in job_data:
            return False, f"Missing required field: {field}"
    
    if not isinstance(job_data.get('command'), str) or not job_data['command'].strip():
        return False, "Command must be a non-empty string"
    
    if 'max_retries' in job_data:
        if not isinstance(job_data['max_retries'], int) or job_data['max_retries'] < 0:
            return False, "max_retries must be a non-negative integer"
    
    return True, None



