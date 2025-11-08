# QueueCTL

A CLI-based background job queue system with support for job enqueueing, worker execution, retries with exponential backoff, and a Dead Letter Queue (DLQ) for failed jobs.

## Features

- ✅ **Job Management**: Enqueue, track, and manage background jobs
- ✅ **Multiple Workers**: Run multiple concurrent workers to process jobs
- ✅ **Automatic Retries**: Exponential backoff retry mechanism for failed jobs
- ✅ **Dead Letter Queue**: Permanent storage for jobs that exceed max retries
- ✅ **Persistent Storage**: JSON-based storage that survives process restarts
- ✅ **Configuration Management**: Configurable retry and backoff settings
- ✅ **Graceful Shutdown**: Workers finish current jobs before stopping
- ✅ **Atomic Job Fetching**: Prevents duplicate job processing

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

### Enqueue a Job

**Linux/Mac:**
```bash
queuectl enqueue '{"id":"job1","command":"echo Hello World"}'
```

**Windows (PowerShell):**
```powershell
python main.py enqueue '{\"id\":\"job1\",\"command\":\"echo Hello World\"}'
```

Or let the system generate an ID:
```bash
# Linux/Mac
queuectl enqueue '{"command":"sleep 2"}'

# Windows
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

```bash
# Enqueue a job that will fail
queuectl enqueue '{"id":"test2","command":"exit 1","max_retries":3}'

# Start worker and observe retries
queuectl worker start --count 1

# Check job status
queuectl list --state failed
```

### 3. DLQ Movement

```bash
# Enqueue a job that will fail permanently
queuectl enqueue '{"id":"test3","command":"exit 1","max_retries":2}'

# Start worker
queuectl worker start --count 1

# Wait for retries to exhaust, then check DLQ
queuectl dlq list
```

### 4. DLQ Retry

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
├── main.py              # CLI entry point
├── job_manager.py       # Job lifecycle management
├── worker_manager.py    # Worker thread management
├── executor.py          # Command execution
├── dlq_manager.py       # Dead Letter Queue operations
├── config_manager.py    # Configuration management
├── storage.py           # Persistent storage layer
├── utils.py             # Utility functions
├── requirements.txt     # Dependencies (none required)
└── README.md           # This file
```

## Troubleshooting

### Workers Not Processing Jobs

1. Check if workers are running: `queuectl status`
2. Verify jobs are in pending state: `queuectl list --state pending`
3. Check for errors in logs (enable logging: set `logging.basicConfig(level=logging.INFO)`)

### Jobs Stuck in Processing

If a worker crashes, jobs may remain in `processing` state. You can manually update them or restart the system (jobs will be retried based on their state).

### Storage File Issues

Storage file is located at `~/.queuectl/data.json`. If corrupted:
1. Backup the file
2. Delete it (will be recreated with defaults)
3. Or manually fix JSON syntax

## License

This project is provided as-is for educational and demonstration purposes.

## Contributing

This is a demonstration project. For production use, consider:
- Using a proper database (PostgreSQL, MongoDB)
- Implementing distributed workers (Celery, RQ)
- Adding job priorities and scheduling
- Implementing job timeouts
- Adding metrics and monitoring

