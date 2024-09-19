from __future__ import annotations

from pathlib import Path
from typing import Iterator, Tuple

import ast


def imports_for_python_file(
    contents: str, top_level_only: bool = True
) -> Iterator[Tuple[str, int]]:
    node_iter = ast.iter_child_nodes if top_level_only else ast.walk
    tree = ast.parse(contents)
    for node in node_iter(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is not None:
                yield node.module, node.level
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, 0


def imp_to_mod(imp: str, current_mod: str, level: int) -> str:
    if level == 0:
        return imp
    current_mod_parts = current_mod.split(".")
    if level > len(current_mod_parts):
        raise ValueError(f"Import level {level} is too deep for module {current_mod}")
    return ".".join(current_mod_parts[:-level] + [imp])


def mods_imported_for_python_file(
    contents: str, base_dir: Path, filepath: Path
) -> Iterator[str]:
    current_mod = path_to_mod(filepath, base_dir)
    for imp, level in imports_for_python_file(contents):
        yield imp_to_mod(imp, current_mod, level)


def path_to_mod(path: Path, mod_root_path: Path = Path(".")) -> str:
    mod_path = path.relative_to(mod_root_path)
    mod_name = ".".join(mod_path.parts)
    if path.suffix == ".py":
        # check if it's `__init__.py`
        if mod_name.endswith(".__init__.py"):
            mod_name = mod_name[:-12]
        else:
            mod_name = mod_name[:-3]
    return mod_name
