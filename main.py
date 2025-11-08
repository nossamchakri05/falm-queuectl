#!/usr/bin/env python3
"""Main CLI entry point for queuectl."""
import json
import sys
import argparse
import logging
from typing import Optional
from storage import Storage
from config_manager import ConfigManager
from job_manager import JobManager
from executor import Executor
from dlq_manager import DLQManager
from worker_manager import WorkerManager

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors by default
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global worker manager instance (for stop command)
_worker_manager: Optional[WorkerManager] = None


def create_managers():
    """Create and initialize all managers."""
    storage = Storage()
    config_manager = ConfigManager(storage)
    job_manager = JobManager(storage, config_manager)
    executor = Executor()
    dlq_manager = DLQManager(storage, job_manager)
    return storage, config_manager, job_manager, executor, dlq_manager


def cmd_enqueue(args):
    """Handle enqueue command."""
    try:
        job_data = json.loads(args.job_data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    
    _, _, job_manager, _, _ = create_managers()
    
    try:
        job = job_manager.enqueue_job(job_data)
        print(f"Enqueued job: {job['id']}")
        print(f"  Command: {job['command']}")
        print(f"  State: {job['state']}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_worker_start(args):
    """Handle worker start command."""
    global _worker_manager
    
    _, config_manager, job_manager, executor, _ = create_managers()
    
    count = args.count or config_manager.get("worker_count") or 1
    
    _worker_manager = WorkerManager(job_manager, executor)
    _worker_manager.start_workers(count)
    
    print(f"Started {count} worker(s)")
    print("Workers are running in the background. Press Ctrl+C to stop.")
    
    # Keep main thread alive
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping workers...")
        _worker_manager.stop_all(wait=True)
        print("Workers stopped")


def cmd_worker_stop(args):
    """Handle worker stop command."""
    import os
    from pathlib import Path
    
    # Use file-based stop signal (works across processes)
    stop_file = Path(os.path.join(os.path.expanduser("~"), ".queuectl", "workers.stop"))
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    stop_file.touch()
    
    print("Stop signal sent to workers. Workers will finish current jobs and stop.")
    
    # Also try to stop in-process workers if available
    global _worker_manager
    if _worker_manager is not None:
        _worker_manager.stop_all(wait=True)
        _worker_manager = None


def cmd_status(args):
    """Handle status command."""
    _, _, job_manager, _, _ = create_managers()
    
    status = job_manager.get_status()
    
    print("Queue Status:")
    print(f"  Jobs:")
    print(f"    Pending: {status['jobs']['pending']}")
    print(f"    Processing: {status['jobs']['processing']}")
    print(f"    Completed: {status['jobs']['completed']}")
    print(f"    Failed: {status['jobs']['failed']}")
    print(f"    Dead: {status['jobs']['dead']}")
    print(f"    Total: {status['jobs']['total']}")
    print(f"  DLQ: {status['dlq']['total']} jobs")


def cmd_list(args):
    """Handle list command."""
    _, _, job_manager, _, _ = create_managers()
    
    jobs = job_manager.list_jobs(state=args.state)
    
    if not jobs:
        state_msg = f" with state '{args.state}'" if args.state else ""
        print(f"No jobs{state_msg}")
        return
    
    print(f"Jobs{(' (state: ' + args.state + ')') if args.state else ''}:")
    for job in jobs:
        print(f"  ID: {job.get('id')}")
        print(f"    Command: {job.get('command')}")
        print(f"    State: {job.get('state')}")
        print(f"    Attempts: {job.get('attempts', 0)}/{job.get('max_retries', 3)}")
        print(f"    Created: {job.get('created_at')}")
        if job.get('next_retry_at'):
            print(f"    Next retry: {job.get('next_retry_at')}")
        print()


def cmd_dlq_list(args):
    """Handle DLQ list command."""
    _, _, _, _, dlq_manager = create_managers()
    
    jobs = dlq_manager.list_jobs()
    print("Dead Letter Queue:")
    print(dlq_manager.format_dlq_jobs(jobs))


def cmd_dlq_retry(args):
    """Handle DLQ retry command."""
    _, _, _, _, dlq_manager = create_managers()
    
    try:
        job = dlq_manager.retry_job(args.job_id)
        print(f"Retried job: {job['id']}")
        print(f"  Command: {job['command']}")
        print(f"  State: {job['state']}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_config_get(args):
    """Handle config get command."""
    _, config_manager, _, _, _ = create_managers()
    
    if args.key:
        value = config_manager.get(args.key)
        if value is None:
            print(f"Configuration key '{args.key}' not found", file=sys.stderr)
            sys.exit(1)
        print(value)
    else:
        print("Configuration:")
        print(config_manager.format_config())


def cmd_config_set(args):
    """Handle config set command."""
    _, config_manager, _, _, _ = create_managers()
    
    # Convert value type
    key = args.key.replace("-", "_")  # Convert kebab-case to snake_case
    
    # Try to parse as int, then float, then keep as string
    value = args.value
    try:
        if "." in value:
            value = float(value)
        else:
            value = int(value)
    except ValueError:
        pass  # Keep as string
    
    try:
        config_manager.set(key, value)
        print(f"Set {args.key} = {value}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="queuectl",
        description="CLI-based background job queue system"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Enqueue command
    enqueue_parser = subparsers.add_parser("enqueue", help="Enqueue a new job")
    enqueue_parser.add_argument("job_data", help="Job data as JSON string")
    
    # Worker commands
    worker_parser = subparsers.add_parser("worker", help="Worker management")
    worker_subparsers = worker_parser.add_subparsers(dest="worker_action")
    
    worker_start_parser = worker_subparsers.add_parser("start", help="Start workers")
    worker_start_parser.add_argument("--count", type=int, help="Number of workers to start")
    
    worker_subparsers.add_parser("stop", help="Stop workers")
    
    # Status command
    subparsers.add_parser("status", help="Show queue status")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument("--state", help="Filter by state (pending, processing, completed, failed, dead)")
    
    # DLQ commands
    dlq_parser = subparsers.add_parser("dlq", help="Dead Letter Queue management")
    dlq_subparsers = dlq_parser.add_subparsers(dest="dlq_action")
    
    dlq_subparsers.add_parser("list", help="List DLQ jobs")
    
    dlq_retry_parser = dlq_subparsers.add_parser("retry", help="Retry a job from DLQ")
    dlq_retry_parser.add_argument("job_id", help="Job ID to retry")
    
    # Config commands
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_action")
    
    config_get_parser = config_subparsers.add_parser("get", help="Get configuration")
    config_get_parser.add_argument("key", nargs="?", help="Configuration key (optional)")
    
    config_set_parser = config_subparsers.add_parser("set", help="Set configuration")
    config_set_parser.add_argument("key", help="Configuration key")
    config_set_parser.add_argument("value", help="Configuration value")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to appropriate command handler
    if args.command == "enqueue":
        cmd_enqueue(args)
    elif args.command == "worker":
        if args.worker_action == "start":
            cmd_worker_start(args)
        elif args.worker_action == "stop":
            cmd_worker_stop(args)
        else:
            worker_parser.print_help()
            sys.exit(1)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "dlq":
        if args.dlq_action == "list":
            cmd_dlq_list(args)
        elif args.dlq_action == "retry":
            cmd_dlq_retry(args)
        else:
            dlq_parser.print_help()
            sys.exit(1)
    elif args.command == "config":
        if args.config_action == "get":
            cmd_config_get(args)
        elif args.config_action == "set":
            cmd_config_set(args)
        else:
            config_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

