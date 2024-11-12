from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FileMetadata:
    line_count: int
    inline_package: Optional[str]
