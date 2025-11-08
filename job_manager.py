"""Job management for queuectl."""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from storage import Storage
from utils import (
    generate_job_id, get_current_timestamp, validate_job_data,
    parse_timestamp, calculate_backoff_delay
)

logger = logging.getLogger(__name__)


class JobManager:
    """Manages job lifecycle and state transitions."""
    
    # Job states
    STATE_PENDING = "pending"
    STATE_PROCESSING = "processing"
    STATE_COMPLETED = "completed"
    STATE_FAILED = "failed"
    STATE_DEAD = "dead"
    
    def __init__(self, storage: Storage, config_manager):
        """Initialize job manager.
        
        Args:
            storage: Storage instance
            config_manager: ConfigManager instance
        """
        self.storage = storage
        self.config_manager = config_manager
    
    def enqueue_job(self, job_data: dict) -> Dict[str, Any]:
        """Enqueue a new job.
        
        Args:
            job_data: Job data dictionary
        
        Returns:
            Created job dictionary
        """
        # Validate job data
        is_valid, error = validate_job_data(job_data)
        if not is_valid:
            raise ValueError(error)
        
        # Get default config values
        config = self.config_manager.get_config()
        max_retries = job_data.get("max_retries", config.get("max_retries", 3))
        
        # Create job
        job_id = job_data.get("id") or generate_job_id()
        now = get_current_timestamp()
        
        job = {
            "id": job_id,
            "command": job_data["command"],
            "state": self.STATE_PENDING,
            "attempts": 0,
            "max_retries": max_retries,
            "created_at": now,
            "updated_at": now,
            "next_retry_at": None
        }
        
        self.storage.add_job(job)
        logger.info(f"Enqueued job {job_id}: {job_data['command']}")
        return job
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        return self.storage.get_job(job_id)
    
    def list_jobs(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        """List jobs, optionally filtered by state.
        
        Args:
            state: Optional state filter
        
        Returns:
            List of jobs
        """
        jobs = self.storage.get_all_jobs()
        if state:
            jobs = [j for j in jobs if j.get("state") == state]
        return jobs
    
    def get_pending_job(self) -> Optional[Dict[str, Any]]:
        """Atomically fetch a pending job and mark it as processing.
        
        Returns:
            Job dictionary or None if no pending jobs
        """
        jobs = self.storage.get_all_jobs()
        now = get_current_timestamp()
        
        # Find a pending job that's ready for processing
        for job in jobs:
            if job.get("state") == self.STATE_PENDING:
                # Check if job is ready (no retry delay or delay has passed)
                next_retry_at = job.get("next_retry_at")
                if next_retry_at:
                    try:
                        retry_time = parse_timestamp(next_retry_at)
                        current_time = parse_timestamp(now)
                        if retry_time > current_time:
                            continue  # Not ready yet
                    except Exception:
                        pass  # Invalid timestamp, proceed
                
                # Atomically update to processing
                try:
                    self.storage.update_job(job["id"], {
                        "state": self.STATE_PROCESSING,
                        "updated_at": now
                    })
                    logger.debug(f"Worker picked up job {job['id']}")
                    return self.storage.get_job(job["id"])
                except Exception as e:
                    logger.error(f"Error updating job {job['id']}: {e}")
                    continue
        
        return None
    
    def mark_job_completed(self, job_id: str):
        """Mark a job as completed.
        
        Args:
            job_id: Job ID
        """
        now = get_current_timestamp()
        self.storage.update_job(job_id, {
            "state": self.STATE_COMPLETED,
            "updated_at": now
        })
        logger.info(f"Job {job_id} completed")
    
    def mark_job_failed(self, job_id: str, error: Optional[str] = None):
        """Mark a job as failed and handle retry logic.
        
        Args:
            job_id: Job ID
            error: Optional error message
        """
        job = self.storage.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        attempts = job.get("attempts", 0) + 1
        max_retries = job.get("max_retries", 3)
        now = get_current_timestamp()
        
        config = self.config_manager.get_config()
        backoff_base = config.get("backoff_base", 2.0)
        
        if attempts > max_retries:
            # Move to DLQ
            job["state"] = self.STATE_DEAD
            job["attempts"] = attempts
            job["updated_at"] = now
            if error:
                job["last_error"] = error
            
            # Remove from jobs and add to DLQ
            self.storage.delete_job(job_id)
            self.storage.add_to_dlq(job)
            logger.warning(f"Job {job_id} exceeded max retries, moved to DLQ")
        else:
            # Calculate next retry time
            # delay = base ^ attempts (as per requirement)
            delay = calculate_backoff_delay(attempts, backoff_base)
            retry_time = datetime.utcnow().timestamp() + delay
            next_retry_at = datetime.utcfromtimestamp(retry_time).isoformat() + 'Z'
            
            self.storage.update_job(job_id, {
                "state": self.STATE_PENDING,  # Reset to pending for retry
                "attempts": attempts,
                "next_retry_at": next_retry_at,
                "updated_at": now,
                "last_error": error
            })
            logger.info(f"Job {job_id} failed (attempt {attempts}/{max_retries}), will retry in {delay:.1f}s")
    
    def get_status(self) -> Dict[str, Any]:
        """Get system status.
        
        Returns:
            Status dictionary
        """
        jobs = self.storage.get_all_jobs()
        dlq_jobs = self.storage.get_dlq_jobs()
        
        status = {
            "jobs": {
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
                "dead": 0,
                "total": len(jobs)
            },
            "dlq": {
                "total": len(dlq_jobs)
            }
        }
        
        for job in jobs:
            state = job.get("state", "unknown")
            if state in status["jobs"]:
                status["jobs"][state] += 1
        
        return status

