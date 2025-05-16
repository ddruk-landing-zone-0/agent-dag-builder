from .logger import LOGGER
import json
import os
import subprocess
import tempfile
import json
import sys


class PythonEnvironmentManager:
    def __init__(self, venv_path: str, create_env: bool = False):
        self.venv_path = venv_path
        if create_env:
            self.create_virtualenv()

        self.python_bin = os.path.join(venv_path, "bin", "python") if os.name != "nt" else os.path.join(venv_path, "Scripts", "python.exe")

        if not os.path.exists(self.python_bin):
            raise FileNotFoundError(f"Python executable not found in virtualenv: {self.python_bin}")
        LOGGER.info(f"Using Python from virtual environment: {self.python_bin}")

    def create_virtualenv(self):
        if os.path.exists(self.venv_path):
            LOGGER.warning(f"Virtual environment already exists at {self.venv_path}. Skipping creation.")
            return

        try:
            subprocess.check_call([sys.executable, "-m", "venv", self.venv_path])
            LOGGER.info(f"Created virtual environment at {self.venv_path}")
        except subprocess.CalledProcessError as e:
            LOGGER.critical(f"Failed to create virtual environment: {e}")
            raise

    def install_dependencies(self, packages):
        if isinstance(packages, str):
            packages = [packages]

        try:
            subprocess.check_call([self.python_bin, "-m", "pip", "install"] + packages)
            LOGGER.info(f"Installed dependencies: {packages}")
        except subprocess.CalledProcessError as e:
            LOGGER.critical(f"Failed to install dependencies: {e}")
            raise

    def execute_python_code(self, function_body: str, arguments: dict) -> dict:
        # Wrap the function in a script with a fixed "result" dict output
        code = f"""
import json
{function_body}

if __name__ == "__main__":
    args = {json.dumps(arguments)}
    result = function(**args)
    print(json.dumps(result))
"""

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            script_path = f.name
            f.write(code)

        try:
            process = subprocess.run(
                [self.python_bin, script_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if process.returncode != 0:
                LOGGER.critical(f"Error in subprocess:\n{process.stderr}")
                raise RuntimeError(f"Python code failed: {process.stderr}")

            output = process.stdout.strip()
            LOGGER.debug(f"Subprocess output: {output}")
            result = json.loads(output)
            result = {str(k): str(v) for k, v in result.items()}
            return result

        except Exception as e:
            LOGGER.critical(f"Exception during execution: {e}")
            raise
        finally:
            os.unlink(script_path)