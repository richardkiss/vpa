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

from .package_annotation_map import PATH_TO_PACKAGE


@dataclass(frozen=True)
class PythonFile:
    path: Path
    annotation: Optional[str]

    @classmethod
    def parse(cls, file_path: Path) -> PythonFile:
        file_string = file_path.read_text(encoding="utf-8", errors="ignore")
        result = re.search(r"^# Package: (.+)$", file_string, re.MULTILINE)
        annotation = result.group(1).strip() if result else None
        return cls(file_path, annotation)


def build_dependency_graph(dir_params: DirectoryParameters) -> Dict[Path, List[Path]]:
    dependency_graph: Dict[Path, List[Path]] = {}
    for python_file in dir_params.gather_non_empty_python_files():
        dependency_graph[python_file.path] = []
        with open(python_file.path, encoding="utf-8", errors="ignore") as f:
            filestring = f.read()
            tree = ast.parse(filestring, filename=python_file.path)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module is not None and node.module.startswith(
                        dir_params.dir_path.stem
                    ):
                        imported_path = os.path.join(
                            dir_params.dir_path.parent,
                            node.module.replace(".", "/") + ".py",
                        )
                        paths_to_search = [
                            imported_path,
                            *(
                                os.path.join(imported_path[:-3], alias.name + ".py")
                                for alias in node.names
                            ),
                        ]
                        for path_to_search in paths_to_search:
                            if os.path.exists(path_to_search):
                                dependency_graph[python_file.path].append(
                                    Path(path_to_search)
                                )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(dir_params.dir_path.stem):
                            imported_path = os.path.join(
                                dir_params.dir_path.parent,
                                alias.name.replace(".", "/") + ".py",
                            )
                            if os.path.exists(imported_path):
                                dependency_graph[python_file.path].append(
                                    Path(imported_path)
                                )
    return dependency_graph


def build_virtual_dependency_graph(
    dir_params: DirectoryParameters,
) -> Dict[str, List[str]]:
    graph = build_dependency_graph(dir_params)
    virtual_graph: Dict[str, List[str]] = {}
    for file, imports in graph.items():
        root_file = PythonFile.parse(Path(file))
        if root_file.annotation is None:
            continue
        root = root_file.annotation
        virtual_graph.setdefault(root, [])

        dependency_files = [PythonFile.parse(Path(imp)) for imp in imports]
        dependencies = [
            f.annotation for f in dependency_files if f.annotation is not None
        ]

        virtual_graph[root].extend(dependencies)

    # Filter out self before returning the list
    return {k: list({v for v in vs if v != k}) for k, vs in virtual_graph.items()}


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


# Define a function to find cycles within a dependency graph.
# graph: A dictionary mapping each file to its list of dependencies.
# excluded_paths: A list of paths that should be excluded from the cycle detection.
# ignore_cycles_in: A list of package names where cycles, if found, should be ignored.
def find_cycles(
    graph: Dict[Path, List[Path]],
    excluded_paths: List[Path],
    ignore_cycles_in: List[str],
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
        python_file = PythonFile.parse(dependency)

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
        python_file = PythonFile.parse(parent)
        # Skip this package if it has no annotation or should be ignored in cycle detection.
        if (
            python_file.annotation is None
            or python_file.annotation in ignore_cycles_in
        ):
            continue
        # Extend the path_accumulator with results from the recursive search starting from this parent.
        path_accumulator.extend(
            recursive_dependency_search(
                python_file.annotation, False, parent, []
            )
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


@dataclass(frozen=True)
class DirectoryParameters:
    dir_path: Path
    excluded_paths: List[Path] = field(default_factory=list)

    def gather_non_empty_python_files(self) -> List[PythonFile]:
        """
        Gathers non-empty Python files in the specified directory while
        ignoring files and directories in the excluded paths.

        Returns:
            A list of paths to non-empty Python files.
        """
        python_files = []
        for root, dirs, files in os.walk(self.dir_path, topdown=True):
            # Modify dirs in-place to remove excluded directories from search
            dirs[:] = [
                d
                for d in dirs
                if Path(os.path.join(root, d)) not in self.excluded_paths
            ]

            for file in files:
                file_path = Path(os.path.join(root, file))
                # Check if the file is a Python file and not in the excluded paths
                if file_path.suffix == ".py" and file_path not in self.excluded_paths:
                    # Check if the file is non-empty
                    if os.path.getsize(file_path) > 0:
                        python_files.append(PythonFile.parse(file_path))

        return python_files


@dataclass
class Config:
    directory_parameters: DirectoryParameters
    ignore_cycles_in: List[str]


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
    print_graph(build_dependency_graph(config.directory_parameters))


@click.command(
    "print_virtual_dependency_graph",
    short_help="Output a dependency graph of all the packages in a directory",
)
@config
def print_virtual_dependency_graph(config: Config) -> None:
    print_graph(build_virtual_dependency_graph(config.directory_parameters))


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
        build_dependency_graph(config.directory_parameters),
        config.directory_parameters.excluded_paths,
        config.ignore_cycles_in,
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
