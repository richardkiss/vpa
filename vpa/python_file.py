from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class PythonFile:
    path: Path
    annotation: Optional[str]

    @classmethod
    def parse(cls, file_path: Path, annotation_override: Dict[Path, str]) -> PythonFile:
        file_string = file_path.read_text(encoding="utf-8", errors="ignore")
        annotation = annotation_override.get(file_path)
        if annotation is None:
            result = re.search(r"^# Package: (.+)$", file_string, re.MULTILINE)
            if result:
                annotation = result.group(1).strip()
        return cls(file_path, annotation)
