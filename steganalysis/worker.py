import os
import sys
from pathlib import Path


def main() -> None:
    from .db import Store
    from .engine import execute_job

    store = Store(Path(sys.argv[1]))
    job_id = sys.argv[2]
    if os.name == "posix":
        import importlib
        from typing import Any

        resource: Any = importlib.import_module("resource")
        budget = store.get("jobs", job_id)["budget"]
        resource.setrlimit(resource.RLIMIT_CPU, (budget["job_seconds"], budget["job_seconds"] + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (128 * 1024 * 1024, 128 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    execute_job(store, job_id)


if __name__ == "__main__":
    main()
