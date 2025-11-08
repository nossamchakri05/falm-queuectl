#!/usr/bin/env python3
"""Basic functionality test."""
import subprocess
import sys
import json

def test_enqueue():
    """Test enqueue with Python API."""
    import uuid
    from storage import Storage
    from config_manager import ConfigManager
    from job_manager import JobManager
    
    storage = Storage()
    config_manager = ConfigManager(storage)
    job_manager = JobManager(storage, config_manager)
    
    # Generate unique test ID
    test_id = f"test_{uuid.uuid4().hex[:8]}"
    
    # Test enqueue
    job = job_manager.enqueue_job({"id": test_id, "command": "echo Hello"})
    assert job["id"] == test_id
    assert job["state"] == "pending"
    print("[PASS] Enqueue test passed")
    
    # Test status
    status = job_manager.get_status()
    assert status["jobs"]["pending"] >= 1
    print("[PASS] Status test passed")
    
    # Test list
    jobs = job_manager.list_jobs(state="pending")
    assert len(jobs) >= 1
    assert any(j["id"] == test_id for j in jobs)
    print("[PASS] List test passed")
    
    # Test config
    config = config_manager.get_config()
    assert "max_retries" in config
    print("[PASS] Config test passed")
    
    print("\nAll basic tests passed!")

if __name__ == "__main__":
    test_enqueue()

