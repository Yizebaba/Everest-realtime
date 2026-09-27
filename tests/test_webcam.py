from everest.core import Store
from everest.webcam import _visual_signature
from PIL import Image
from pathlib import Path
import monitor


def test_visual_signature_detects_large_visibility_change():
    first = Image.new('RGB', (160, 120), 'white')
    second = Image.new('RGB', (160, 120), 'white')
    for x in range(80):
        for y in range(120):
            second.putpixel((x, y), (0, 0, 0))
    before = _visual_signature(first)
    after = _visual_signature(second)
    assert sum(abs(a - b) for a, b in zip(before, after)) / len(after) >= 28


def test_camera_frame_trigger_ignores_small_changes_and_triggers_recovery(tmp_path):
    store = Store(tmp_path / 'camera.db')
    try:
        first = bytes(576).hex()
        small = (bytes([5]) * 576).hex()
        large = (bytes([40]) * 576).hex()
        assert store.camera_frame_trigger('camera-01', first, True, 28) is False
        assert store.camera_frame_trigger('camera-01', small, True, 28) is False
        assert store.camera_frame_trigger('camera-01', large, True, 28) is True
        assert store.camera_frame_trigger('camera-01', None, False, 28) is False
        assert store.camera_frame_trigger('camera-01', large, True, 28) is True
    finally:
        store.close()


def test_camera_change_requires_translated_evidence(monkeypatch, tmp_path):
    source = {
        'rule_id': 'camera-01', 'name': 'Windy 珠峰 Khumjung 摄像头',
        'url': 'https://example.test/camera', 'camera_id': '1652187391',
        'category': '专项监控', 'category_id': 'camera', 'interval_minutes': 30,
    }
    result = {
        'run_id': 'camera-run', 'source': source, 'result': 'found',
        'retrieved_at': '2026-09-15T00:00:00+00:00', 'matches': ['camera frame'],
        'content': ['camera frame'], 'cards': [], 'relevance': 'in_scope',
        'event_status': 'candidate', 'camera_frame_signature': bytes([40]) * 576,
    }
    store = Store(tmp_path / 'camera.db')
    try:
        store.camera_frame_trigger('camera-01', bytes(576).hex(), True, 28)
        monkeypatch.setattr(monitor, 'collect_camera', lambda *args: {**result, 'camera_frame_signature': (bytes([40]) * 576).hex()})
        monkeypatch.setattr(monitor, 'make_cards', lambda record, *args: record.update(cards=[]))
        monkeypatch.setattr(monitor, 'write_report', lambda *args: None)
        args = type('Args', (), {'source': ['camera-01'], 'all': True, 'notify': 'changed', 'send': False})()
        settings = {'workers': 1, 'camera_visual_hash_distance': 28,
                    'camera_translation_timeout_ms': 90000, 'camera_translation_settle_ms': 8000,
                    'windy_pair': {}, '_root': str(Path(__file__).resolve().parents[1])}
        assert monitor.run(args, settings, {'sources': [source], 'defaults': {}}, {}, store, tmp_path) == 0
        latest = __import__('json').loads((tmp_path / 'latest.json').read_text(encoding='utf-8'))
        saved = __import__('json').loads((Path(latest['report']).parent / 'camera-01' / 'result.json').read_text(encoding='utf-8'))
        assert saved['camera_frame_trigger'] is True
        assert saved['selected_for_notification'] is False
        assert store.notices(latest['run_id']) == []
    finally:
        store.close()
