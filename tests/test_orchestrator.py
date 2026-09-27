def test_langgraph_orchestrator_calls_mcp_tools_in_order(monkeypatch):
    import everest.orchestrator as module
    calls = []

    def fake_call(name, arguments=None):
        calls.append((name, arguments))
        return {'tool': name}

    monkeypatch.setattr(module, 'call', fake_call)
    graph = module.build_graph()
    result = graph.invoke({'kind': 'fast'})
    assert calls[0][0] == 'run_fast_source'
    assert calls[-1] == ('read_runtime_status', None)
    assert len(result['execution']['fast_sources']) == 7


def test_normal_orchestrator_uses_normal_cycle(monkeypatch):
    import everest.orchestrator as module
    calls = []
    monkeypatch.setattr(module, 'call', lambda name, arguments=None: calls.append(name) or {'tool': name})
    assert module.build_graph().invoke({'kind': 'normal'})['execution']['tool'] == 'normal_cycle'
    assert calls == ['normal_cycle', 'read_runtime_status']


def test_fast_and_normal_cycles_use_separate_mcp_tools(monkeypatch):
    import everest.orchestrator as module
    calls = []
    monkeypatch.setattr(module, 'call', lambda name, arguments=None: calls.append(name) or {'tool': name})
    module.build_graph().invoke({'kind': 'fast'})
    module.build_graph().invoke({'kind': 'normal'})
    assert calls[-2:] == ['normal_cycle', 'read_runtime_status']
