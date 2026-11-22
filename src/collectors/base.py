"""
Base classes and utilities for metric collectors.
"""
import time
from collections import deque
from typing import List, Tuple, Any, Optional

class RingBuffer:
    """Bounded circular buffer for time-series chart data."""
    def __init__(self, maxlen: int = 60, default_value: float = 0.0):
        self.maxlen = maxlen
        self._data: deque = deque([default_value] * maxlen, maxlen=maxlen)

    def append(self, value: float):
        self._data.append(float(value))

    def as_list(self) -> List[float]:
        return list(self._data)

    def last(self) -> float:
        return self._data[-1] if self._data else 0.0

    def min_max(self) -> Tuple[float, float]:
        if not self._data:
            return 0.0, 0.0
        return min(self._data), max(self._data)

    def clear(self, default_value: float = 0.0):
        self._data = deque([default_value] * self.maxlen, maxlen=self.maxlen)

    def __len__(self) -> int:
        return len(self._data)


class BaseCollector:
    """Abstract base class for all system metric collectors."""
    def __init__(self, name: str):
        self.name = name
        self.last_update_time: float = 0.0
        self.error: Optional[str] = None
        self.available: bool = True

    def update(self) -> dict:
        """Collect and return the latest metrics dictionary."""
        raise NotImplementedError("Subclasses must implement update()")
