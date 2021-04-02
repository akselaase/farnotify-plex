import math
from os import PathLike
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Union
from queue import PriorityQueue
from contextlib import suppress
import inotify_simple  # type: ignore
from inotify_simple import flags
from errno import ENOTDIR
from dataclasses import dataclass

DIR_FLAGS = flags.CLOSE_WRITE | flags.CREATE | flags.DELETE | flags.DELETE_SELF | flags.MODIFY | flags.MOVE_SELF | flags.MOVED_FROM | flags.MOVED_TO | flags.EXCL_UNLINK | flags.ONLYDIR
FILE_FLAGS = flags.CLOSE_WRITE | flags.DELETE_SELF | flags.MODIFY | flags.MOVE_SELF


@dataclass
class Event:
    wd: int
    mask: int
    cookie: int
    name: str
    path: Path

    def __str__(self) -> str:
        return super().__str__() + ' FLAGS [{}]'.format(' | '.join(map(lambda flag: flag.name, flags.from_mask(self.mask))))


class INotify(inotify_simple.INotify):
    read_delay: Optional[float] = 100  # milliseconds
    wd_path: Dict[int, Path]

    def __init__(self, inheritable=False, nonblocking=False):
        super().__init__(inheritable=inheritable, nonblocking=nonblocking)
        self.wd_path = {}

    def add_path(self, path: Path):
        if path.is_dir():
            return self._add_dir(path, recurse=True)
        elif path.is_file():
            return self._add_file(path)
        else:
            raise ValueError('Unknown target type')

    def _add_dir(self, path: Path, recurse=True):
        wd = self.add_watch(path, DIR_FLAGS)
        if not recurse:
            return wd
        else:
            res = [wd]
            for child in path.iterdir():
                if child.is_dir():
                    res.extend(self._add_dir(child, recurse=True))
            return res

    def _add_file(self, path: Path):
        return self.add_watch(path, FILE_FLAGS)

    def add_watch(self, path, mask):
        path = path.resolve()
        wd = super().add_watch(path, mask)
        self.wd_path[wd] = path
        return wd

    def __iter__(self):
        while True:
            events = self.read(None, self.read_delay)  # type: Iterable[inotify_simple.Event]
            for ev in events:
                path = self.wd_path.get(ev.wd)

                # Add watchers for newly created subdirs
                if ev.mask & flags.ISDIR and \
                        ev.mask & flags.CREATE:
                    try:
                        self._add_dir(path / ev.name)
                    except OSError as ex:
                        if ex.errno != ENOTDIR:
                            raise

                # Forget removed mappings
                if ev.mask & flags.IGNORED:
                    del self.wd_path[ev.wd]

                # Reduce delay if we overflow
                if ev.mask & flags.Q_OVERFLOW and self.read_delay is not None:
                    self.read_delay /= 2
                    if self.read_delay < 10:
                        self.read_delay = None

                yield Event(ev.wd, ev.mask, ev.cookie, ev.name, path)
