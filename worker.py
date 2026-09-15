"""Resident Docker worker.

Runs two independent loops:
  * normal cadence: full multi-source pass with screenshots, on EVEREST_TICK_SECONDS
  * fast channel:   cheap change detection for interval_seconds sources (e.g. GEOFON 3s)

The fast channel is a separate process so a slow page capture never delays it.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from everest.core import now, write_json

TICK = int(os.environ.get('EVEREST_TICK_SECONDS', '300'))
FAST = os.environ.get('EVEREST_FAST_ENABLED', 'true').lower() not in ('0', 'false', 'no')


def start_fast():
    return subprocess.Popen([sys.executable, '-B', 'monitor.py', 'fast'])


fast_proc = start_fast() if FAST else None

while True:
    completed = subprocess.run(
        [sys.executable, '-B', 'monitor.py', 'run', '--notify', 'changed', '--send'],
        check=False,
    )
    fast_alive = fast_proc is not None and fast_proc.poll() is None
    if fast_proc is not None and not fast_alive:
        fast_proc = start_fast()
        fast_alive = True
    write_json(Path('data/worker.json'), {
        'checked_at': now(),
        'exit_code': completed.returncode,
        'fast_channel_alive': fast_alive,
        'tick_seconds': TICK,
    })
    time.sleep(max(30, TICK))
