"""Real pipes must be drained while cancellable native renderers are running."""
import json
import sys
from unittest.mock import Mock

import pytest

from services.engine import cadquery_engine, openscad


@pytest.fixture(params=[openscad, cadquery_engine], ids=['openscad', 'cadquery'])
def engine(request, monkeypatch):
    module = request.param
    monkeypatch.setattr(module, 'RENDER_TIMEOUT_S', 2)
    if module is cadquery_engine:
        monkeypatch.setattr(module, '_try_warm_pool', lambda *_: None)
    return module


def test_output_larger_than_pipe_capacity_completes(engine):
    command = [sys.executable, '-c',
               ('import sys; sys.stdout.write("o"*262144); sys.stdout.flush(); '
                'sys.stderr.write("e"*262144); sys.stderr.flush()')]
    success, output = engine.run_render(command, is_cancelled=lambda: False)
    assert success, 'the child only writes output and exits; waiting before reading deadlocks it'
    assert output.endswith('e'*262144)
    assert len(output) == (524288 if engine is cadquery_engine else 262144)


def test_streaming_stdout_cannot_block_stderr_or_completion(engine):
    command = [sys.executable, '-c',
               ('import sys; sys.stdout.write("o"*262144+"\\n"); sys.stdout.flush(); '
                'sys.stderr.write("diagnostic complete\\n"); sys.stderr.flush()')]
    events = [json.loads(event) for event in
              engine.stream_render(command, 'fixture', 0, 100, 1, 1)]
    assert events[-1]['event'] == 'part_done', events[-1]
    assert any(event.get('line') == 'diagnostic complete' for event in events)
    manager = engine._cq_process_manager if engine is cadquery_engine else engine._process_manager
    assert manager._active_process is None


def test_cancellation_still_interrupts_a_verbose_child(engine, monkeypatch):
    manager = engine._cq_process_manager if engine is cadquery_engine else engine._process_manager
    cancel = Mock(wraps=manager.cancel)
    monkeypatch.setattr(manager, 'cancel', cancel)
    checks = [0]

    def cancelled():
        checks[0] += 1
        return checks[0] >= 3

    command = [sys.executable, '-c',
               'import sys,time; sys.stdout.write("o"*262144); sys.stdout.flush(); time.sleep(30)']
    success, output = engine.run_render(command, is_cancelled=cancelled)
    assert not success
    assert 'cancelled' in output.lower()
    cancel.assert_called_once()
    assert manager._active_process is None


def test_timeout_still_stops_a_verbose_child(engine, monkeypatch):
    monkeypatch.setattr(engine, 'RENDER_TIMEOUT_S', 0.2)
    command = [sys.executable, '-c',
               'import sys,time; sys.stderr.write("e"*262144); sys.stderr.flush(); time.sleep(30)']
    success, _ = engine.run_render(command, is_cancelled=lambda: False)
    assert not success
    manager = engine._cq_process_manager if engine is cadquery_engine else engine._process_manager
    assert manager._active_process is None
