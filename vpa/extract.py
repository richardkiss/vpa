from pathlib import Path
from typing import Dict, List, Set, Tuple

import os
import pprint

from .config import Config
from .edge import Edge
from .graph import edges_to_adjacency_list
from .parse_summary import Metadata, parse_summary_for_config


TreeData = Tuple[str, List["TreeData"], List[str]]


def package_edges_for_path_edges(
    edges: List[Edge], path_to_package: Dict[str, str]
) -> List[Edge]:
    package_edges_set = set()
    for edge in edges:
        p0, p1 = [path_to_package.get(_, _) for _ in edge]
        if p0 == p1:
            continue
        package_edge = (p0, p1)
        package_edges_set.add(package_edge)
    return sorted(package_edges_set)


def dump(target: str) -> None:
    print(target)


def rebuild_potential_nodes(
    adj_list: Dict[str, List[str]],
    nodes_previously_rejected: Set[str],
    metadata_lookup: Dict[str, Metadata],
    safe_targets: Set[str],
) -> List[str]:
    """
    build a list of potential nodes to operate on
    these are nodes not yet in a package and do not import anything besides
    safe targets
    """
    potential_nodes = []
    for k, v in adj_list.items():
        if (
            k not in nodes_previously_rejected
            and k in metadata_lookup
            and len(set(v).difference(safe_targets)) == 0
        ):
            potential_nodes.append(k)

    potential_nodes.sort()
    return potential_nodes


def process_next_potential_node(
    base_path: Path,
    path_nodes: List[str],
    path_edges: List[Edge],
    path_to_package: Dict[str, str],
    new_module_name: str,
    safe_targets: Set[str],
    nodes_previously_rejected: Set[str],
    metadata_lookup: Dict[str, Metadata],
    used_by_lookup: Dict[str, List[str]],
) -> None:
    target = None
    prior_target = ""

    while True:
        if target is None:
            package_edges = package_edges_for_path_edges(path_edges, path_to_package)

            package_nodes = sorted(path_to_package.get(_, _) for _ in path_nodes)
            adj_list = edges_to_adjacency_list(package_edges, nodes=package_nodes)
            potential_nodes = rebuild_potential_nodes(
                adj_list, nodes_previously_rejected, metadata_lookup, safe_targets
            )
            if len(potential_nodes) == 0:
                break
            for pn in potential_nodes:
                target = pn
                if pn > prior_target:
                    break
        assert target is not None
        prior_target = target
        md = metadata_lookup[target]
        used_by_list = used_by_lookup[target]

        print("-------")
        print(
            f"** `{target}` has {md.line_count} line(s); used by {len(used_by_list)} file(s)"
        )
        print()
        print("Choose:")
        print("ret: enumerate all potential nodes")
        print(f"  l: view `{target}` with `less`")
        print(f"  y: move `{target}` to {new_module_name}")
        print(f"  n: reject `{target}` from {new_module_name} and remove from list")
        print(f'  u: list all nodes "used by" `{target}`')
        print(f'  i: list all nodes "imported" by `{target}`')
        print("  q: quit")
        print("int: choose a different node to consider")

        r = input("> ")
        try:
            target = potential_nodes[int(r)]
        except Exception:
            pass
        r = r[:1].lower()
        if r == "u":
            print("*******")
            print(
                f"{target} contains {md.line_count:5d} line(s) and is used by the following {len(used_by_list):3d} file(s)"
            )
            for used_by in used_by_list:
                print(f"{used_by}")
            print()
        if r == "":
            for idx, node in enumerate(potential_nodes):
                md = metadata_lookup[node]
                used_by_list = used_by_lookup[node]
                print(
                    f"{idx:3d}: [{len(used_by_list):3d} u, {md.line_count:5d}: l] {node}"
                )
                # also print: used_by_count, line_count
            print("u: used by, l: line count")
        if r == "q":
            break
        if r == "b":
            target = None
            breakpoint()
            continue
        if r == "l":
            path = base_path / target
            os.system(f"less {path}")
            continue
        if r == "y":
            print(f"Moving {target} to {new_module_name}")
            path_to_package[target] = new_module_name
            target = None
        if r == "n":
            if target is not None:
                nodes_previously_rejected.add(target)
            print(f"Rejecting {target}")
            target = None

    if len(potential_nodes) == 0:
        print("No potential nodes found. We are done.")


def extract(config: Config, new_module_name: str, top: bool) -> None:
    parse_summary = parse_summary_for_config(config)
    nodes = parse_summary.nodes

    path_edges = list(parse_summary.edges)
    if top:
        path_edges = [(dst, src) for src, dst in path_edges]
    path_to_package = config.package_map()
    safe_targets = set([new_module_name])
    nodes_previously_rejected = set([new_module_name])
    metadata = parse_summary.node_to_metadata

    used_by_lookup: Dict[str, List[str]] = {k: [] for k in nodes}
    for s, d in path_edges:
        used_by_lookup[d].append(s)

    process_next_potential_node(
        config.dir_path,
        nodes,
        path_edges,
        path_to_package,
        new_module_name,
        safe_targets,
        nodes_previously_rejected,
        metadata,
        used_by_lookup,
    )

    mod_paths = []
    for k, v in path_to_package.items():
        if v == new_module_name:
            mod_paths.append(k)

    toml_dict = {new_module_name: mod_paths}
    pprint.pprint(toml_dict)
