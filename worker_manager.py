"""Worker management for queuectl."""
import threading
import time
import logging
import signal
import sys
import os
from pathlib import Path
from typing import List, Optional, Dict
from job_manager import JobManager
from executor import Executor
from storage import Storage

logger = logging.getLogger(__name__)

# Stop signal file
STOP_SIGNAL_FILE = os.path.join(os.path.expanduser("~"), ".queuectl", "workers.stop")


class Worker:
    """Single worker thread that processes jobs."""
    
    def __init__(self, worker_id: int, job_manager: JobManager, executor: Executor, stop_event: threading.Event):
        """Initialize worker.
        
        Args:
            worker_id: Unique worker ID
            job_manager: JobManager instance
            executor: Executor instance
            stop_event: Event to signal worker to stop
        """
        self.worker_id = worker_id
        self.job_manager = job_manager
        self.executor = executor
        self.stop_event = stop_event
        self.thread: Optional[threading.Thread] = None
        self.current_job_id: Optional[str] = None
        self.is_running = False
    
    def start(self):
        """Start worker thread."""
        if self.thread and self.thread.is_alive():
            logger.warning(f"Worker {self.worker_id} is already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"Worker {self.worker_id} started")
    
    def stop(self, wait: bool = True):
        """Stop worker.
        
        Args:
            wait: Whether to wait for current job to finish
        """
        self.is_running = False
        self.stop_event.set()
        
        if wait and self.thread and self.thread.is_alive():
            logger.info(f"Worker {self.worker_id} stopping (waiting for current job)...")
            # Wait for current job to finish (with timeout)
            self.thread.join(timeout=30)
            if self.thread.is_alive():
                logger.warning(f"Worker {self.worker_id} did not stop gracefully")
        else:
            logger.info(f"Worker {self.worker_id} stopped")
    
    def _check_stop_signal(self) -> bool:
        """Check if stop signal file exists.
        
        Returns:
            True if stop signal exists
        """
        return Path(STOP_SIGNAL_FILE).exists()
    
    def _run(self):
        """Main worker loop."""
        logger.info(f"Worker {self.worker_id} started processing")
        
        while self.is_running and not self.stop_event.is_set():
            # Check for file-based stop signal
            if self._check_stop_signal():
                logger.info(f"Worker {self.worker_id} received stop signal")
                break
            
            try:
                # Fetch a pending job
                job = self.job_manager.get_pending_job()
                
                if not job:
                    # No jobs available, wait a bit
                    time.sleep(0.5)
                    continue
                
                self.current_job_id = job["id"]
                logger.info(f"Worker {self.worker_id} processing job {self.current_job_id}")
                
                # Execute command
                exit_code, stdout, stderr = self.executor.execute(job["command"])
                
                # Handle result
                if exit_code == 0:
                    self.job_manager.mark_job_completed(self.current_job_id)
                    logger.info(f"Worker {self.worker_id} completed job {self.current_job_id}")
                else:
                    error_msg = f"Exit code {exit_code}"
                    if stderr:
                        error_msg += f": {stderr[:200]}"
                    self.job_manager.mark_job_failed(self.current_job_id, error_msg)
                    logger.warning(f"Worker {self.worker_id} failed job {self.current_job_id}: {error_msg}")
                
                self.current_job_id = None
                
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}", exc_info=True)
                if self.current_job_id:
                    try:
                        self.job_manager.mark_job_failed(self.current_job_id, str(e))
                    except Exception:
                        pass
                    self.current_job_id = None
                time.sleep(1)  # Brief pause before retrying
        
        logger.info(f"Worker {self.worker_id} stopped")


class WorkerManager:
    """Manages multiple worker threads."""
    
    def __init__(self, job_manager: JobManager, executor: Executor):
        """Initialize worker manager.
        
        Args:
            job_manager: JobManager instance
            executor: Executor instance
        """
        self.job_manager = job_manager
        self.executor = executor
        self.workers: List[Worker] = []
        self.stop_event = threading.Event()
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal, stopping workers...")
            self.stop_all(wait=True)
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def start_workers(self, count: int):
        """Start multiple workers.
        
        Args:
            count: Number of workers to start
        """
        # Remove stop signal file if it exists
        stop_file = Path(STOP_SIGNAL_FILE)
        if stop_file.exists():
            stop_file.unlink()
        
        # Stop existing workers first
        self.stop_all(wait=False)
        
        self.stop_event.clear()
        self.workers = []
        
        for i in range(count):
            worker = Worker(i + 1, self.job_manager, self.executor, self.stop_event)
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {count} worker(s)")
    
    def stop_all(self, wait: bool = True):
        """Stop all workers.
        
        Args:
            wait: Whether to wait for current jobs to finish
        """
        # Create stop signal file
        stop_file = Path(STOP_SIGNAL_FILE)
        stop_file.parent.mkdir(parents=True, exist_ok=True)
        stop_file.touch()
        
        self.stop_event.set()
        
        for worker in self.workers:
            worker.stop(wait=wait)
        
        # Wait for all threads to finish
        if wait:
            for worker in self.workers:
                if worker.thread and worker.thread.is_alive():
                    worker.thread.join(timeout=5)
        
        self.workers = []
        logger.info("All workers stopped")
    
    def get_active_workers(self) -> int:
        """Get number of active workers.
        
        Returns:
            Number of active workers
        """
        return sum(1 for w in self.workers if w.is_running and (w.thread and w.thread.is_alive()))
    
    def get_worker_status(self) -> List[Dict]:
        """Get status of all workers.
        
        Returns:
            List of worker status dictionaries
        """
        status = []
        for worker in self.workers:
            status.append({
                "id": worker.worker_id,
                "running": worker.is_running and (worker.thread and worker.thread.is_alive()),
                "current_job": worker.current_job_id
            })
        return status

