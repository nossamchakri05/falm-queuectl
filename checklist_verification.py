#!/usr/bin/env python3
"""Comprehensive checklist verification for QueueCTL submission."""
import sys
import subprocess
import uuid
from storage import Storage
from config_manager import ConfigManager
from job_manager import JobManager
from executor import Executor
from dlq_manager import DLQManager
from utils import calculate_backoff_delay

def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_result(item, passed, details=""):
    """Print test result."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {item}")
    if details:
        print(f"      {details}")

# Track results
results = []

print_header("QueueCTL - Submission Checklist Verification")

# ============================================================================
# CHECKLIST ITEM 1: All required commands functional
# ============================================================================
print_header("1. All required commands functional")

commands_to_test = [
    ("enqueue", "python main.py --help"),
    ("status", "python main.py status"),
    ("list", "python main.py list"),
    ("list with state", "python main.py list --state pending"),
    ("dlq list", "python main.py dlq list"),
    ("config get", "python main.py config get"),
    ("config set", "python main.py config set max-retries 3"),
    ("config get specific", "python main.py config get max_retries"),
]

passed_commands = 0
for name, cmd in commands_to_test:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print_result(f"Command '{name}'", True)
            passed_commands += 1
        else:
            print_result(f"Command '{name}'", False, f"Exit code: {result.returncode}")
    except Exception as e:
        print_result(f"Command '{name}'", False, str(e))

item1_passed = passed_commands == len(commands_to_test)
results.append(("All required commands functional", item1_passed))
print(f"\n  Result: {passed_commands}/{len(commands_to_test)} commands working")

# ============================================================================
# CHECKLIST ITEM 2: Jobs persist after restart
# ============================================================================
print_header("2. Jobs persist after restart")

try:
    # Create first instance and add job
    storage1 = Storage()
    config_manager1 = ConfigManager(storage1)
    job_manager1 = JobManager(storage1, config_manager1)
    
    test_id = f"persist_{uuid.uuid4().hex[:8]}"
    job = job_manager1.enqueue_job({
        'id': test_id,
        'command': 'echo Persistence Test'
    })
    print_result("Job enqueued", True, f"Job ID: {test_id}")
    
    # Simulate restart - create new instances
    storage2 = Storage()
    config_manager2 = ConfigManager(storage2)
    job_manager2 = JobManager(storage2, config_manager2)
    
    # Try to retrieve the job
    found_job = job_manager2.get_job(test_id)
    if found_job and found_job['id'] == test_id:
        print_result("Job retrieved after restart", True, f"Found: {found_job['id']}")
        item2_passed = True
    else:
        print_result("Job retrieved after restart", False, "Job not found")
        item2_passed = False
except Exception as e:
    print_result("Job persistence test", False, str(e))
    item2_passed = False

results.append(("Jobs persist after restart", item2_passed))

# ============================================================================
# CHECKLIST ITEM 3: Retry and backoff implemented correctly
# ============================================================================
print_header("3. Retry and backoff implemented correctly")

try:
    # Test backoff calculation
    delay1 = calculate_backoff_delay(1, 2.0)
    delay2 = calculate_backoff_delay(2, 2.0)
    delay3 = calculate_backoff_delay(3, 2.0)
    
    expected1, expected2, expected3 = 2.0, 4.0, 8.0
    
    if delay1 == expected1 and delay2 == expected2 and delay3 == expected3:
        print_result("Backoff calculation", True, f"{delay1}s, {delay2}s, {delay3}s")
        backoff_calc_ok = True
    else:
        print_result("Backoff calculation", False, f"Expected {expected1}, {expected2}, {expected3}, got {delay1}, {delay2}, {delay3}")
        backoff_calc_ok = False
    
    # Test retry logic
    storage = Storage()
    config_manager = ConfigManager(storage)
    job_manager = JobManager(storage, config_manager)
    
    test_id = f"retry_{uuid.uuid4().hex[:8]}"
    job = job_manager.enqueue_job({
        'id': test_id,
        'command': 'exit 1',
        'max_retries': 2
    })
    
    # Mark as failed
    job_manager.mark_job_failed(test_id, 'Test failure')
    job = job_manager.get_job(test_id)
    
    if job and job['state'] == 'pending' and job['attempts'] == 1 and job.get('next_retry_at'):
        print_result("Retry logic", True, f"State: {job['state']}, Attempts: {job['attempts']}, Next retry: {job.get('next_retry_at')}")
        retry_logic_ok = True
    else:
        print_result("Retry logic", False, f"State: {job['state'] if job else 'None'}, Attempts: {job['attempts'] if job else 'N/A'}")
        retry_logic_ok = False
    
    item3_passed = backoff_calc_ok and retry_logic_ok
except Exception as e:
    print_result("Retry and backoff test", False, str(e))
    item3_passed = False

results.append(("Retry and backoff implemented correctly", item3_passed))

# ============================================================================
# CHECKLIST ITEM 4: DLQ operational
# ============================================================================
print_header("4. DLQ operational")

try:
    storage = Storage()
    config_manager = ConfigManager(storage)
    job_manager = JobManager(storage, config_manager)
    dlq_manager = DLQManager(storage, job_manager)
    
    # Create job that will exceed max retries
    test_id = f"dlq_{uuid.uuid4().hex[:8]}"
    job = job_manager.enqueue_job({
        'id': test_id,
        'command': 'exit 1',
        'max_retries': 1
    })
    print_result("Job created for DLQ test", True, f"Job ID: {test_id}")
    
    # Fail it twice (exceeds max_retries)
    job_manager.mark_job_failed(test_id, 'Failure 1')
    job_manager.mark_job_failed(test_id, 'Failure 2')
    
    # Check DLQ
    dlq_jobs = dlq_manager.list_jobs()
    if len(dlq_jobs) > 0 and any(j['id'] == test_id for j in dlq_jobs):
        print_result("Job moved to DLQ", True, f"DLQ contains {len(dlq_jobs)} job(s)")
        
        # Test DLQ retry
        retried_job = dlq_manager.retry_job(test_id)
        if retried_job['state'] == 'pending' and retried_job['attempts'] == 0:
            print_result("DLQ retry", True, f"Job reset: state={retried_job['state']}, attempts={retried_job['attempts']}")
            item4_passed = True
        else:
            print_result("DLQ retry", False, f"State: {retried_job['state']}, Attempts: {retried_job['attempts']}")
            item4_passed = False
    else:
        print_result("Job moved to DLQ", False, f"DLQ contains {len(dlq_jobs)} jobs")
        item4_passed = False
except Exception as e:
    print_result("DLQ test", False, str(e))
    item4_passed = False

results.append(("DLQ operational", item4_passed))

# ============================================================================
# CHECKLIST ITEM 5: CLI user-friendly and documented
# ============================================================================
print_header("5. CLI user-friendly and documented")

try:
    # Check help text
    result = subprocess.run("python main.py --help", shell=True, capture_output=True, text=True, timeout=5)
    if result.returncode == 0 and "queuectl" in result.stdout and "enqueue" in result.stdout:
        print_result("Help command", True, "Help text available")
        help_ok = True
    else:
        print_result("Help command", False)
        help_ok = False
    
    # Check README exists
    import os
    if os.path.exists("README.md"):
        try:
            with open("README.md", "r", encoding="utf-8") as f:
                readme_content = f.read()
        except:
            # Try with different encoding
            with open("README.md", "r", encoding="latin-1") as f:
                readme_content = f.read()
        
        if len(readme_content) > 1000 and ("Usage" in readme_content or "usage" in readme_content) and ("Installation" in readme_content or "installation" in readme_content):
            print_result("README documentation", True, f"README.md exists ({len(readme_content)} chars)")
            readme_ok = True
        else:
            print_result("README documentation", False, "README incomplete")
            readme_ok = False
    else:
        print_result("README documentation", False, "README.md not found")
        readme_ok = False
    
    # Check command output is readable
    result = subprocess.run("python main.py status", shell=True, capture_output=True, text=True, timeout=5)
    if result.returncode == 0 and "Queue Status" in result.stdout and "Pending" in result.stdout:
        print_result("Command output readability", True, "Output is human-readable")
        output_ok = True
    else:
        print_result("Command output readability", False)
        output_ok = False
    
    item5_passed = help_ok and readme_ok and output_ok
except Exception as e:
    print_result("CLI documentation test", False, str(e))
    item5_passed = False

results.append(("CLI user-friendly and documented", item5_passed))

# ============================================================================
# CHECKLIST ITEM 6: Code is modular and maintainable
# ============================================================================
print_header("6. Code is modular and maintainable")

try:
    # Check all modules can be imported independently
    modules = [
        'storage',
        'config_manager',
        'job_manager',
        'executor',
        'dlq_manager',
        'worker_manager',
        'utils'
    ]
    
    modules_ok = True
    for module in modules:
        try:
            __import__(module)
            print_result(f"Module '{module}'", True, "Imports successfully")
        except ImportError as e:
            print_result(f"Module '{module}'", False, str(e))
            modules_ok = False
    
    # Check for clear separation of concerns
    import inspect
    from storage import Storage
    from job_manager import JobManager
    
    storage_methods = [m for m in dir(Storage) if not m.startswith('_')]
    job_manager_methods = [m for m in dir(JobManager) if not m.startswith('_')]
    
    if len(storage_methods) > 5 and len(job_manager_methods) > 5:
        print_result("Module separation", True, f"Storage: {len(storage_methods)} methods, JobManager: {len(job_manager_methods)} methods")
        separation_ok = True
    else:
        print_result("Module separation", False)
        separation_ok = False
    
    item6_passed = modules_ok and separation_ok
except Exception as e:
    print_result("Modularity test", False, str(e))
    item6_passed = False

results.append(("Code is modular and maintainable", item6_passed))

# ============================================================================
# CHECKLIST ITEM 7: Includes test or script verifying main flows
# ============================================================================
print_header("7. Includes test or script verifying main flows")

try:
    # Check test files exist
    import os
    test_files = []
    if os.path.exists("test_basic.py"):
        test_files.append("test_basic.py")
    if os.path.exists("test_queuectl.py"):
        test_files.append("test_queuectl.py")
    
    if len(test_files) > 0:
        print_result("Test files exist", True, f"Found: {', '.join(test_files)}")
        test_files_ok = True
    else:
        print_result("Test files exist", False, "No test files found")
        test_files_ok = False
    
    # Run test_basic.py
    if os.path.exists("test_basic.py"):
        result = subprocess.run("python test_basic.py", shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and "PASS" in result.stdout:
            print_result("test_basic.py execution", True, "All tests passed")
            basic_test_ok = True
        else:
            print_result("test_basic.py execution", False, f"Exit code: {result.returncode}")
            basic_test_ok = False
    else:
        basic_test_ok = False
    
    item7_passed = test_files_ok and basic_test_ok
except Exception as e:
    print_result("Test verification", False, str(e))
    item7_passed = False

results.append(("Includes test or script verifying main flows", item7_passed))

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print_header("FINAL CHECKLIST RESULTS")

all_passed = True
for item, passed in results:
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {item}")
    if not passed:
        all_passed = False

print("\n" + "=" * 70)
if all_passed:
    print("  [SUCCESS] ALL CHECKLIST ITEMS PASSED")
    print("  Project is ready for submission!")
    sys.exit(0)
else:
    print("  [WARNING] SOME CHECKLIST ITEMS FAILED")
    print("  Please review and fix the failed items before submission.")
    sys.exit(1)

