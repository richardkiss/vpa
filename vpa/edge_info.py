from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List

from .config import Config
from .edge import Edge
from .graph import remap_edges
from .imports import mods_imported_for_python_file, path_to_mod


@dataclass(frozen=True)
class EdgeInfo:
    path_edges: List[Edge]
    mod_edges: List[Edge]
    mod_to_path: Dict[str, str]
    path_to_package: Dict[str, str]
    reverse_lookup: Dict[Edge, str]


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


def generate_forward_lookup_from_reverse(
    rlookup: Dict[str, List[str]],
) -> Dict[str, str]:
    d = {}
    for k, vs in rlookup.items():
        for v in vs:
            d[v] = k
    return d


def edge_info_for_config(config: Config) -> EdgeInfo:
    """
    Given a configuration, return the edges, mod to path mapping, and path_to_package.
    The edges are the modules corresponding to the paths.
    """

    base_dir = config.dir_path
    mod_edges: List[Edge] = []
    path_edges: List[Edge] = []
    mod_to_path: Dict[str, str] = {}
    path_to_package: Dict[str, str] = {}
    package_map: Dict[str, str] = generate_forward_lookup_from_reverse(
        config.package_contents
    )

    for path in python_files(base_dir, config.excluded_paths):
        src_mod = path_to_mod(path, base_dir)
        src_path = str(path.relative_to(base_dir))
        mod_to_path[src_mod] = src_path
        filestring = path.read_text()
        for imp_mod in mods_imported_for_python_file(filestring, base_dir, path):
            mod_edges.append((src_mod, imp_mod))
        result = re.search(r"^# Package: (.+)$", filestring, re.MULTILINE)
        if result:
            path_to_package[src_path] = result.group(1).strip()
        else:
            r = package_map.get(src_path)
            if r:
                path_to_package[src_path] = r
    # remove edges containing an unvisited path, ie. that are not in `mod_to_path`
    mod_edges = sorted(
        (s, d) for s, d in mod_edges if s in mod_to_path and d in mod_to_path
    )
    path_edges, reverse_lookup = remap_edges(mod_edges, mod_to_path)
    edge_info = EdgeInfo(
        mod_edges=mod_edges,
        path_edges=path_edges,
        mod_to_path=mod_to_path,
        path_to_package=path_to_package,
        reverse_lookup=reverse_lookup,
    )
    return edge_info
