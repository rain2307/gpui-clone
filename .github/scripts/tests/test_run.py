import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import toml


RUN_SCRIPT = Path(__file__).resolve().parents[1] / "run.py"
SPEC = importlib.util.spec_from_file_location("sync_run", RUN_SCRIPT)
sync_run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_run)


class LocalPatchRootsTests(unittest.TestCase):
    def test_collects_repository_root_for_local_patch(self):
        cargo_toml = toml.loads(
            """
            [patch.crates-io]
            scratch = { path = "corgi-patches/scratch" }
            """
        )

        self.assertEqual(sync_run.get_local_patch_roots(cargo_toml), {"corgi-patches"})

    def test_ignores_patch_paths_outside_repository(self):
        cargo_toml = toml.loads(
            """
            [patch.crates-io]
            parent = { path = "../parent-patch" }
            absolute = { path = "/tmp/absolute-patch" }
            registry = { version = "1" }
            """
        )

        self.assertEqual(sync_run.get_local_patch_roots(cargo_toml), set())

    def test_root_cleanup_keeps_local_patch_manifest(self):
        cargo_toml = toml.loads(
            """
            [workspace]
            members = ["crates/app"]
            resolver = "2"

            [patch.crates-io]
            scratch = { path = "corgi-patches/scratch" }
            """
        )

        with tempfile.TemporaryDirectory() as output_dir:
            output_path = Path(output_dir)
            sync_run.write_toml(output_path / "Cargo.toml", cargo_toml)

            app_path = output_path / "crates" / "app"
            (app_path / "src").mkdir(parents=True)
            (app_path / "Cargo.toml").write_text(
                "[package]\nname = 'app'\nversion = '0.1.0'\nedition = '2021'\n"
                "[dependencies]\nscratch = '1.0.9'\n"
            )
            (app_path / "src" / "lib.rs").write_text("")

            patch_path = output_path / "corgi-patches" / "scratch"
            (patch_path / "src").mkdir(parents=True)
            (patch_path / "Cargo.toml").write_text(
                "[package]\nname = 'scratch'\nversion = '1.0.9'\nedition = '2021'\n"
            )
            (patch_path / "src" / "lib.rs").write_text("")

            disposable_path = output_path / "docs"
            disposable_path.mkdir()

            sync_run.clean_root_files(output_dir, cargo_toml)

            self.assertTrue((patch_path / "Cargo.toml").is_file())
            self.assertFalse(disposable_path.exists())

            if shutil.which("cargo"):
                subprocess.run(
                    ["cargo", "metadata", "--no-deps", "--offline", "--format-version", "1"],
                    cwd=output_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )


if __name__ == "__main__":
    unittest.main()
