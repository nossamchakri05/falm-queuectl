"""Command execution for queuectl."""
import subprocess
import logging
import shlex
import sys
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class Executor:
    """Executes shell commands and captures results."""
    
    def __init__(self, timeout: Optional[int] = None):
        """Initialize executor.
        
        Args:
            timeout: Optional timeout in seconds
        """
        self.timeout = timeout
    
    def execute(self, command: str) -> Tuple[int, str, str]:
        """Execute a shell command.
        
        Args:
            command: Command to execute
        
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        logger.info(f"Executing command: {command}")
        
        try:
            # Use shell=True for cross-platform compatibility
            # On Windows, use cmd.exe; on Unix, use /bin/sh
            if sys.platform == "win32":
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.timeout
                )
            else:
                # On Unix, we can use shlex to properly handle commands
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.timeout
                )
            
            stdout, stderr = process.communicate()
            exit_code = process.returncode
            
            logger.debug(f"Command exited with code {exit_code}")
            if stdout:
                logger.debug(f"stdout: {stdout[:200]}")
            if stderr:
                logger.debug(f"stderr: {stderr[:200]}")
            
            return exit_code, stdout, stderr
        
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {self.timeout}s")
            process.kill()
            return 124, "", f"Command timed out after {self.timeout}s"
        
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return 1, "", str(e)



