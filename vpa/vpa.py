from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import json

import click
import yaml

from .config import Config
from .imports import path_to_mod
from .edge_info import (
    edge_info_for_config,
    generate_forward_lookup_from_reverse,
)
from .extract import extract
from .graph import (
    is_excluded,
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
@click.option(
    "--directory",
    "include_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="The directory to include.",
)
@click.option(
    "--exclude-path",
    "excluded_paths",
    multiple=True,
    type=click.Path(exists=False, file_okay=True, dir_okay=True, path_type=Path),
    help="Optional paths to exclude.",
)
@click.option(
    "--top-level-only",
    is_flag=True,
    help="Parse only top level `import` statements",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    required=False,
    default=None,
    help="Path to the YAML configuration file.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    include_dir: Path,
    excluded_paths: List[Path],
    top_level_only: bool,
    config_path: Optional[Path],
) -> None:
    config_ignore_cycles_in: List[str] = []
    package_contents: Dict[str, List[str]] = {}
    config_excluded_paths: List[Path] = []
    if config_path is not None:
        # Reading from the YAML configuration file
        config_data = yaml.safe_load(config_path.read_text())

        # Extracting required configuration values
        config_excluded_paths = [Path(p) for p in config_data.get("excluded_paths", [])]
        config_ignore_cycles_in = config_data.get("ignore_cycles_in", [])
        package_contents = config_data.get("package_contents", {})

    # Instantiating the Config object
    config = Config(
        dir_path=Path(include_dir),
        excluded_paths=[*excluded_paths, *config_excluded_paths],
        ignore_cycles_in=config_ignore_cycles_in,
        top_level_only=top_level_only,
        package_contents=package_contents,
    )

    ctx.obj = config


@cli.command(
    "print_leafs",
    short_help="Print dependencies that have no further dependencies",
)
@click.option("--ignore-dep", multiple=True, type=str, help="Ignore a dependency")
@click.pass_context
def print_leafs(ctx: click.Context, ignore_dep: List[str]) -> None:
    config = ctx.obj
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


@cli.command(
    "print_edges",
    short_help="print edge info",
)
@click.pass_context
def print_edges(ctx: click.Context) -> None:
    config = ctx.obj
    edge_info = edge_info_for_config(config)
    for edge in edge_info.path_edges:
        print(edge)


@cli.command(
    "print_missing_annotations",
    short_help="Search a directory for python files without package annotations",
)
@click.pass_context
def print_missing_annotations(ctx: click.Context) -> None:
    config = ctx.obj
    edge_info = edge_info_for_config(config)
    path_to_package = edge_info.path_to_package
    missing_annotations = []
    for path in edge_info.nodes:
        if path not in path_to_package:
            missing_annotations.append(path)
    print("\n".join(missing_annotations))


@cli.command(
    "print_dependency_graph",
    short_help="Output a dependency graph of all the files in a directory",
)
@click.pass_context
def print_dependency_graph(ctx: click.Context) -> None:
    config = ctx.obj
    edge_info = edge_info_for_config(config)
    dep_graph = edges_to_adjacency_list(edge_info.path_edges)
    print(json.dumps(dep_graph, indent=4))


@cli.command(
    "print_virtual_dependency_graph",
    short_help="Output a dependency graph of all the packages in a directory",
)
@click.pass_context
def print_virtual_dependency_graph(ctx: click.Context) -> None:
    config = ctx.obj
    edge_info = edge_info_for_config(config)
    reduced_edges, reverse_lookup = remap_edges(
        edge_info.path_edges, edge_info.path_to_package
    )
    adj_list = edges_to_adjacency_list(reduced_edges)
    print(json.dumps(adj_list, indent=4))


def cycle_path_for_cycle(cycle: List[str]) -> List[Tuple[str, str]]:
    cycle_path: List[Tuple[str, str]] = []
    for idx in range(len(cycle) - 1):
        src = cycle[idx]
        dst = cycle[idx + 1]
        cycle_path.append((src, dst))
    cycle_path.append((cycle[-1], cycle[0]))
    return cycle_path


@cli.command("print_cycles", short_help="Output cycles found in the dependency graph")
@click.pass_context
def print_cycles(ctx: click.Context) -> None:
    config = ctx.obj
    edge_info = edge_info_for_config(config)
    path_lookup = generate_transitive_path_lookup(edge_info.path_edges)
    for src, path_dict in path_lookup.items():
        if src in path_dict:
            cycle: List[str] = edge_path_as_node_list(path_dict[src][0])
            cycle_path = cycle_path_for_cycle(cycle)
            print(f"cycle of length {len(cycle_path)} found from {src} ({cycle})")
            for src, dst in cycle_path:
                src_mod = path_to_mod(Path(src))
                dst_mod = path_to_mod(Path(dst))
                print(f"  {src} -> {dst} ({src_mod} -> {dst_mod})")


@cli.command(
    "print_cycles_legacy",
    short_help="(Legacy) output cycles found in the virtual dependency graph",
)
@click.option(
    "--ignore-cycles-in",
    "ignore_cycles_in",
    multiple=True,
    type=str,
    help="Ignore dependency cycles in a package",
)
@click.pass_context
def print_cycles_legacy(ctx: click.Context, ignore_cycles_in: List[str]) -> None:
    config = ctx.obj
    excluded_paths = config.excluded_paths
    ignore_cycles_in = config.ignore_cycles_in
    edge_info = edge_info_for_config(config)
    str_graph: Dict[str, List[str]] = edges_to_adjacency_list(edge_info.path_edges)
    graph: Dict[Path, List[Path]] = {
        Path(k): [Path(v) for v in vs] for k, vs in str_graph.items()
    }

    path_to_package: Dict[Path, str] = config.package_map_path(edge_info.node_metadata)

    # Define a nested function for recursive dependency searching.
    # top_level_package: The name of the package at the top of the dependency tree.
    # left_top_level: A boolean flag indicating whether we have moved beyond the top-level package in our traversal.
    # dependency: The current dependency path being examined.
    # already_seen: A list of dependency paths that have already been visited to avoid infinite loops.
    def recursive_dependency_search(
        top_level_package: str,
        left_top_level: bool,
        dependency: Path,
        already_seen: List[Path],
    ) -> List[List[Tuple[str, Path]]]:
        # Check if the dependency is in the list of already seen dependencies or is excluded.
        if dependency in already_seen or is_excluded(dependency, excluded_paths):
            return []

        # Mark this dependency as seen.
        already_seen.append(dependency)
        # Parse the dependency file to obtain its annotations.
        package: Optional[str] = path_to_package.get(dependency, None)

        # If there are no annotations, return an empty list as there's nothing to process.
        if package is None:
            return []
        # If the current dependency package matches the top-level package and we've left the top-level,
        # return a list containing this dependency.
        elif package == top_level_package and left_top_level:
            return [[(package, dependency)]]
        else:
            # Update the left_top_level flag if we have moved to a different package.
            left_top_level = left_top_level or package != top_level_package
            # Recursively search through all dependencies of the current dependency and accumulate the results.
            return [
                [(package, dependency), *stack]
                for stack in [
                    _stack
                    for dep in graph.get(dependency, [])
                    for _stack in recursive_dependency_search(
                        top_level_package, left_top_level, dep, already_seen
                    )
                ]
            ]

    # Initialize an accumulator for paths that are part of cycles.
    path_accumulator = []
    # Iterate over each package (parent) in the graph.
    for parent in graph:
        # Parse the parent package file.
        package: Optional[str] = path_to_package.get(parent, None)
        # Skip this package if it has no annotations or should be ignored in cycle detection.
        if package is None or package in ignore_cycles_in:
            continue
        # Extend the path_accumulator with results from the recursive search starting from this parent.
        path_accumulator.extend(recursive_dependency_search(package, False, parent, []))

    # Format and return the accumulated paths as strings showing the cycles.
    r = [
        " -> ".join([str(d) + f" ({p})" for p, d in stack])
        for stack in path_accumulator
    ]
    print("\n".join(r))


@cli.command(
    "extract",
    short_help="Interactive interface to extract a new package",
)
@click.argument("new_package_name", type=str)
@click.option(
    "--top", type=bool, is_flag=True, help="Peel nodes from tree top instead of bottom"
)
@click.pass_context
def do_extract(ctx: click.Context, new_package_name: str, top: bool) -> None:
    config = ctx.obj
    extract(config, new_package_name, top)


if __name__ == "__main__":
    cli()
