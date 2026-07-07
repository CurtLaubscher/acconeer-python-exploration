"""Recent-session persistence for the heatmap alignment workbench."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6 import QtCore


class RecentSessionStore:
    """Persist the Heatmap Alignment Workbench recent-session list."""

    SETTINGS_KEY = "recent_session_paths"
    LIMIT = 10

    def __init__(self, settings: QtCore.QSettings) -> None:
        self._settings = settings

    @staticmethod
    def normalized_path(path: Path | str) -> str:
        return str(Path(path).expanduser().resolve(strict=False))

    @staticmethod
    def _dedupe_key(path: str) -> str:
        return os.path.normcase(path)

    def paths(self) -> tuple[Path, ...]:
        return tuple(Path(path) for path in self._read_path_strings())

    def add(self, path: Path | str) -> None:
        normalized = self.normalized_path(path)
        new_key = self._dedupe_key(normalized)
        remaining = [
            existing
            for existing in self._read_path_strings()
            if self._dedupe_key(existing) != new_key
        ]
        self._write_path_strings([normalized, *remaining][: self.LIMIT])

    def remove(self, path: Path | str) -> None:
        normalized = self.normalized_path(path)
        remove_key = self._dedupe_key(normalized)
        self._write_path_strings(
            [
                existing
                for existing in self._read_path_strings()
                if self._dedupe_key(existing) != remove_key
            ]
        )

    def clear(self) -> None:
        self._settings.remove(self.SETTINGS_KEY)

    def _read_path_strings(self) -> list[str]:
        raw_value = self._settings.value(self.SETTINGS_KEY, [])
        if isinstance(raw_value, str):
            candidates = [raw_value]
        elif isinstance(raw_value, (list, tuple)):
            candidates = [value for value in raw_value if isinstance(value, str)]
        else:
            candidates = []

        result: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate:
                continue
            normalized = self.normalized_path(candidate)
            key = self._dedupe_key(normalized)
            if key in seen:
                continue
            seen.add(key)
            result.append(normalized)
            if len(result) == self.LIMIT:
                break
        return result

    def _write_path_strings(self, paths: list[str]) -> None:
        self._settings.setValue(self.SETTINGS_KEY, paths[: self.LIMIT])
