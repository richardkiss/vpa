from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List



@dataclass
class Config:
    dir_path: Path
    ignore_cycles_in: List[str]
    package_contents: Dict[str, List[str]]
    excluded_paths: List[Path] = field(default_factory=list)

    def package_map(self) -> Dict[str, str]:
        d = {}
        for k, vs in self.package_contents.items():
            for v in vs:
                d[v] = k
        return d

