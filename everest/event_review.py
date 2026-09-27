"""LangGraph-based, non-blocking event review for collected monitoring results."""
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


ReviewDecision = Literal[
    'approve_send',
    'suppress_duplicate',
    'suppress_noise',
    'needs_human_review',
    'source_unhealthy',
]


class ReviewState(TypedDict, total=False):
    source: dict
    result: dict
    valid: bool
    has_event: bool
    has_evidence: bool
    duplicate_count: int
    decision: ReviewDecision
    reason: str


def _assess_acquisition(state: ReviewState):
    result = state['result']
    valid = result.get('result') != 'unknown' and result.get('relevance') != 'out_of_scope'
    if not valid:
        return {'valid': False, 'decision': 'source_unhealthy', 'reason': result.get('error') or 'no_in_scope_data'}
    return {'valid': True}


def _assess_event(state: ReviewState):
    result = state['result']
    has_event = bool(result.get('matches')) and result.get('event_status') != 'product_update'
    if not has_event:
        return {'has_event': False, 'decision': 'suppress_noise', 'reason': 'no_candidate_event'}
    return {'has_event': True, 'duplicate_count': int(result.get('duplicate_event_keys', 0))}


def _assess_evidence(state: ReviewState):
    has_evidence = bool(state['result'].get('cards'))
    if not has_evidence:
        return {'has_evidence': False, 'decision': 'needs_human_review', 'reason': 'evidence_unavailable'}
    return {'has_evidence': True}


def _decide(state: ReviewState):
    if state.get('decision'):
        return {}
    if state.get('duplicate_count', 0):
        return {'decision': 'suppress_duplicate', 'reason': 'event_key_already_seen'}
    return {'decision': 'approve_send', 'reason': 'valid_event_with_evidence'}


def _route_after_acquisition(state: ReviewState):
    return 'event' if state.get('valid') else 'decision'


def _route_after_event(state: ReviewState):
    return 'evidence' if state.get('has_event') else 'decision'


def build_graph():
    graph = StateGraph(ReviewState)
    graph.add_node('acquisition', _assess_acquisition)
    graph.add_node('event', _assess_event)
    graph.add_node('evidence', _assess_evidence)
    graph.add_node('decision', _decide)
    graph.add_edge(START, 'acquisition')
    graph.add_conditional_edges('acquisition', _route_after_acquisition, {'event': 'event', 'decision': 'decision'})
    graph.add_conditional_edges('event', _route_after_event, {'evidence': 'evidence', 'decision': 'decision'})
    graph.add_edge('evidence', 'decision')
    graph.add_edge('decision', END)
    return graph.compile()


_GRAPH = build_graph()


def review(source, result):
    """Return the LangGraph review decision used by the notification gate."""
    state = _GRAPH.invoke({'source': source, 'result': result})
    return {
        'scope': 'notification_gate',
        'framework': 'langgraph',
        'decision': state['decision'],
        'reason': state['reason'],
        'valid': state.get('valid', False),
        'has_event': state.get('has_event', False),
        'has_evidence': state.get('has_evidence', False),
        'duplicate_count': state.get('duplicate_count', 0),
    }
