"""Dead Letter Queue management for queuectl."""
import logging
from typing import List, Dict, Any
from storage import Storage
from job_manager import JobManager
from utils import get_current_timestamp

logger = logging.getLogger(__name__)


class DLQManager:
    """Manages Dead Letter Queue operations."""
    
    def __init__(self, storage: Storage, job_manager: JobManager):
        """Initialize DLQ manager.
        
        Args:
            storage: Storage instance
            job_manager: JobManager instance
        """
        self.storage = storage
        self.job_manager = job_manager
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs in DLQ.
        
        Returns:
            List of DLQ jobs
        """
        return self.storage.get_dlq_jobs()
    
    def retry_job(self, job_id: str) -> Dict[str, Any]:
        """Retry a job from DLQ by moving it back to pending state.
        
        Args:
            job_id: Job ID to retry
        
        Returns:
            Retried job dictionary
        """
        # Remove from DLQ
        job = self.storage.remove_from_dlq(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in DLQ")
        
        # Reset job state and add back to jobs
        now = get_current_timestamp()
        job["state"] = JobManager.STATE_PENDING
        job["attempts"] = 0  # Reset attempts
        job["next_retry_at"] = None
        job["updated_at"] = now
        job.pop("last_error", None)
        
        # Add back to jobs queue
        self.storage.add_job(job)
        logger.info(f"Retried job {job_id} from DLQ")
        return job
    
    def format_dlq_jobs(self, jobs: List[Dict[str, Any]]) -> str:
        """Format DLQ jobs for display.
        
        Args:
            jobs: List of DLQ jobs
        
        Returns:
            Formatted string
        """
        if not jobs:
            return "No jobs in DLQ"
        
        lines = []
        for job in jobs:
            lines.append(f"  ID: {job.get('id')}")
            lines.append(f"    Command: {job.get('command')}")
            lines.append(f"    Attempts: {job.get('attempts', 0)}/{job.get('max_retries', 3)}")
            lines.append(f"    Failed at: {job.get('updated_at')}")
            if job.get('last_error'):
                lines.append(f"    Error: {job.get('last_error')}")
            lines.append("")
        
        return "\n".join(lines)



