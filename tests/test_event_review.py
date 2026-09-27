from everest.core import Store
from everest.delivery import destination
from everest.event_review import review


def result(**overrides):
    value = {
        'result': 'found', 'relevance': 'in_scope', 'event_status': 'candidate',
        'matches': ['new event'], 'cards': ['proof.png'], 'duplicate_event_keys': 0,
    }
    value.update(overrides)
    return value


def test_approves_valid_event_with_evidence():
    opinion = review({'rule_id': 'demo'}, result())
    assert opinion['decision'] == 'approve_send' and opinion['scope'] == 'notification_gate'


def test_suppresses_duplicate_event():
    opinion = review({'rule_id': 'demo'}, result(duplicate_event_keys=1))
    assert opinion['decision'] == 'suppress_duplicate'


def test_requests_review_without_evidence():
    opinion = review({'rule_id': 'demo'}, result(cards=[]))
    assert opinion['decision'] == 'needs_human_review'


def test_marks_failed_source_unhealthy():
    opinion = review({'rule_id': 'demo'}, result(result='unknown', error='TimeoutError'))
    assert opinion['decision'] == 'source_unhealthy'


def test_record_uses_langgraph_to_suppress_duplicate(tmp_path):
    store = Store(tmp_path / 'review.db')
    try:
        source = {'rule_id': 'demo', 'category_id': 'earthquake'}
        first = {**result(), 'source': source, 'run_id': 'first', 'retrieved_at': '2026-09-25T00:00:00+00:00', 'event_keys': ['quake:one'], 'seed_event_keys': True}
        store.record(first, tmp_path / 'first.json', 'none', destination({'serverchan': {'sendkey': 'k'}}))
        second = {**result(matches=['revised event text']), 'source': source, 'run_id': 'second', 'retrieved_at': '2026-09-25T00:01:00+00:00', 'event_keys': ['quake:one']}
        assert not store.record(second, tmp_path / 'second.json', 'changed', destination({'serverchan': {'sendkey': 'k'}}))
        assert second['event_review']['decision'] == 'suppress_duplicate'
    finally:
        store.close()
