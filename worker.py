"""Resident Docker worker.

Runs two independent loops:
  * normal cadence: full multi-source pass with screenshots, on EVEREST_TICK_SECONDS
  * fast channel:   cheap change detection for interval_seconds sources (e.g. GEOFON 3s)

The fast channel is a separate process so a slow page capture never delays it.
"""
import os
import threading
import time
from pathlib import Path

from everest.core import now, write_json
from everest.orchestrator import run_cycle

TICK = int(os.environ.get('EVEREST_TICK_SECONDS', '300'))
FAST = os.environ.get('EVEREST_FAST_ENABLED', 'true').lower() not in ('0', 'false', 'no')
FAST_TICK = float(os.environ.get('EVEREST_FAST_TICK_SECONDS', '3'))


fast_state = {'last': None, 'error': ''}


def fast_loop():
    while True:
        try:
            fast_state['last'] = run_cycle('fast')
            fast_state['error'] = ''
        except Exception as exc:
            fast_state['error'] = type(exc).__name__
        time.sleep(max(1, FAST_TICK))


fast_thread = threading.Thread(target=fast_loop, name='langgraph-fast', daemon=True) if FAST else None
if fast_thread:
    fast_thread.start()


while True:
    normal = run_cycle('normal')
    write_json(Path('data/worker.json'), {
        'checked_at': now(),
        'fast': fast_state['last'] if FAST else {'execution': {'exit_code': 0}},
        'fast_error': fast_state['error'],
        'fast_channel_alive': bool(fast_thread and fast_thread.is_alive()),
        'normal': normal,
        'tick_seconds': TICK,
        'fast_tick_seconds': FAST_TICK,
        'run_retention_hours': int(os.environ.get('EVEREST_RUN_RETENTION_HOURS', '48')),
    })
    time.sleep(max(30, TICK))
