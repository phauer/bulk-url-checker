import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "bulk-url-checker.py"


def _load_script_module():
    # the script name contains a hyphen, so it can't be imported with a plain import statement
    spec = importlib.util.spec_from_file_location("bulk_url_checker", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def checker():
    module = _load_script_module()
    module.RETRY_DELAY_SECONDS = 0  # retries must not slow down the tests
    return module
