from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List


from vpa.python_file import PythonFile


@dataclass(frozen=True)
class DirectoryParameters:
    dir_path: Path
    excluded_paths: List[Path] = field(default_factory=list)

    def python_files(self) -> Iterator[Path]:
        """
        Gathers non-empty Python files in the specified directory while
        ignoring files and directories in the excluded paths.
        """
        exclude = set(self.dir_path / p for p in self.excluded_paths)
        for root, dirs, files in self.dir_path.walk(top_down=True):
            # Modify dirs in-place to remove excluded directories from search
            dirs[:] = [d for d in dirs if root / d not in exclude]
            for file in files:
                file_path = root / file
                if file_path.suffix == ".py" and file_path not in exclude:
                    yield file_path

    def gather_non_empty_python_files(
        self, annotation_override: Dict[Path, str] = {}
    ) -> List[PythonFile]:
        """
        Gathers non-empty Python files in the specified directory while
        ignoring files and directories in the excluded paths.

        Returns:
            A list of paths to non-empty Python files.
        """
        return list(
            PythonFile.parse(file_path, annotation_override)
            for file_path in self.python_files()
            if file_path.stat().st_size > 0
        )
