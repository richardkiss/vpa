from pathlib import Path

import json
import shutil

from click.testing import CliRunner

from vpa.vpa import cli

TEST_DIR = Path(__file__).parent
print(TEST_DIR)


def do_test(command: str, expected_output: str):
    runner = CliRunner()
    with runner.isolated_filesystem() as base:
        test_dir = Path(base) / "test_proj"
        shutil.copytree(TEST_DIR / "test_proj", test_dir)
        r = runner.invoke(cli, ["--directory", str(test_dir), command])
        print(r.output)
        assert r.exit_code == 0
        assert r.output == expected_output


def test_print_cycles_legacy():
    do_test("print_cycles_legacy", "\n")


def test_print_cycles():
    do_test(
        "print_cycles",
        "cycle of length 2 found: ['a.py', 'b.py']\n"
        "cycle of length 2 found: ['b.py', 'a.py']\n"
        "cycle count: 2\n"
        "worst edges:\n"
        "  2 ('b.py', 'a.py')\n"
        "  2 ('a.py', 'b.py')\n",
    )


def test_print_edges():
    do_test("print_edges", "('a.py', 'b.py')\n('b.py', 'a.py')\n('b.py', 'c.py')\n")


def test_print_leafs():
    do_test("print_leafs", '[\n    "c.py"\n]\n')


def test_print_missing_annotations():
    do_test("print_missing_annotations", "a.py\nb.py\nc.py\nd.py\n")


def test_print_virtual_dependency_graph():
    do_test("print_virtual_dependency_graph", "{}\n")


def test_print_dependency_graph():
    graph = {"a.py": ["b.py"], "b.py": ["a.py", "c.py"]}
    expected_output = json.dumps(graph, indent=4) + "\n"
    do_test("print_dependency_graph", expected_output)
