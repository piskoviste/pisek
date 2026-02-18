# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2025        Daniel Skýpala <daniel@honza.info>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from dataclasses import dataclass, asdict
import json
import logging
import os
import threading
from typing import Callable, Literal

from pisek.utils.text import fatal_user_error
from pisek.utils.colors import remove_colors
from pisek.utils.paths import INTERNALS_DIR

root_logger = logging.getLogger()
logger = logging.getLogger(__name__)

LOG_JSON_FILE = "log.json"

LogLevel = (
    Literal["critical"]
    | Literal["error"]
    | Literal["warning"]
    | Literal["info"]
    | Literal["debug"]
)


@dataclass
class LogEntry:
    scope: str
    level: LogLevel
    message: str

    def __init__(self, scope: str, level: LogLevel, message: str) -> None:
        self.scope = scope
        self.level = level
        self.message = remove_colors(message)


def log(log_entry: LogEntry) -> None:
    getattr(root_logger, log_entry.level)(
        log_entry.message, extra={"scope": log_entry.scope}
    )


def map_log_level(log_level: str) -> int:
    log_level = log_level.lower()
    if log_level == "debug":
        return logging.DEBUG
    elif log_level == "info":
        return logging.INFO
    elif log_level == "warning":
        return logging.WARNING
    elif log_level == "error":
        return logging.ERROR
    elif log_level == "critical":
        return logging.CRITICAL
    else:
        fatal_user_error(f"Invalid log level: '{log_level}'")


class _CallbackHandler(logging.Handler):
    def __init__(self, callback: Callable[[LogEntry], None], level=logging.NOTSET):
        self.__callback = callback
        super().__init__(level)

    def emit(self, record):
        try:
            if hasattr(record, "scope"):
                scope = record.scope
            else:
                scope = "unknown"
            self.__callback(LogEntry(scope, record.levelname.lower(), record.msg))
        except Exception:
            self.handleError(record)


class _JSONLogging:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enabled = False
        self._entries: list[LogEntry] = []

    def enable(self) -> None:
        self._enabled = True

    def get_handler(self) -> logging.Handler:
        return _CallbackHandler(self._log)

    def _log(self, entry: LogEntry) -> None:
        self._entries.append(entry)

    def write(self) -> None:
        if not self._enabled:
            return

        os.makedirs(INTERNALS_DIR, exist_ok=True)
        with open(os.path.join(INTERNALS_DIR, LOG_JSON_FILE), "w") as f:
            json.dump(list(map(asdict, self._entries)), f)


json_logging = _JSONLogging()
