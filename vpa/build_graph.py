from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Dict, List

from .directory_parameters import DirectoryParameters
from .python_file import PythonFile


def build_dependency_graph(
    dir_params: DirectoryParameters, annotation_override: Dict[Path, str]
) -> Dict[Path, List[Path]]:
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
    annotation_override: Dict[Path, str],
) -> Dict[str, List[str]]:
    graph = build_dependency_graph(dir_params, annotation_override)
    virtual_graph: Dict[str, List[str]] = {}
    for file, imports in graph.items():
        root_file = PythonFile.parse(Path(file), annotation_override)
        if root_file.annotation is None:
            continue
        root = root_file.annotation
        virtual_graph.setdefault(root, [])

        dependency_files = [
            PythonFile.parse(Path(imp), annotation_override) for imp in imports
        ]
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
