from pathlib import Path

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
        r = runner.invoke(cli, ["--directory", test_dir, command])
        print(r.output)
        assert r.exit_code == 0
        assert r.output == expected_output


def test_print_cycles():
    do_test("print_cycles", "\n")


def test_find_cycles():
    do_test(
        "find_cycles",
        "cycle of length 2 found from a.py (['b.py', 'a.py'])\n  b.py -> a.py (b -> a)\n  a.py -> b.py (a -> b)\ncycle of length 2 found from b.py (['a.py', 'b.py'])\n  a.py -> b.py (a -> b)\n  b.py -> a.py (b -> a)\n",
    )


def test_print_edges():
    do_test("print_edges", "('a.py', 'b.py')\n('b.py', 'a.py')\n")


def test_print_leafs():
    do_test("print_leafs", "[]\n")


def test_print_missing_annotations():
    do_test("print_missing_annotations", "a.py\nb.py\n")


def test_print_virtual_dependency_graph():
    do_test("print_virtual_dependency_graph", "{}\n")
