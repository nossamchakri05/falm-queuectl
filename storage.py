"""Persistent storage layer for queuectl."""
import json
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from threading import Lock

logger = logging.getLogger(__name__)

# Default storage file
DEFAULT_STORAGE_FILE = os.path.join(os.path.expanduser("~"), ".queuectl", "data.json")

# Try to import fcntl (Unix) or use alternative for Windows
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


class Storage:
    """JSON-based persistent storage with file locking."""
    
    def __init__(self, storage_file: str = DEFAULT_STORAGE_FILE):
        """Initialize storage.
        
        Args:
            storage_file: Path to JSON storage file
        """
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._ensure_storage_file()
    
    def _ensure_storage_file(self):
        """Ensure storage file exists with default structure."""
        if not self.storage_file.exists():
            self._write_data({
                "jobs": [],
                "config": {
                    "max_retries": 3,
                    "backoff_base": 2.0,
                    "worker_count": 1
                },
                "dlq": []
            })
    
    def _read_data(self) -> Dict[str, Any]:
        """Read data from storage file with locking."""
        with self._lock:
            try:
                with open(self.storage_file, 'r') as f:
                    # Use fcntl on Unix, thread lock is sufficient on Windows for single-process
                    if HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                        try:
                            data = json.load(f)
                        finally:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    else:
                        # Windows: thread lock provides sufficient protection
                        data = json.load(f)
                    return data
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning("Storage file corrupted or missing, reinitializing")
                self._ensure_storage_file()
                return self._read_data()
    
    def _write_data(self, data: Dict[str, Any]):
        """Write data to storage file with locking."""
        with self._lock:
            # Write to temporary file first, then rename (atomic on most systems)
            temp_file = self.storage_file.with_suffix('.tmp')
            try:
                with open(temp_file, 'w') as f:
                    # Use fcntl on Unix, thread lock is sufficient on Windows for single-process
                    if HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        try:
                            json.dump(data, f, indent=2)
                        finally:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    else:
                        # Windows: thread lock provides sufficient protection
                        json.dump(data, f, indent=2)
                
                # Atomic rename
                temp_file.replace(self.storage_file)
            except Exception as e:
                logger.error(f"Error writing to storage: {e}")
                if temp_file.exists():
                    temp_file.unlink()
                raise
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs."""
        data = self._read_data()
        return data.get("jobs", [])
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job by ID."""
        jobs = self.get_all_jobs()
        for job in jobs:
            if job.get("id") == job_id:
                return job
        return None
    
    def add_job(self, job: Dict[str, Any]):
        """Add a new job."""
        data = self._read_data()
        jobs = data.get("jobs", [])
        
        # Check if job ID already exists
        if any(j.get("id") == job.get("id") for j in jobs):
            raise ValueError(f"Job with ID {job.get('id')} already exists")
        
        jobs.append(job)
        data["jobs"] = jobs
        self._write_data(data)
        logger.info(f"Added job {job.get('id')}")
    
    def update_job(self, job_id: str, updates: Dict[str, Any]):
        """Update a job."""
        data = self._read_data()
        jobs = data.get("jobs", [])
        
        for i, job in enumerate(jobs):
            if job.get("id") == job_id:
                jobs[i].update(updates)
                jobs[i]["updated_at"] = updates.get("updated_at", jobs[i].get("updated_at"))
                data["jobs"] = jobs
                self._write_data(data)
                logger.debug(f"Updated job {job_id}")
                return
        
        raise ValueError(f"Job {job_id} not found")
    
    def delete_job(self, job_id: str):
        """Delete a job."""
        data = self._read_data()
        jobs = data.get("jobs", [])
        jobs = [j for j in jobs if j.get("id") != job_id]
        data["jobs"] = jobs
        self._write_data(data)
        logger.info(f"Deleted job {job_id}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration."""
        data = self._read_data()
        return data.get("config", {
            "max_retries": 3,
            "backoff_base": 2.0,
            "worker_count": 1
        })
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration."""
        data = self._read_data()
        config = data.get("config", {})
        config.update(updates)
        data["config"] = config
        self._write_data(data)
        logger.info(f"Updated config: {updates}")
    
    def get_dlq_jobs(self) -> List[Dict[str, Any]]:
        """Get all DLQ jobs."""
        data = self._read_data()
        return data.get("dlq", [])
    
    def add_to_dlq(self, job: Dict[str, Any]):
        """Add a job to DLQ."""
        data = self._read_data()
        dlq = data.get("dlq", [])
        dlq.append(job)
        data["dlq"] = dlq
        self._write_data(data)
        logger.info(f"Added job {job.get('id')} to DLQ")
    
    def remove_from_dlq(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Remove a job from DLQ and return it."""
        data = self._read_data()
        dlq = data.get("dlq", [])
        for i, job in enumerate(dlq):
            if job.get("id") == job_id:
                removed_job = dlq.pop(i)
                data["dlq"] = dlq
                self._write_data(data)
                logger.info(f"Removed job {job_id} from DLQ")
                return removed_job
        return None

