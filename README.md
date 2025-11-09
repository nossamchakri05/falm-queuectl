# QueueCTL

A CLI-based background job queue system with support for job enqueueing, worker execution, retries with exponential backoff, and a Dead Letter Queue (DLQ) for failed jobs.

## Features

- ✅ **Interactive Menu UI**: User-friendly terminal menu interface for easy navigation
- ✅ **Job Management**: Enqueue, track, and manage background jobs
- ✅ **Multiple Workers**: Run multiple concurrent workers to process jobs
- ✅ **Automatic Retries**: Exponential backoff retry mechanism for failed jobs
- ✅ **Dead Letter Queue**: Permanent storage for jobs that exceed max retries
- ✅ **Persistent Storage**: JSON-based storage that survives process restarts
- ✅ **Configuration Management**: Configurable retry and backoff settings
- ✅ **Graceful Shutdown**: Workers finish current jobs before stopping
- ✅ **Atomic Job Fetching**: Prevents duplicate job processing
- ✅ **Dual Interface**: Both interactive menu and command-line modes available

## Installation

### Prerequisites

- Python 3.7 or higher
- No external dependencies (uses only Python standard library)

### Setup

1. Clone or download this repository
2. Make `main.py` executable (optional):
   ```bash
   chmod +x main.py
   ```

3. (Optional) Add to PATH or create an alias:
   ```bash
   # Linux/Mac
   alias queuectl="python3 /path/to/QueueCTL/main.py"
   
   # Windows (PowerShell)
   Set-Alias queuectl "python E:\QueueCTL\main.py"
   ```

## Usage

### Interactive Menu Mode (Recommended for Beginners)

The interactive menu provides a user-friendly, guided interface for managing your job queue. It's perfect for interactive use and learning the system.

#### Launching the Interactive Menu

```bash
# Launch interactive menu (default when no command is provided)
python main.py

# Or explicitly
python main.py --interactive
# or
python main.py -i
```

#### Menu Options

The interactive menu displays a numbered list of available operations:

```
============================================================
               QueueCTL - Job Queue Manager
============================================================

  Main Menu:
  --------------------------------------------------------
  1.  Show Queue Status
  2.  List Jobs
  3.  Enqueue New Job
  4.  Start Workers
  5.  Stop Workers
  6.  View Dead Letter Queue (DLQ)
  7.  Retry Job from DLQ
  8.  View Configuration
  9.  Set Configuration
  0.  Exit
  --------------------------------------------------------
```

#### Interactive Menu Features

**1. Show Queue Status**
- Displays a comprehensive overview of the queue
- Shows counts for pending, processing, completed, failed, and dead jobs
- Displays DLQ job count

**2. List Jobs**
- Provides a sub-menu to filter jobs by state:
  - All jobs
  - Pending
  - Processing
  - Completed
  - Failed
  - Dead
- Shows detailed information for each job including ID, command, state, attempts, and timestamps

**3. Enqueue New Job**
- Guided input prompts for:
  - **Job ID**: Optional (auto-generated if left empty)
  - **Command**: Required (the command to execute)
  - **Max Retries**: Optional (defaults to 3)
- Validates input and provides clear error messages

**4. Start Workers**
- Prompts for number of workers (uses default from config if empty)
- Starts workers and keeps them running until interrupted
- Press `Ctrl+C` to stop workers gracefully

**5. Stop Workers**
- Sends stop signal to all running workers
- Workers finish current jobs before stopping

**6. View Dead Letter Queue (DLQ)**
- Lists all jobs in the Dead Letter Queue
- Shows detailed information about permanently failed jobs

**7. Retry Job from DLQ**
- Prompts for Job ID to retry
- Moves job from DLQ back to pending state
- Validates that the job exists in DLQ

**8. View Configuration**
- Option to view all configuration or a specific key
- Shows current settings for max_retries, backoff_base, and worker_count

**9. Set Configuration**
- Displays available configuration keys
- Prompts for key and value
- Validates input and updates configuration

**0. Exit**
- Gracefully exits the interactive menu

#### Example Interactive Session

```
$ python main.py

============================================================
               QueueCTL - Job Queue Manager
============================================================

  Main Menu:
  --------------------------------------------------------
  1.  Show Queue Status
  2.  List Jobs
  3.  Enqueue New Job
  4.  Start Workers
  5.  Stop Workers
  6.  View Dead Letter Queue (DLQ)
  7.  Retry Job from DLQ
  8.  View Configuration
  9.  Set Configuration
  0.  Exit
  --------------------------------------------------------

  Enter your choice (0-9): 1

============================================================
  Queue Status
============================================================
Queue Status:
  Jobs:
    Pending: 5
    Processing: 2
    Completed: 10
    Failed: 1
    Dead: 0
    Total: 18
  DLQ: 0 jobs

  Press Enter to continue...
```

### Command-Line Mode

For automation and scripting, you can use the command-line interface directly:

### Enqueue a Job

**Linux/Mac:**
```bash
queuectl enqueue '{"id":"job1","command":"echo Hello World"}'
```

**Windows (PowerShell):**
```powershell
# Method 1: Use escaped quotes (recommended)
python main.py enqueue '{\"id\":\"job1\",\"command\":\"echo Hello World\"}'

# Method 2: Use a JSON file (easiest for complex jobs)
python main.py enqueue --file job.json
```

Or let the system generate an ID:
```bash
# Linux/Mac
queuectl enqueue '{"command":"sleep 2"}'

# Windows PowerShell
python main.py enqueue '{\"command\":\"sleep 2\"}'
```

### Start Workers

Start 3 workers:
```bash
queuectl worker start --count 3
```

Start with default worker count (from config):
```bash
queuectl worker start
```

Workers run in the foreground. Press `Ctrl+C` to stop gracefully.

### Stop Workers

```bash
queuectl worker stop
```

### Check Status

```bash
queuectl status
```

Output:
```
Queue Status:
  Jobs:
    Pending: 5
    Processing: 2
    Completed: 10
    Failed: 1
    Dead: 0
    Total: 18
  DLQ: 0 jobs
```

### List Jobs

List all jobs:
```bash
queuectl list
```

Filter by state:
```bash
queuectl list --state pending
queuectl list --state processing
queuectl list --state completed
queuectl list --state failed
queuectl list --state dead
```

### Dead Letter Queue

List jobs in DLQ:
```bash
queuectl dlq list
```

Retry a job from DLQ:
```bash
queuectl dlq retry job1
```

### Configuration

View configuration:
```bash
queuectl config get
```

Get specific config value:
```bash
queuectl config get max_retries
```

Set configuration:
```bash
queuectl config set max-retries 5
queuectl config set backoff-base 3.0
queuectl config set worker-count 4
```

## Architecture

### Components

```
┌─────────────┐
│   main.py   │  CLI Entry Point
└──────┬──────┘
       │
       ├─── job_manager.py      Job lifecycle & state management
       ├─── worker_manager.py   Worker threads & coordination
       ├─── executor.py         Command execution
       ├─── dlq_manager.py      Dead Letter Queue operations
       ├─── config_manager.py   Configuration management
       ├─── storage.py          Persistent JSON storage
       └─── utils.py            Helper utilities
```

### Job Lifecycle

```
┌─────────┐
│ pending │  Job is enqueued
└────┬────┘
     │ Worker picks up job
     ▼
┌────────────┐
│ processing │  Job is being executed
└────┬───────┘
     │
     ├─── Exit code 0 ────► ┌───────────┐
     │                      │ completed │
     │                      └───────────┘
     │
     └─── Exit code != 0 ──► ┌────────┐
                             │ failed  │
                             └────┬────┘
                                  │
                                  ├─── attempts < max_retries ──► ┌─────────┐
                                  │                                │ pending │ (with backoff)
                                  │                                └─────────┘
                                  │
                                  └─── attempts >= max_retries ──► ┌──────┐
                                                                    │ dead │ (DLQ)
                                                                    └──────┘
```

### Job States

- **pending**: Waiting to be processed
- **processing**: Currently being executed by a worker
- **completed**: Successfully executed
- **failed**: Failed but eligible for retry
- **dead**: Permanently failed (moved to DLQ)

### Retry Mechanism

Failed jobs are retried with exponential backoff:

```
delay = base ^ attempts
```

Where:
- `base` = configurable (default: 2 seconds)
- `attempts` = number of failed attempts (1-indexed: 1, 2, 3, ...)

Example with `base=2`:
- Attempt 1: 2^1 = 2 seconds
- Attempt 2: 2^2 = 4 seconds
- Attempt 3: 2^3 = 8 seconds
- Attempt 4: 2^4 = 16 seconds

### Storage

Jobs are persisted to `~/.queuectl/data.json` with the following structure:

```json
{
  "jobs": [
    {
      "id": "unique-job-id",
      "command": "echo 'Hello World'",
      "state": "pending",
      "attempts": 0,
      "max_retries": 3,
      "created_at": "2025-11-04T10:30:00Z",
      "updated_at": "2025-11-04T10:30:00Z",
      "next_retry_at": null
    }
  ],
  "config": {
    "max_retries": 3,
    "backoff_base": 2.0,
    "worker_count": 1
  },
  "dlq": []
}
```

### Concurrency & Locking

- **Thread-based workers**: Workers run in separate threads within the same process
- **Thread locks**: Storage operations use thread locks to prevent race conditions
- **Atomic job fetching**: Jobs are atomically updated from `pending` to `processing` to prevent duplicate processing
- **File locking**: On Unix systems, file-level locking (fcntl) provides additional protection

## Testing Scenarios

### 1. Basic Job Execution

**Using Interactive Menu:**
```bash
python main.py
# Choose option 3 (Enqueue New Job)
# Enter: Job ID: test1, Command: echo Success
# Choose option 4 (Start Workers)
# Enter: Number of workers: 1
# In another terminal, choose option 1 (Show Queue Status)
```

**Using Command Line:**
```bash
# Enqueue a simple job
queuectl enqueue '{"id":"test1","command":"echo Success"}'

# Start a worker
queuectl worker start --count 1

# Check status (in another terminal)
queuectl status
queuectl list --state completed
```

### 2. Failed Job Retry

**Using Interactive Menu:**
```bash
python main.py
# Choose option 3 (Enqueue New Job)
# Enter: Job ID: test2, Command: exit 1, Max retries: 3
# Choose option 4 (Start Workers)
# Choose option 2 (List Jobs) -> option 5 (Failed) to check status
```

**Using Command Line:**
```bash
# Enqueue a job that will fail
queuectl enqueue '{"id":"test2","command":"exit 1","max_retries":3}'

# Start worker and observe retries
queuectl worker start --count 1

# Check job status
queuectl list --state failed
```

### 3. DLQ Movement

**Using Interactive Menu:**
```bash
python main.py
# Choose option 3 (Enqueue New Job)
# Enter: Job ID: test3, Command: exit 1, Max retries: 2
# Choose option 4 (Start Workers)
# Wait for retries to exhaust, then choose option 6 (View DLQ)
```

**Using Command Line:**
```bash
# Enqueue a job that will fail permanently
queuectl enqueue '{"id":"test3","command":"exit 1","max_retries":2}'

# Start worker
queuectl worker start --count 1

# Wait for retries to exhaust, then check DLQ
queuectl dlq list
```

### 4. DLQ Retry

**Using Interactive Menu:**
```bash
python main.py
# Choose option 7 (Retry Job from DLQ)
# Enter: Job ID: test3
# Choose option 2 (List Jobs) -> option 2 (Pending) to verify
```

**Using Command Line:**
```bash
# Retry a job from DLQ
queuectl dlq retry test3

# Job should be back in pending state
queuectl list --state pending
```

### 5. Multiple Workers

```bash
# Enqueue multiple jobs
queuectl enqueue '{"id":"job1","command":"sleep 1"}'
queuectl enqueue '{"id":"job2","command":"sleep 1"}'
queuectl enqueue '{"id":"job3","command":"sleep 1"}'

# Start 3 workers
queuectl worker start --count 3

# Jobs should be processed concurrently
```

### 6. Persistence

```bash
# Enqueue jobs
queuectl enqueue '{"id":"persist1","command":"echo test"}'

# Stop workers
queuectl worker stop

# Restart workers - jobs should still be there
queuectl worker start --count 1
```

### 7. Configuration

**Using Interactive Menu:**
```bash
python main.py
# Choose option 8 (View Configuration) to see all settings
# Choose option 9 (Set Configuration)
# Enter: Key: max-retries, Value: 5
# Enter: Key: backoff-base, Value: 3.0
# Choose option 8 again to verify changes
```

**Using Command Line:**
```bash
# View config
queuectl config get

# Update config
queuectl config set max-retries 5
queuectl config set backoff-base 3.0

# Verify
queuectl config get
```

## Assumptions & Trade-offs

### Design Decisions

1. **JSON File Storage**: 
   - **Pros**: Simple, human-readable, no external dependencies
   - **Cons**: Not ideal for high-throughput scenarios (1000s of jobs/second)
   - **Trade-off**: Chosen for simplicity and portability

2. **Thread-based Workers**:
   - **Pros**: Simple implementation, shared memory, easy coordination
   - **Cons**: Limited by Python's GIL for CPU-bound tasks
   - **Trade-off**: Suitable for I/O-bound job execution (shell commands)

3. **Thread Locks for Storage**:
   - **Pros**: Simple, sufficient for single-process scenarios
   - **Cons**: Doesn't protect against multiple processes
   - **Trade-off**: Added file locking (fcntl) on Unix for additional protection

4. **Exponential Backoff**:
   - **Formula**: `base ^ attempts` (not `base * 2^attempts`)
   - **Rationale**: Simpler formula, still provides exponential growth
   - **Trade-off**: Slightly different from traditional exponential backoff

5. **Graceful Shutdown**:
   - Workers finish current job before stopping
   - 30-second timeout for graceful shutdown
   - **Trade-off**: Balance between responsiveness and job completion

6. **Command Execution**:
   - Uses `subprocess` with `shell=True` for cross-platform compatibility
   - **Trade-off**: Security consideration (user should validate commands)

### Limitations

1. **Single Process**: Workers run in the same process. For distributed systems, consider using a message queue (Redis, RabbitMQ, etc.)

2. **No Job Priority**: Jobs are processed in FIFO order. Priority queues could be added as an enhancement.

3. **No Job Timeout**: Jobs can run indefinitely. Timeout feature could be added.

4. **No Scheduled Jobs**: Jobs execute immediately when picked up. Cron-like scheduling could be added.

5. **No Job Output Storage**: stdout/stderr are not persisted. Could be added for debugging.

6. **Limited Scalability**: JSON file storage doesn't scale to thousands of concurrent operations.

## File Structure

```
QueueCTL/
├── main.py              # CLI entry point with interactive menu
├── job_manager.py       # Job lifecycle management
├── worker_manager.py    # Worker thread management
├── executor.py          # Command execution
├── dlq_manager.py       # Dead Letter Queue operations
├── config_manager.py    # Configuration management
├── storage.py           # Persistent storage layer
├── utils.py             # Utility functions
├── requirements.txt     # Dependencies (none required)
├── README.md           # This file
└── CHECKLIST_VERIFICATION_RESULTS.md  # Test results
```

### Main Components

- **main.py**: Entry point that provides both interactive menu and command-line interfaces
- **job_manager.py**: Manages job lifecycle, state transitions, and job operations
- **worker_manager.py**: Handles worker thread creation, coordination, and lifecycle
- **executor.py**: Executes shell commands for jobs
- **dlq_manager.py**: Manages Dead Letter Queue operations
- **config_manager.py**: Handles configuration storage and retrieval
- **storage.py**: Provides persistent JSON-based storage with thread safety

## Troubleshooting

### Workers Not Processing Jobs

**Using Interactive Menu:**
1. Launch menu: `python main.py`
2. Choose option 1 (Show Queue Status) to check current state
3. Choose option 2 (List Jobs) -> option 2 (Pending) to verify jobs
4. Choose option 4 (Start Workers) to start processing

**Using Command Line:**
1. Check if workers are running: `queuectl status`
2. Verify jobs are in pending state: `queuectl list --state pending`
3. Check for errors in logs (enable logging: set `logging.basicConfig(level=logging.INFO)`)

### Jobs Stuck in Processing

If a worker crashes, jobs may remain in `processing` state. 

**Using Interactive Menu:**
1. Launch menu: `python main.py`
2. Choose option 2 (List Jobs) -> option 3 (Processing) to see stuck jobs
3. Restart workers: Choose option 5 (Stop Workers), then option 4 (Start Workers)

**Using Command Line:**
- Check stuck jobs: `queuectl list --state processing`
- Restart workers: `queuectl worker stop` then `queuectl worker start`

Jobs will be retried based on their state when workers restart.

### Storage File Issues

Storage file is located at `~/.queuectl/data.json`. If corrupted:
1. Backup the file
2. Delete it (will be recreated with defaults)
3. Or manually fix JSON syntax

## License

This project is provided as-is for educational and demonstration purposes.

## Quick Start Guide

### First Time Users

1. **Launch the Interactive Menu:**
   ```bash
   python main.py
   ```

2. **Check Queue Status:**
   - Choose option `1` to see the current state of your queue

3. **Enqueue Your First Job:**
   - Choose option `3`
   - Enter a command (e.g., `echo "Hello World"`)
   - Leave Job ID empty to auto-generate one
   - Press Enter for default max retries (3)

4. **Start Workers:**
   - Choose option `4`
   - Enter number of workers (or press Enter for default)
   - Workers will process jobs automatically

5. **Monitor Jobs:**
   - Use option `1` to check status
   - Use option `2` to list jobs by state

### Advanced Users

For automation and scripting, use the command-line interface directly. All commands work the same way as the interactive menu, but can be scripted and automated.

## Contributing

This is a demonstration project. For production use, consider:
- Using a proper database (PostgreSQL, MongoDB)
- Implementing distributed workers (Celery, RQ)
- Adding job priorities and scheduling
- Implementing job timeouts
- Adding metrics and monitoring
- Enhancing the interactive menu with more features

