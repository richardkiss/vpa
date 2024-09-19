from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TextIO

import json
import sys

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
    "--config",
    "config_path",
    type=click.File(),
    required=False,
    default=None,
    help="Path to the YAML configuration file.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    include_dir: Path,
    excluded_paths: List[Path],
    config_path: Optional[Path],
) -> None:
    config_ignore_cycles_in: List[str] = []
    package_contents: Dict[str, List[str]] = {}
    config_excluded_paths: List[Path] = []
    if config_path is not None:
        # Reading from the YAML configuration file
        config_data = yaml.safe_load(str(config_path))

        # Extracting required configuration values
        config_excluded_paths = [Path(p) for p in config_data.get("excluded_paths", [])]
        config_ignore_cycles_in = config_data.get("ignore_cycles_in", [])
        package_contents = config_data.get("package_contents", {})

    # Instantiating the Config object
    config = Config(
        dir_path=Path(include_dir),
        excluded_paths=[*excluded_paths, *config_excluded_paths],
        ignore_cycles_in=config_ignore_cycles_in,
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


@cli.command(
    "print_cycles", short_help="Output cycles found in the virtual dependency graph"
)
@click.option(
    "--ignore-cycles-in",
    "ignore_cycles_in",
    multiple=True,
    type=str,
    help="Ignore dependency cycles in a package",
)
@click.pass_context
def print_cycles(
    ctx: click.Context, ignore_cycles_in: List[str], f: TextIO = sys.stdout
) -> None:
    config = ctx.obj
    edge_info = edge_info_for_config(config)
    path_lookup = generate_transitive_path_lookup(edge_info.path_edges)

    for src, path_dict in path_lookup.items():
        if src in path_dict:
            cycle = edge_path_as_node_list(path_dict[src][0])
            print(f"cycle of length {len(cycle)} found from {src} ({cycle})", file=f)
            for idx in range(len(cycle) - 1):
                src = cycle[idx]
                dst = cycle[idx + 1]
                src_mod = path_to_mod(Path(src))
                dst_mod = path_to_mod(Path(dst))
                print(f"  {src} -> {dst} ({src_mod} -> {dst_mod})", file=f)


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


def main():
    cli()


if __name__ == "__main__":
    main()
