from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List

from .edge import Edge
from .file_metadata import FileMetadata
from .graph import remap_edges
from .imports import mods_imported_for_python_file, path_to_mod


def python_files(base_dir: Path, excluded_paths: List[Path]) -> Iterator[Path]:
    """
    Gathers non-empty Python files in the specified directory.
    """
    exclude = set(base_dir / p for p in excluded_paths)
    for root, dirs, files in base_dir.walk(top_down=True):
        dirs[:] = [d for d in dirs if root / d not in exclude]
        for file in files:
            path = root / file
            if path.suffix != ".py":
                continue
            if path in exclude:
                continue
            if path.stat().st_size == 0:
                continue
            yield path


@dataclass(frozen=True)
class ParseSummary:
    nodes: List[str]
    edges: List[Edge]
    node_to_metadata: Dict[str, FileMetadata]

    def path_to_package(self) -> Dict[str, str]:
        return {k: v.inline_package for k, v in self.node_to_metadata.items()}


def build_parse_summary(
    base_dir: Path, excluded_paths: List[Path], top_level_only: bool
) -> ParseSummary:
    path_edges: List[Edge] = []
    mod_to_path: Dict[str, str] = {}
    node_to_metadata: Dict[str, FileMetadata] = {}

    mod_edges: List[Edge] = []
    for path in python_files(base_dir, excluded_paths):
        src_mod = path_to_mod(path, base_dir)
        src_path_str = str(path.relative_to(base_dir))
        mod_to_path[src_mod] = src_path_str
        filestring = path.read_text()
        line_count = len(filestring.split("\n"))
        inline_package = None
        for imp_mod in mods_imported_for_python_file(
            filestring, base_dir, path, top_level_only
        ):
            mod_edges.append((src_mod, imp_mod))
        result = re.search(r"^# Package: (.+)$", filestring, re.MULTILINE)
        if result:
            inline_package = result.group(1).strip()
        node_to_metadata[src_path_str] = FileMetadata(line_count, inline_package)

    path_edges, reverse_lookup = remap_edges(mod_edges, mod_to_path)
    parse_summary = ParseSummary(
        nodes=sorted(mod_to_path.values()),
        edges=path_edges,
        node_to_metadata=node_to_metadata,
    )
    return parse_summary
