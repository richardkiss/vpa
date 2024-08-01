from __future__ import annotations

import ast
import json
import re
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import click
import yaml

from .build_graph import (
    build_dependency_graph,
    build_virtual_dependency_graph,
    is_excluded,
)
from .directory_parameters import DirectoryParameters
from .python_file import PythonFile


from .package_annotation_map import PATH_TO_PACKAGE


# Define a function to find cycles within a dependency graph.
# graph: A dictionary mapping each file to its list of dependencies.
# excluded_paths: A list of paths that should be excluded from the cycle detection.
# ignore_cycles_in: A list of package names where cycles, if found, should be ignored.
def find_cycles(
    graph: Dict[Path, List[Path]],
    excluded_paths: List[Path],
    ignore_cycles_in: List[str],
    annotation_override: Dict[Path, str],
) -> List[str]:
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
        python_file = PythonFile.parse(dependency, annotation_override)

        # If there are no annotations, return an empty list as there's nothing to process.
        if python_file.annotation is None:
            return []
        # If the current dependency package matches the top-level package and we've left the top-level,
        # return a list containing this dependency.
        elif python_file.annotation == top_level_package and left_top_level:
            return [[(python_file.annotation, dependency)]]
        else:
            # Update the left_top_level flag if we have moved to a different package.
            left_top_level = (
                left_top_level or python_file.annotation != top_level_package
            )
            # Recursively search through all dependencies of the current dependency and accumulate the results.
            return [
                [(python_file.annotation, dependency), *stack]
                for stack in [
                    _stack
                    for dep in graph[dependency]
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
        python_file = PythonFile.parse(parent, annotation_override)
        # Skip this package if it has no annotation or should be ignored in cycle detection.
        if python_file.annotation is None or python_file.annotation in ignore_cycles_in:
            continue
        # Extend the path_accumulator with results from the recursive search starting from this parent.
        path_accumulator.extend(
            recursive_dependency_search(python_file.annotation, False, parent, [])
        )

    # Format and return the accumulated paths as strings showing the cycles.
    return [
        " -> ".join([str(d) + f" ({p})" for p, d in stack])
        for stack in path_accumulator
    ]


def print_graph(graph: Union[Dict[str, List[str]], Dict[Path, List[Path]]]) -> None:
    print(
        json.dumps(
            {str(k): list(str(v) for v in vs) for k, vs in graph.items()}, indent=4
        )
    )


@click.group(
    help="A utility for grouping different parts of the repo into separate projects"
)
def cli() -> None:
    pass


@dataclass
class Config:
    directory_parameters: DirectoryParameters
    ignore_cycles_in: List[str]
    annotation_override: Dict[Path, str]


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
        if config_path is not None:
            # Reading from the YAML configuration file
            with open(config_path) as file:
                config_data = yaml.safe_load(file)

            # Extracting required configuration values
            exclude_paths = [Path(p) for p in config_data.get("exclude_paths", [])]
            ignore_cycles_in = config_data.get("ignore_cycles_in", [])

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
            annotation_override=PATH_TO_PACKAGE,
        )

        # Calling the wrapped function with the Config object and other arguments
        return func(config, *args, **kwargs)

    return inner


@click.command(
    "find_missing_annotations",
    short_help="Search a directory for python files without annotations",
)
@config
def find_missing_annotations(config: Config) -> None:
    flag = False
    for file in config.directory_parameters.gather_non_empty_python_files():
        if file.annotation is None:
            print(file.path)
            flag = True

    if flag:
        sys.exit(1)


@click.command(
    "print_dependency_graph",
    short_help="Output a dependency graph of all the files in a directory",
)
@config
def print_dependency_graph(config: Config) -> None:
    print_graph(
        build_dependency_graph(config.directory_parameters, config.annotation_override)
    )


@click.command(
    "print_virtual_dependency_graph",
    short_help="Output a dependency graph of all the packages in a directory",
)
@config
def print_virtual_dependency_graph(config: Config) -> None:
    print_graph(
        build_virtual_dependency_graph(
            config.directory_parameters, config.annotation_override
        )
    )


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
    flag = False
    for cycle in find_cycles(
        build_dependency_graph(config.directory_parameters, config.annotation_override),
        config.directory_parameters.excluded_paths,
        config.ignore_cycles_in,
        config.annotation_override,
    ):
        print(cycle)
        flag = True

    if flag:
        sys.exit(1)


cli.add_command(find_missing_annotations)
cli.add_command(print_dependency_graph)
cli.add_command(print_virtual_dependency_graph)
cli.add_command(print_cycles)

if __name__ == "__main__":
    cli()
