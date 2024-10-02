from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .config import Config
from .imports import path_to_mod
from .edge import Edge
from .graph import remap_edges
from .parse_summary import ParseSummary, FileMetadata, build_parse_summary


@dataclass(frozen=True)
class EdgeInfo:
    nodes: List[str]
    path_edges: List[Edge]
    mod_edges: List[Edge]
    path_to_package: Dict[str, str]
    node_metadata: Dict[str, FileMetadata]


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

    This method is deprecated. Use `parse_summary_for_config` instead.
    """

    parsed_summary: ParseSummary = build_parse_summary(
        config.dir_path, config.excluded_paths, top_level_only=config.top_level_only
    )

    base_dir = Path("")
    path_edges: List[Edge] = []
    mod_to_path: Dict[str, str] = {}
    path_to_package: Dict[str, str] = {}

    node_metadata: Dict[str, FileMetadata] = dict(parsed_summary.node_to_metadata)

    for node in parsed_summary.nodes:
        mod_to_path[path_to_mod(Path(node), base_dir)] = node
        md = parsed_summary.node_to_metadata.get(node)
        assert md is not None
        if md.inline_package:
            path_to_package[node] = md.inline_package
        node_metadata[node] = FileMetadata(md.line_count, md.inline_package)

    mod_to_path_rev = {v: k for k, v in mod_to_path.items()}
    mod_edges, reverse_lookup = remap_edges(parsed_summary.edges, mod_to_path_rev)

    for edge in path_edges:
        src, dst = edge
    edge_info = EdgeInfo(
        nodes=parsed_summary.nodes,
        mod_edges=mod_edges,
        path_edges=parsed_summary.edges,
        path_to_package=path_to_package,
        node_metadata=parsed_summary.node_to_metadata,
    )
    return edge_info
