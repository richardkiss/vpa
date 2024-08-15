from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List



@dataclass
class Config:
    dir_path: Path
    ignore_cycles_in: List[str]
    module_maps: Dict[str, str]
    excluded_paths: List[Path] = field(default_factory=list)
