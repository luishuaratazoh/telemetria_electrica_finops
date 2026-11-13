"""Buffer local en memoria para cuando el broker no esta disponible (descarta lo mas antiguo si se llena)."""
from __future__ import annotations

from collections import deque
from typing import Any


class LocalBuffer:
    def __init__(self, max_items: int = 200_000) -> None:
        self._q: deque[tuple[str, dict[str, Any], str | None]] = deque(maxlen=max_items)
        self.dropped = 0
        self._max = max_items

    def add(self, topic: str, message: dict[str, Any], key: str | None) -> None:
        if len(self._q) == self._max:
            self.dropped += 1
        self._q.append((topic, message, key))

    def pop_batch(self, n: int) -> list[tuple[str, dict[str, Any], str | None]]:
        out = []
        while self._q and len(out) < n:
            out.append(self._q.popleft())
        return out

    def push_front(self, items: list[tuple[str, dict[str, Any], str | None]]) -> None:
        for it in reversed(items):
            self._q.appendleft(it)

    def __len__(self) -> int:
        return len(self._q)
