"""LangGraph is the sole worker orchestrator; MCP tools perform monitor execution."""
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from .mcp_runtime import call

FAST_RULE_IDS = ['earthquake-02', 'earthquake-03', 'earthquake-04', 'earthquake-05', 'earthquake-07', 'platform-10', 'special-02']


class CycleState(TypedDict, total=False):
    kind: Literal['fast', 'normal']
    fast_sources: list[str]
    source_results: list[dict]
    execution: dict
    status: dict


def _execute(state: CycleState):
    if state['kind'] != 'fast':
        return {'execution': call('normal_cycle')}
    requested = state.get('fast_sources', FAST_RULE_IDS)
    if isinstance(requested, str):
        requested = [requested]
    results = [call('run_fast_source', {'rule_id': rule_id}) for rule_id in requested]
    return {'source_results': results, 'execution': {'fast_sources': results}}


def _status(state: CycleState):
    # worker.json is an output of this graph. Reading it here causes each cycle
    # to embed the prior complete worker state inside the next one.
    return {'status': {'source': 'current_cycle'}}


def build_graph():
    graph = StateGraph(CycleState)
    graph.add_node('execute', _execute)
    graph.add_node('status', _status)
    graph.add_edge(START, 'execute')
    graph.add_edge('execute', 'status')
    graph.add_edge('status', END)
    return graph.compile()


_GRAPH = build_graph()


def run_cycle(kind):
    fast_sources = FAST_RULE_IDS if kind == 'fast' else []
    return _GRAPH.invoke({'kind': kind, 'fast_sources': fast_sources})
