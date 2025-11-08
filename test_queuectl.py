#!/usr/bin/env python3
"""Test script for queuectl functionality."""
import subprocess
import time
import json
import sys
import os

def run_command(cmd):
    """Run a command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"

def test_enqueue():
    """Test job enqueueing."""
    print("Test 1: Enqueue job...")
    cmd = 'python main.py enqueue \'{"id":"test1","command":"echo Hello World"}\''
    code, stdout, stderr = run_command(cmd)
    if code == 0 and "Enqueued job: test1" in stdout:
        print("  ✓ Passed")
        return True
    else:
        print(f"  ✗ Failed: {stdout} {stderr}")
        return False

def test_status():
    """Test status command."""
    print("Test 2: Check status...")
    cmd = "python main.py status"
    code, stdout, stderr = run_command(cmd)
    if code == 0 and "Queue Status" in stdout:
        print("  ✓ Passed")
        return True
    else:
        print(f"  ✗ Failed: {stdout} {stderr}")
        return False

def test_list():
    """Test list command."""
    print("Test 3: List jobs...")
    cmd = "python main.py list --state pending"
    code, stdout, stderr = run_command(cmd)
    if code == 0:
        print("  ✓ Passed")
        return True
    else:
        print(f"  ✗ Failed: {stdout} {stderr}")
        return False

def test_config():
    """Test config commands."""
    print("Test 4: Configuration...")
    # Get config
    cmd = "python main.py config get"
    code, stdout, stderr = run_command(cmd)
    if code != 0:
        print(f"  ✗ Failed to get config: {stdout} {stderr}")
        return False
    
    # Set config
    cmd = "python main.py config set max-retries 5"
    code, stdout, stderr = run_command(cmd)
    if code == 0:
        print("  ✓ Passed")
        return True
    else:
        print(f"  ✗ Failed: {stdout} {stderr}")
        return False

def test_dlq():
    """Test DLQ commands."""
    print("Test 5: DLQ operations...")
    cmd = "python main.py dlq list"
    code, stdout, stderr = run_command(cmd)
    if code == 0:
        print("  ✓ Passed")
        return True
    else:
        print(f"  ✗ Failed: {stdout} {stderr}")
        return False

def main():
    """Run all tests."""
    print("Running queuectl tests...\n")
    
    tests = [
        test_enqueue,
        test_status,
        test_list,
        test_config,
        test_dlq
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed!")

if __name__ == "__main__":
    main()



