import os
import sys
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from watchfiles import arun_process, run_process
from watchfiles.main import Change
from watchfiles.run import run_function, set_tty, spawn_context as run_spawn_context, start_process

if TYPE_CHECKING:
    from conftest import MockRustType


class FakeProcess(SpawnProcess):
    def __init__(self, is_alive=True, exitcode=1, pid=123):
        self._is_alive = is_alive
        self._exitcode = exitcode
        self._pid = pid

    @property
    def exitcode(self):
        return self._exitcode

    @property
    def pid(self):
        return self._pid

    def start(self):
        pass

    def is_alive(self):
        return self._is_alive

    def join(self, wait):
        pass


def test_alive_terminates(mocker, mock_rust_notify: 'MockRustType'):
    mock_start_process = mocker.patch.object(run_spawn_context, 'Process', return_value=FakeProcess())
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target=object(), debounce=5, step=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 2  # kill in loop + final kill


def test_dead_callback(mocker, mock_rust_notify: 'MockRustType'):
    mock_start_process = mocker.patch.object(run_spawn_context, 'Process', return_value=FakeProcess(is_alive=False))
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}, {(1, '/path/to/foobar.py')}])

    c = mocker.MagicMock()

    assert run_process('/x/y/z', target=object(), callback=c, debounce=5, step=1) == 2
    assert mock_start_process.call_count == 3
    assert mock_kill.call_count == 0
    assert c.call_count == 2
    c.assert_called_with({(Change.added, '/path/to/foobar.py')})


@pytest.mark.skipif(sys.platform == 'win32', reason='fails on windows')
def test_alive_doesnt_terminate(mocker, mock_rust_notify: 'MockRustType'):
    mock_start_process = mocker.patch.object(run_spawn_context, 'Process', return_value=FakeProcess(exitcode=None))
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    assert run_process('/x/y/z', target=object(), debounce=5, step=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 4  # 2 kills in loop (graceful and termination) + 2 final kills


def test_start_process(mocker):
    mock_process = mocker.patch('watchfiles.run.spawn_context.Process')
    v = object()
    start_process(v, 'function', (1, 2, 3), {})
    assert mock_process.call_count == 1
    mock_process.assert_called_with(target=v, args=(1, 2, 3), kwargs={})
    assert os.getenv('WATCHFILES_CHANGES') == '[]'


def test_start_process_env(mocker):
    mock_process = mocker.patch('watchfiles.run.spawn_context.Process')
    v = object()
    changes = [(Change.added, 'a.py'), (Change.modified, 'b.py'), (Change.deleted, 'c.py')]  # use a list to keep order
    start_process(v, 'function', (1, 2, 3), {}, changes)
    assert mock_process.call_count == 1
    mock_process.assert_called_with(target=v, args=(1, 2, 3), kwargs={})
    assert os.getenv('WATCHFILES_CHANGES') == '[["added", "a.py"], ["modified", "b.py"], ["deleted", "c.py"]]'


async def test_async_alive_terminates(mocker, mock_rust_notify: 'MockRustType'):
    mock_start_process = mocker.patch.object(run_spawn_context, 'Process', return_value=FakeProcess())
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foobar.py')}])

    callback_calls = []

    async def c(changes):
        callback_calls.append(changes)

    assert await arun_process('/x/y/async', target=object(), callback=c, debounce=5, step=1) == 1
    assert mock_start_process.call_count == 2
    assert mock_kill.call_count == 2  # kill in loop + final kill
    assert callback_calls == [{(Change.added, '/path/to/foobar.py')}]


async def test_async_sync_callback(mocker, mock_rust_notify: 'MockRustType'):
    mock_start_process = mocker.patch.object(run_spawn_context, 'Process', return_value=FakeProcess())
    mock_kill = mocker.patch('watchfiles.run.os.kill')
    mock_rust_notify([{(1, '/path/to/foo.py')}, {(2, '/path/to/bar.py')}])

    callback_calls = []

    assert await arun_process('/x/y/async', target=object(), callback=callback_calls.append, debounce=5, step=1) == 2
    assert mock_start_process.call_count == 3
    assert mock_kill.call_count == 3
    assert callback_calls == [{(Change.added, '/path/to/foo.py')}, {(Change.modified, '/path/to/bar.py')}]


def test_run_function(tmp_work_path: Path, create_test_function):
    assert not (tmp_work_path / 'sentinel').exists()
    run_function(create_test_function, None, (), {})
    assert (tmp_work_path / 'sentinel').exists()


def test_run_function_tty(tmp_work_path: Path, create_test_function):
    # could this cause problems by changing sys.stdin?
    assert not (tmp_work_path / 'sentinel').exists()
    run_function(create_test_function, '/dev/tty', (), {})
    assert (tmp_work_path / 'sentinel').exists()


def test_set_tty_error():
    with set_tty('/foo/bar'):
        pass
