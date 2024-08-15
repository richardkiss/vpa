from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, TypeVar

S = TypeVar("S")
T = TypeVar("T")


EdgePath = None | Tuple[str, "EdgePath"]


def edges_to_adjacency_list(
    edges: List[Tuple[str, str]], include_empty=False
) -> Dict[str, List[str]]:
    """
    Given a list of edges, return an adjacency list as a `dict` with keys the source
    vertex and values a list of destination vertices.
    """
    adj_list_set: Dict[str, Set[str]] = {}
    for src, dst in edges:
        if include_empty:
            adj_list_set.setdefault(dst, set())
        adj_list_set.setdefault(src, set()).add(dst)
    adj_list: Dict[str, List[str]] = {k: sorted(v) for k, v in adj_list_set.items()}
    return adj_list


def remap_edges[S, T](
    edges: List[Tuple[S, S]], mapping: Dict[S, T], drop_missing=True,
) -> Tuple[List[Tuple[T, T]], Dict[Tuple[T, T], List[Tuple[S, S]]]]:
    s: Set[Tuple[T, T]] = set()
    reverse_lookup: Dict[Tuple[T, T], List[Tuple[S, S]]] = {}
    for src, dst in edges:
        s0 = mapping.get(src)
        d0 = mapping.get(dst)
        if not drop_missing:
            s0 = s0 if s0 is not None else src
            d0 = d0 if d0 is not None else dst
        if s0 is not None and d0 is not None and s0 != d0:
            s.add((s0, d0))
            reverse_lookup.setdefault((s0, d0), []).append((src, dst))
    return sorted(s), reverse_lookup


def generate_transitive_path_lookup(
    edges: List[Tuple[str, str]],
) -> Dict[str, Dict[str, List[EdgePath]]]:
    """
    Given a list of edges, return a dictionary mapping source nodes to destination nodes to paths.

    We start with known paths of a given length, first with 1. We extend by iterating over
    edges, where the edge acts as a prefix of known paths of the current length. New paths
    are added to a separate dictionary. Repeat until no new paths appear in the "new_paths"
    dictionary.
    """

    all_paths: Dict[str, Dict[str, List[EdgePath]]] = {}
    for s, d in edges:
        all_paths.setdefault(s, {})[d] = [(d, None)]
    prev_paths: Dict[str, Dict[str, List[EdgePath]]] = dict(all_paths)
    while prev_paths:
        new_paths: Dict[str, Dict[str, List[EdgePath]]] = {}
        for src, dst in edges:
            dst_paths: Dict[str, List[EdgePath]] = prev_paths.get(dst, {})
            for new_d, paths_to_new_d in dst_paths.items():
                if (
                    all_paths.get(src, {}).get(new_d) is not None
                    or new_paths.get(src, {}).get(new_d) is not None
                ):
                    # we have a path from src to dst already, so don't add a longer one
                    continue
                new_path = (dst, paths_to_new_d[0])
                new_paths.setdefault(src, {}).setdefault(new_d, []).append(new_path)
        for s, s_path_dict in prev_paths.items():
            for d, paths_to_d in s_path_dict.items():
                all_paths.setdefault(s, {})[d] = paths_to_d
        prev_paths = new_paths
    return all_paths


def edge_path_as_node_list(path: EdgePath) -> List[str]:
    node_list = []
    while path is not None:
        node_list.append(path[0])
        path = path[1]
    return node_list


def is_excluded(file_path: Path, excluded_paths: List[Path]) -> bool:
    file_path = file_path.resolve()  # Normalize the file path

    for excluded_path in excluded_paths:
        excluded_path = excluded_path.resolve()  # Normalize the excluded path
        # Check if the file path matches the excluded path exactly
        if file_path == excluded_path:
            return True
        # Check if the excluded path is a directory and if the file is under this directory
        if excluded_path.is_dir() and any(
            parent == excluded_path for parent in file_path.parents
        ):
            return True

    return False
