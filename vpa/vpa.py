from __future__ import annotations

import ast
import json
import re
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from pprint import pprint
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import click
import yaml

from .config import Config
from .graph import (
    generate_transitive_path_lookup,
    edge_path_as_node_list,
    edges_to_adjacency_list,
    remap_edges,
)
from .directory_parameters import DirectoryParameters
from .imports import mods_imported_for_python_file, path_to_mod


@dataclass(frozen=True)
class EdgeInfo:
    edges: List[Tuple[str, str]]
    mod_to_path: Dict[str, str]
    annotations: Dict[str, str]


def edge_info_for_config(config: Config) -> EdgeInfo:
    """
    Given a configuration, return the edges, mod to path mapping, and annotations.
    The edges are the modules corresponding to the paths.
    """

    base_dir = config.directory_parameters.dir_path
    edges: List[Tuple[str, str]] = []
    annotations: Dict[str, str] = {}
    all_mods: Set[str] = set()
    mod_to_path: Dict[str, str] = {}

    for path in [
        _.path for _ in config.directory_parameters.gather_non_empty_python_files()
    ]:
        src_mod = path_to_mod(path, base_dir)
        src_path = path.relative_to(base_dir)
        mod_to_path[src_mod] = str(src_path)
        all_mods.add(src_mod)
        filestring = path.read_text()
        for imp_mod in mods_imported_for_python_file(filestring, base_dir, path):
            edges.append((src_mod, imp_mod))
        result = re.search(r"^# Package: (.+)$", filestring, re.MULTILINE)
        if result:
            annotations[src_mod] = result.group(1).strip()
        else:
            r = config.module_maps.get(path)
            if r:
                annotations[src_mod] = r
    edge_info = EdgeInfo(edges=edges, mod_to_path=mod_to_path, annotations=annotations)
    return edge_info


def generate_dot(config: Config) -> str:
    edge_info = edge_info_for_config(config)
    src_mapping = {s: s for s, d in edge_info.edges}
    reduced_edges, reverse_lookup = remap_edges(edge_info.edges, edge_info.mod_to_path)
    s = "digraph G {\n"
    for src, dst in reduced_edges:
        s += f'  "{src}" -> "{dst}";\n'
    s += "}\n"
    return s


@click.group(
    help="A utility for grouping different parts of the repo into separate projects"
)
def cli() -> None:
    pass


def config(func: Callable[..., None]) -> Callable[..., None]:
    @click.option(
        "--directory",
        "include_dir",
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
        required=True,
        help="The directory to include.",
    )
    @click.option(
        "--exclude-path",
        "excluded_paths",
        multiple=True,
        type=click.Path(exists=False, file_okay=True, dir_okay=True),
        help="Optional paths to exclude.",
    )
    @click.option(
        "--config",
        "config_path",
        type=click.Path(exists=True),
        required=False,
        default=None,
        help="Path to the YAML configuration file.",
    )
    def inner(config_path: Optional[str], *args: Any, **kwargs: Any) -> None:
        exclude_paths = []
        ignore_cycles_in = []
        module_maps = {}
        if config_path is not None:
            # Reading from the YAML configuration file
            with open(config_path) as file:
                config_data = yaml.safe_load(file)

            # Extracting required configuration values
            exclude_paths = [Path(p) for p in config_data.get("exclude_paths", [])]
            ignore_cycles_in = config_data.get("ignore_cycles_in", [])
            module_maps = config_data.get("module_maps", {})

        # Instantiate DirectoryParameters with the provided options
        dir_params = DirectoryParameters(
            dir_path=Path(kwargs.pop("include_dir")),
            excluded_paths=[
                *(Path(p) for p in kwargs.pop("excluded_paths")),
                *exclude_paths,
            ],
        )

        # Instantiating the Config object
        config = Config(
            directory_parameters=dir_params,
            ignore_cycles_in=[*kwargs.pop("ignore_cycles_in", []), *ignore_cycles_in],
            module_maps=module_maps,
            # annotation_override={},
        )

        # Calling the wrapped function with the Config object and other arguments
        return func(config, *args, **kwargs)

    return inner


def reverse_module_maps(module_maps: Dict[str, List[str]]) -> Dict[str, str]:
    d = {}
    for k, vs in module_maps.items():
        for v in vs:
            d[v] = k
    return d


@click.command(
    "print_leafs",
    short_help="Print dependencies that have no further dependencies",
)
@click.option("--ignore-dep", multiple=True, type=str, help="Ignore a dependency")
@config
def print_leafs(config: Config, ignore_dep: List[str]) -> None:
    edge_info = edge_info_for_config(config)
    rev_mod_map = reverse_module_maps(config.module_maps)
    reduced_edges_1, reverse_lookup_1 = remap_edges(
        edge_info.edges, edge_info.mod_to_path
    )
    reduced_edges_2, reverse_lookup_2 = remap_edges(reduced_edges_1, rev_mod_map, drop_missing=False)

    adj_list = edges_to_adjacency_list(reduced_edges_2)
    deps_to_ignore = set(ignore_dep)
    leaf_set = set()
    for ks in adj_list.values():
        for k in ks:
            imports = adj_list.get(k, [])
            import_set = set(imports)
            if not import_set.difference(deps_to_ignore):
                leaf_set.add(k)
    leafs = sorted(str(_) for _ in leaf_set)
    print(json.dumps(leafs, indent=4))


@click.command(
    "print_missing_annotations",
    short_help="Search a directory for python files without annotations",
)
@config
def print_missing_annotations(config: Config) -> None:
    edge_info = edge_info_for_config(config)
    annotations = edge_info.annotations
    mod_to_path = edge_info.mod_to_path
    missing_annotations = []
    for mod, path in mod_to_path.items():
        if mod not in annotations:
            missing_annotations.append(str(path))
    print("\n".join(missing_annotations))


@click.command(
    "print_dependency_graph",
    short_help="Output a dependency graph of all the files in a directory",
)
@config
def print_dependency_graph(config: Config) -> None:
    edge_info = edge_info_for_config(config)
    mod_to_path = edge_info.mod_to_path
    edges = edge_info.edges
    reduced_edges, reverse_lookup = remap_edges(edges, mod_to_path)
    reduced_edges_str = [(str(src), str(dst)) for src, dst in reduced_edges]
    dep_graph = edges_to_adjacency_list(reduced_edges_str)
    print(json.dumps(dep_graph, indent=4))


@click.command(
    "print_virtual_dependency_graph",
    short_help="Output a dependency graph of all the packages in a directory",
)
@config
def print_virtual_dependency_graph(config: Config) -> None:
    edge_info = edge_info_for_config(config)
    reduced_edges, reverse_lookup = remap_edges(edge_info.edges, edge_info.annotations)
    adj_list = edges_to_adjacency_list(reduced_edges)
    print(json.dumps(adj_list, indent=4))


@click.command(
    "print_cycles", short_help="Output cycles found in the virtual dependency graph"
)
@click.option(
    "--ignore-cycles-in",
    "ignore_cycles_in",
    multiple=True,
    type=str,
    help="Ignore dependency cycles in a package",
)
@config
def print_cycles(config: Config) -> None:
    edge_info = edge_info_for_config(config)
    reduced_edges, reverse_lookup = remap_edges(edge_info.edges, edge_info.annotations)
    adj_list = edges_to_adjacency_list(reduced_edges)
    path_lookup = generate_transitive_path_lookup(reduced_edges)
    for src, path_dict in path_lookup.items():
        if src in path_dict:
            cycle = edge_path_as_node_list(path_dict[src][0])
            print(f"cycle of length {len(cycle)} found from {src} ({cycle})")
            for idx in range(len(cycle) - 1):
                src = cycle[idx]
                dst = cycle[idx + 1]
                print(f"  {src} -> {dst} ({reverse_lookup[(src, dst)]})")


def main():
    cli.add_command(print_missing_annotations)
    cli.add_command(print_dependency_graph)
    cli.add_command(print_virtual_dependency_graph)
    cli.add_command(print_cycles)
    cli.add_command(print_leafs)
    cli()


if __name__ == "__main__":
    main()
