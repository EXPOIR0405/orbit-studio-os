import os
import tempfile

# Set before pytest imports any application module; never use the operator database.
_database_dir = tempfile.TemporaryDirectory(prefix="orbit-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + _database_dir.name.replace("\\", "/") + "/test.db"
os.environ["ORBIT_DISABLE_WORKER"] = "1"
os.environ["ORBIT_ENABLE_LIVE"] = "false"

def pytest_sessionfinish(session, exitstatus):
    from orbit import storage
    storage.engine.dispose()
    _database_dir.cleanup()
