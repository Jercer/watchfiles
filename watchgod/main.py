import logging
from pathlib import Path
from time import sleep, time
from typing import Type, Union

from .watcher import AllWatcher, DefaultWatcher

__all__ = 'watch',
logger = logging.getLogger('watchgod.main')


def unix_ms():
    return int(round(time() * 1000))


def watch(path: Union[Path, str], watcher_cls: Type[AllWatcher]=DefaultWatcher, debounce=400, min_sleep=100):
    p = watcher_cls(path)
    try:
        while True:
            start = unix_ms()
            changes = p.check()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('time=%0.0fms files=%d changes=%d', unix_ms() - start, len(p.files), len(changes))

            if changes:
                yield changes
            sleep_time = debounce - (unix_ms() - start)
            if sleep_time < min_sleep:
                sleep_time = min_sleep
            sleep(sleep_time / 1000)
    except KeyboardInterrupt:
        pass