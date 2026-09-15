"""Resident Docker worker. Each cycle uses the same source cadence and per-source cards."""
import os
import subprocess
import sys
import time
from pathlib import Path
from everest.core import now, write_json

while True:
    completed = subprocess.run([sys.executable, '-B', 'monitor.py', 'run', '--notify', 'changed', '--send'], check=False)
    write_json(Path('data/worker.json'), {'checked_at': now(), 'exit_code': completed.returncode})
    time.sleep(max(60, int(os.environ.get('EVEREST_TICK_SECONDS', '300'))))
