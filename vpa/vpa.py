from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint
from typing import Any, Callable, Dict, List, Optional

import click
import yaml

from .config import Config
from .edge_info import (
    edge_info_for_config,
    generate_forward_lookup_from_reverse,
)
from .graph import (
    generate_transitive_path_lookup,
    edge_path_as_node_list,
    edges_to_adjacency_list,
    remap_edges,
)


def generate_dot(config: Config) -> str:
    edge_info = edge_info_for_config(config)
    src_edges = {s for s, d in edge_info.path_edges}
    s = "digraph G {\n"
    for src, dst in edge_info.path_edges:
        if dst in src_edges:
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
        excluded_paths: List[Path] = []
        ignore_cycles_in = []
        package_contents: Dict[str, List[str]] = {}
        if config_path is not None:
            # Reading from the YAML configuration file
            with open(config_path) as file:
                config_data = yaml.safe_load(file)

            # Extracting required configuration values
            excluded_paths = [Path(p) for p in config_data.get("excluded_paths", [])]
            ignore_cycles_in = config_data.get("ignore_cycles_in", [])
            package_contents = config_data.get("package_contents", {})

        # Instantiating the Config object
        config = Config(
            dir_path=Path(kwargs.pop("include_dir")),
            excluded_paths=[
                *(Path(p) for p in kwargs.pop("excluded_paths")),
                *excluded_paths,
            ],
            ignore_cycles_in=[*kwargs.pop("ignore_cycles_in", []), *ignore_cycles_in],
            package_contents=package_contents,
            # annotation_override={},
        )

        # Calling the wrapped function with the Config object and other arguments
        return func(config, *args, **kwargs)

    return inner


@click.command(
    "print_leafs",
    short_help="Print dependencies that have no further dependencies",
)
@click.option("--ignore-dep", multiple=True, type=str, help="Ignore a dependency")
@config
def print_leafs(config: Config, ignore_dep: List[str]) -> None:
    edge_info = edge_info_for_config(config)
    rev_mod_map = generate_forward_lookup_from_reverse(config.package_contents)
    reduced_edges, reverse_lookup = remap_edges(
        edge_info.path_edges, rev_mod_map, drop_missing=False
    )

    adj_list = edges_to_adjacency_list(reduced_edges)
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
    "print_edges",
    short_help="print edge info",
)
@config
def print_edges(config: Config) -> None:
    edge_info = edge_info_for_config(config)
    for edge in edge_info.path_edges:
        print(edge)


@click.command(
    "print_missing_annotations",
    short_help="Search a directory for python files without package annotations",
)
@config
def print_missing_annotations(config: Config) -> None:
    edge_info = edge_info_for_config(config)
    path_to_package = edge_info.path_to_package
    mod_to_path = edge_info.mod_to_path
    missing_annotations = []
    for mod, path in mod_to_path.items():
        if path not in path_to_package:
            missing_annotations.append(path)
    print("\n".join(missing_annotations))


@click.command(
    "print_dependency_graph",
    short_help="Output a dependency graph of all the files in a directory",
)
@config
def print_dependency_graph(config: Config) -> None:
    edge_info = edge_info_for_config(config)
    mod_to_path = edge_info.mod_to_path
    edges = edge_info.mod_edges
    dep_graph = edges_to_adjacency_list(edge_info.path_edges)
    print(json.dumps(dep_graph, indent=4))


@click.command(
    "print_virtual_dependency_graph",
    short_help="Output a dependency graph of all the packages in a directory",
)
@config
def print_virtual_dependency_graph(config: Config) -> None:
    edge_info = edge_info_for_config(config)
    reduced_edges, reverse_lookup = remap_edges(
        edge_info.path_edges, edge_info.path_to_package
    )
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
    path_lookup = generate_transitive_path_lookup(edge_info.path_edges)
    reverse_lookup = edge_info.reverse_lookup
    for src, path_dict in path_lookup.items():
        if src in path_dict:
            cycle = edge_path_as_node_list(path_dict[src][0])
            print(f"cycle of length {len(cycle)} found from {src} ({cycle})")
            for idx in range(len(cycle) - 1):
                src = cycle[idx]
                dst = cycle[idx + 1]
                print(f"  {src} -> {dst} ({reverse_lookup[(src, dst)]})")


def main():
    cli.add_command(print_edges)
    cli.add_command(print_missing_annotations)
    cli.add_command(print_dependency_graph)
    cli.add_command(print_virtual_dependency_graph)
    cli.add_command(print_cycles)
    cli.add_command(print_leafs)
    cli()


if __name__ == "__main__":
    main()
