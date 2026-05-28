import os
import sys
import time
import logging
from pathlib import Path
from typing import Callable, Optional, Set

logger = logging.getLogger("apex.hotreload")


class HotReloader:
    def __init__(self, watch_dirs: list, callback: Optional[Callable] = None):
        self.watch_dirs = [Path(d).resolve() for d in watch_dirs]
        self.callback = callback
        self._watched_files: Set[str] = set()
        self._running = False

    def _get_files(self) -> Set[str]:
        files: Set[str] = set()
        for watch_dir in self.watch_dirs:
            if watch_dir.exists():
                for path in watch_dir.rglob("*.py"):
                    files.add(str(path))
                for path in watch_dir.rglob("*.html"):
                    files.add(str(path))
                for path in watch_dir.rglob("*.css"):
                    files.add(str(path))
                for path in watch_dir.rglob("*.js"):
                    files.add(str(path))
        return files

    def _check_changes(self) -> bool:
        current_files = self._get_files()
        if self._watched_files and current_files != self._watched_files:
            self._watched_files = current_files
            return True
        timestamps = {}
        for f in current_files:
            try:
                timestamps[f] = os.path.getmtime(f)
            except OSError:
                continue
        if hasattr(self, "_timestamps"):
            for f, mtime in timestamps.items():
                if f in self._timestamps and self._timestamps[f] != mtime:
                    self._timestamps = timestamps
                    return True
        self._timestamps = timestamps
        self._watched_files = current_files
        return False

    def start(self, interval: float = 0.5):
        self._timestamps = {}
        self._watched_files = self._get_files()
        for f in self._watched_files:
            try:
                self._timestamps[f] = os.path.getmtime(f)
            except OSError:
                continue
        logger.info(f"Watching {len(self._watch_dirs)} director{'y' if len(self._watch_dirs) == 1 else 'ies'} for changes")
        self._running = True
        while self._running:
            time.sleep(interval)
            if self._check_changes():
                logger.info("Change detected, reloading...")
                if self.callback:
                    self.callback()
                sys.stdout.flush()
                os._exit(3)


def watch_and_reload(watch_dirs: list):
    reloader = HotReloader(watch_dirs)
    reloader.start()
