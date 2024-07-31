from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Annotation:
    package: str

    @classmethod
    def is_annotated(cls, file_string: str) -> bool:
        return file_string.startswith("# Package: ")

    @classmethod
    def parse(cls, file_string: str) -> Annotation:
        result = re.search(r"^# Package: (.+)$", file_string, re.MULTILINE)
        if result is None:
            raise ValueError("Annotation not found")

        return cls(result.group(1).strip())
