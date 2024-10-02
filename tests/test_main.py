from pathlib import Path

import shutil

from click.testing import CliRunner

from vpa.vpa import cli

TEST_DIR = Path(__file__).parent
print(TEST_DIR)


def test_print_cycles():
    test_proj_dir = TEST_DIR / "test_proj"
    runner = CliRunner()
    with runner.isolated_filesystem() as base:
        # need to cp -r test_proj_dir base
        test_dir = Path(base) / "test_proj"
        shutil.copytree(test_proj_dir, test_dir)
        r = runner.invoke(cli, ["--directory", test_dir, "print_cycles"])
        print(r.output)
        assert r.exit_code == 0
        assert r.output == "\n"


def test_find_cycles():
    test_proj_dir = TEST_DIR / "test_proj"
    runner = CliRunner()
    with runner.isolated_filesystem() as base:
        # need to cp -r test_proj_dir base
        test_dir = Path(base) / "test_proj"
        shutil.copytree(test_proj_dir, test_dir)
        r = runner.invoke(cli, ["--directory", test_dir, "find_cycles"])
        print(r.output)
        assert r.exit_code == 0
        assert (
            r.output
            == "cycle of length 2 found from a.py (['b.py', 'a.py'])\n  b.py -> a.py (b -> a)\n  a.py -> b.py (a -> b)\ncycle of length 2 found from b.py (['a.py', 'b.py'])\n  a.py -> b.py (a -> b)\n  b.py -> a.py (b -> a)\n"
        )
