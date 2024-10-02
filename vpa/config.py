from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .file_metadata import FileMetadata


@dataclass
class Config:
    dir_path: Path
    ignore_cycles_in: List[str]
    package_contents: Dict[str, List[str]]
    top_level_only: bool
    excluded_paths: List[Path] = field(default_factory=list)

    def package_map(
        self, node_metadata: Dict[str, FileMetadata] = {}
    ) -> Dict[str, str]:
        d = {}
        for k, vs in self.package_contents.items():
            for v in vs:
                d[v] = k
        for k, md in node_metadata.items():
            if md.inline_package:
                d[k] = md.inline_package
        return d

    def package_map_path(
        self, node_metadata: Dict[str, FileMetadata] = {}
    ) -> Dict[Path, str]:
        return {Path(k): v for k, v in self.package_map(node_metadata).items()}
