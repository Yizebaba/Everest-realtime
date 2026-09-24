"""Retention for completed run evidence directories."""
import datetime as dt
import shutil
from pathlib import Path


def cleanup_runs(data_dir, retention_hours):
    """Remove only run directories whose UTC timestamp is older than retention."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=float(retention_hours))
    removed = []
    for path in (Path(data_dir) / 'runs').iterdir() if (Path(data_dir) / 'runs').is_dir() else ():
        if not path.is_dir() or path.is_symlink():
            continue
        try:
            started = dt.datetime.strptime(path.name[:16], '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if started < cutoff:
            shutil.rmtree(path)
            removed.append(path.name)
    return removed
