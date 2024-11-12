# Uncycle

Uncycle is a Python tool designed to analyze and reorganize Python projects by generating a graph of imports and assisting in the refactoring process. It helps in identifying and minimizing cross-dependencies, making it easier to split large projects into smaller, more manageable modules or packages.

## Features

- **Import Graph Generation**: Automatically scans Python files in a project and generates a graph of module imports.
- **Dependency Analysis**: Identifies and maps out cross-dependencies among modules.
- **Interactive Refactoring**: Provides an interactive interface to assist in refactoring decisions.
- **Bottom-up or Top-down Approach**: Allows refactoring from either the bottom (default) or the top of the dependency graph.
- **YAML Configuration**: Supports configuration via YAML files for excluding paths and defining package contents.

## Why Use uncycle?

Sometimes, projects grow too large and contain a mix of code at various levels, making them difficult to maintain. Because Python does not allow circular dependencies, the import graph provides hints about which source files are high-level and which are low-level. This tool imports the graph and allows you to extract files from either the bottom (default) or the top, facilitating their refactoring into new, independent packages.

## Installation

(Add installation instructions here, e.g., pip install command or setup process)

## Usage

To use uncycle, follow these steps:

1. Navigate to your project directory.
2. (Optional) Create a YAML configuration file (see Configuration section below).
3. Run the uncycle command with the desired options:

```
uncycle extract --directory <target_directory> <source_directory> [--config <config_file.yaml>]
```

For example:

```
uncycle extract --directory projects/chia chia_core --config uncycle_config.yaml
```

4. The tool will present an interactive interface, allowing you to:

   - View file contents
   - Move files to the target directory
   - Reject files from being moved
   - List dependencies and dependents of each file
   - Navigate through the project structure

5. Make decisions about each file presented, considering its dependencies and usage within the project.

6. Once finished, the tool will output a summary of the files moved to the new package.

## Configuration

You can use a YAML configuration file to exclude certain paths and predefine package contents. Here's an example of what the YAML file might look like:

```yaml
excluded_paths:
  - "chia/_tests"
  - "tools"
  - "benchmarks"

package_contents:
  chia.simulator:
    - "chia/util/timing.py"
    - "chia/simulator/socket.py"
    - "chia/simulator/ssl_certs_1.py"
    - "chia/simulator/ssl_certs_2.py"
    # ... more files ...

  chia.core:
    - "chia/util/cpu.py"
    - "chia/consensus/condition_costs.py"
    - "chia/consensus/difficulty_adjustment.py"
    # ... more files ...
```

- `excluded_paths`: Lists directories or files to be excluded from the analysis.
- `package_contents`: Defines the desired structure of your packages, listing which files should be included in each package.

Note: Existing packages are considered okay to import, as the tool is designed to help refactor large projects into several smaller packages.

## Output

After running uncycle, it will produce a summary output of the files you selected to move (either interactively or via the configuration file). This output can be used to guide your refactoring process.

## Example Interaction

Here's a snippet of what interacting with uncycle looks like:

```
-------
** `chia/util/collection.py` has 18 line(s); used by 2 file(s)

Choose:
ret: enumerate all potential nodes
  l: view `chia/util/collection.py` with `less`
  y: move `chia/util/collection.py` to chia_core
  n: reject `chia/util/collection.py` from chia_core and remove from list
  u: list all nodes "used by" `chia/util/collection.py`
  i: list all nodes "imported" by `chia/util/collection.py`
  q: quit
int: choose a different node to consider
```
