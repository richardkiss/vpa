from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


from .directory_parameters import DirectoryParameters


@dataclass
class Config:
    directory_parameters: DirectoryParameters
    ignore_cycles_in: List[str]
    annotation_override: Dict[Path, str]
