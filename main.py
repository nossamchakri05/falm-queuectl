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
    # If --file option is provided, read from file
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                job_data_str = f.read().strip()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Join job_data parts in case it was split by shell (Windows PowerShell issue)
        if isinstance(args.job_data, list):
            job_data_str = ' '.join(args.job_data)
        else:
            job_data_str = args.job_data
        
        # Remove surrounding quotes if present (PowerShell sometimes adds them)
        job_data_str = job_data_str.strip().strip('"\'')
    
    try:
        job_data = json.loads(job_data_str)
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


def clear_screen():
    """Clear the terminal screen."""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')


def print_menu():
    """Display the main menu."""
    print("\n" + "="*60)
    print(" " * 15 + "QueueCTL - Job Queue Manager")
    print("="*60)
    print("\n  Main Menu:")
    print("  " + "-"*56)
    print("  1.  Show Queue Status")
    print("  2.  List Jobs")
    print("  3.  Enqueue New Job")
    print("  4.  Start Workers")
    print("  5.  Stop Workers")
    print("  6.  View Dead Letter Queue (DLQ)")
    print("  7.  Retry Job from DLQ")
    print("  8.  View Configuration")
    print("  9.  Set Configuration")
    print("  0.  Exit")
    print("  " + "-"*56)


def interactive_menu():
    """Interactive menu-driven interface."""
    global _worker_manager
    
    while True:
        print_menu()
        try:
            choice = input("\n  Enter your choice (0-9): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nExiting...")
            break
        
        if choice == "0":
            print("\n  Goodbye!")
            break
        elif choice == "1":
            # Show Status
            print("\n" + "="*60)
            print("  Queue Status")
            print("="*60)
            args = argparse.Namespace()
            cmd_status(args)
            input("\n  Press Enter to continue...")
        elif choice == "2":
            # List Jobs
            print("\n" + "="*60)
            print("  List Jobs")
            print("="*60)
            print("\n  Filter by state (optional):")
            print("  1. All jobs")
            print("  2. Pending")
            print("  3. Processing")
            print("  4. Completed")
            print("  5. Failed")
            print("  6. Dead")
            
            state_choice = input("\n  Enter choice (1-6, default: 1): ").strip()
            state_map = {
                "1": None,
                "2": "pending",
                "3": "processing",
                "4": "completed",
                "5": "failed",
                "6": "dead"
            }
            state = state_map.get(state_choice, None)
            
            args = argparse.Namespace(state=state)
            cmd_list(args)
            input("\n  Press Enter to continue...")
        elif choice == "3":
            # Enqueue Job
            print("\n" + "="*60)
            print("  Enqueue New Job")
            print("="*60)
            print("\n  Enter job details:")
            
            job_id = input("  Job ID (leave empty to auto-generate): ").strip()
            command = input("  Command to execute: ").strip()
            
            if not command:
                print("  Error: Command is required!", file=sys.stderr)
                input("\n  Press Enter to continue...")
                continue
            
            max_retries_input = input("  Max retries (default: 3, press Enter for default): ").strip()
            max_retries = int(max_retries_input) if max_retries_input else 3
            
            # Build job data
            job_data = {"command": command, "max_retries": max_retries}
            if job_id:
                job_data["id"] = job_id
            
            # Create args object
            args = argparse.Namespace()
            args.file = None
            args.job_data = json.dumps(job_data)
            
            try:
                cmd_enqueue(args)
            except SystemExit:
                pass  # Error already printed
            
            input("\n  Press Enter to continue...")
        elif choice == "4":
            # Start Workers
            print("\n" + "="*60)
            print("  Start Workers")
            print("="*60)
            
            count_input = input("\n  Number of workers (press Enter for default): ").strip()
            count = int(count_input) if count_input else None
            
            args = argparse.Namespace(count=count)
            
            print("\n  Starting workers...")
            try:
                cmd_worker_start(args)
            except KeyboardInterrupt:
                print("\n  Workers stopped by user.")
            except SystemExit:
                pass
        elif choice == "5":
            # Stop Workers
            print("\n" + "="*60)
            print("  Stop Workers")
            print("="*60)
            
            args = argparse.Namespace()
            cmd_worker_stop(args)
            input("\n  Press Enter to continue...")
        elif choice == "6":
            # View DLQ
            print("\n" + "="*60)
            print("  Dead Letter Queue")
            print("="*60)
            
            args = argparse.Namespace()
            cmd_dlq_list(args)
            input("\n  Press Enter to continue...")
        elif choice == "7":
            # Retry Job from DLQ
            print("\n" + "="*60)
            print("  Retry Job from DLQ")
            print("="*60)
            
            job_id = input("\n  Enter Job ID to retry: ").strip()
            if not job_id:
                print("  Error: Job ID is required!", file=sys.stderr)
                input("\n  Press Enter to continue...")
                continue
            
            args = argparse.Namespace(job_id=job_id)
            try:
                cmd_dlq_retry(args)
            except SystemExit:
                pass  # Error already printed
            
            input("\n  Press Enter to continue...")
        elif choice == "8":
            # View Configuration
            print("\n" + "="*60)
            print("  View Configuration")
            print("="*60)
            
            key = input("\n  Configuration key (press Enter for all): ").strip()
            key = key if key else None
            
            args = argparse.Namespace(key=key)
            try:
                cmd_config_get(args)
            except SystemExit:
                pass  # Error already printed
            
            input("\n  Press Enter to continue...")
        elif choice == "9":
            # Set Configuration
            print("\n" + "="*60)
            print("  Set Configuration")
            print("="*60)
            print("\n  Available configuration keys:")
            print("    - max-retries (integer)")
            print("    - backoff-base (float)")
            print("    - worker-count (integer)")
            
            key = input("\n  Configuration key: ").strip()
            if not key:
                print("  Error: Configuration key is required!", file=sys.stderr)
                input("\n  Press Enter to continue...")
                continue
            
            value = input("  Configuration value: ").strip()
            if not value:
                print("  Error: Configuration value is required!", file=sys.stderr)
                input("\n  Press Enter to continue...")
                continue
            
            args = argparse.Namespace(key=key, value=value)
            try:
                cmd_config_set(args)
            except SystemExit:
                pass  # Error already printed
            
            input("\n  Press Enter to continue...")
        else:
            print("\n  Invalid choice! Please enter a number between 0-9.")
            input("\n  Press Enter to continue...")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="queuectl",
        description="CLI-based background job queue system"
    )
    
    parser.add_argument("--interactive", "-i", action="store_true", 
                       help="Launch interactive menu interface")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Enqueue command
    enqueue_parser = subparsers.add_parser("enqueue", help="Enqueue a new job")
    enqueue_parser.add_argument("job_data", nargs=argparse.REMAINDER, help="Job data as JSON string")
    enqueue_parser.add_argument("--file", "-f", help="Read job data from a JSON file instead of command line")
    
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
    
    # Launch interactive menu if requested or no command provided
    if args.interactive or (hasattr(args, 'command') and not args.command):
        interactive_menu()
        return
    
    if not hasattr(args, 'command') or not args.command:
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

