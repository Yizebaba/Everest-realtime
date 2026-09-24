import datetime as dt

from everest.retention import cleanup_runs


def test_cleanup_runs_only_removes_completed_directories_older_than_retention(tmp_path):
    runs = tmp_path / 'runs'
    old = runs / '20200101T000000Z-old'; old.mkdir(parents=True)
    recent_stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    recent = runs / f'{recent_stamp}-new'; recent.mkdir()
    invalid = runs / 'manual-notes'; invalid.mkdir()

    assert cleanup_runs(tmp_path, 48) == ['20200101T000000Z-old']
    assert not old.exists()
    assert recent.exists()
    assert invalid.exists()
