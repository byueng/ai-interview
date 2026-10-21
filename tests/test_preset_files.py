import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.file import read_json, write_json, write_unique_json
from backend.errors import InvalidPresetNameError
from backend import preset_service


class PresetFileTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "presets"
        self.path = self.root / "Agent面试.json"

    def test_first_save_creates_parent_and_uses_original_name(self):
        saved = write_unique_json(self.path, {"position": "Agent面试"})
        self.assertEqual(saved, self.path)
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8")), {"position": "Agent面试"})

    def test_repeated_saves_preserve_all_contents(self):
        paths = [write_unique_json(self.path, {"index": i}) for i in range(4)]
        self.assertEqual(
            [p.name for p in paths],
            ["Agent面试.json", "Agent面试(1).json", "Agent面试(2).json", "Agent面试(3).json"],
        )
        self.assertEqual([json.loads(p.read_text(encoding="utf-8"))["index"] for p in paths], list(range(4)))

    def test_numbered_files_without_original_continue_from_maximum(self):
        write_unique_json(self.root / "Agent面试(3).json", {})
        write_unique_json(self.root / "Agent面试(10).json", {})
        self.assertEqual(write_unique_json(self.path, {}).name, "Agent面试(11).json")

    def test_escapes_name_and_ignores_unrelated_names(self):
        target = self.root / "Agent+(后端).json"
        write_unique_json(self.root / "Agent+(后端)开发(99).json", {})
        self.assertEqual(write_unique_json(target, {}), target)
        self.assertEqual(write_unique_json(target, {}).name, "Agent+(后端)(1).json")

    def test_directory_also_reserves_name(self):
        self.path.mkdir(parents=True)
        self.assertEqual(write_unique_json(self.path, {}).name, "Agent面试(1).json")

    def test_collision_between_scan_and_open_retries(self):
        original_open = Path.open
        collided = False

        def racing_open(path, mode="r", *args, **kwargs):
            nonlocal collided
            if mode == "x" and not collided:
                collided = True
                with original_open(path, "x", encoding="utf-8") as file:
                    file.write('{"existing": true}')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", racing_open):
            saved = write_unique_json(self.path, {"new": True})
        self.assertEqual(saved.name, "Agent面试(1).json")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"existing": True})

    def test_concurrent_saves_do_not_overwrite(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            paths = list(executor.map(lambda i: write_unique_json(self.path, {"index": i}), range(20)))
        self.assertEqual(len(set(paths)), 20)
        self.assertEqual({json.loads(p.read_text(encoding="utf-8"))["index"] for p in paths}, set(range(20)))

    def test_invalid_data_does_not_create_file(self):
        with self.assertRaises(TypeError):
            write_unique_json(self.path, {"invalid": object()})
        self.assertFalse(self.path.exists())

    def test_snapshot_writer_still_overwrites(self):
        self.root.mkdir()
        write_json(self.path, {"version": 1})
        write_json(self.path, {"version": 2})
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"version": 2})

    def test_snapshot_writer_creates_parent(self):
        write_json(self.path, {"version": 1})
        self.assertEqual(read_json(self.path), {"version": 1})

    def test_invalid_snapshot_data_does_not_truncate_existing_file(self):
        write_json(self.path, {"version": 1})
        with self.assertRaises(TypeError):
            write_json(self.path, {"invalid": object()})
        self.assertEqual(read_json(self.path), {"version": 1})

    def test_reader_uses_read_only_mode(self):
        write_json(self.path, {})
        with patch("backend.file.open", wraps=open) as opened:
            self.assertEqual(read_json(self.path), {})
        self.assertEqual(opened.call_args.kwargs["mode"], "r")

    def test_symlink_guard_rejects_read_and_delete_before_file_access(self):
        # Keep the guard covered even when Windows cannot create a real symlink.
        with patch.object(preset_service, "data_directory", return_value=self.root), \
             patch.object(Path, "is_symlink", return_value=True), \
             patch.object(preset_service, "read_json") as read, \
             patch.object(Path, "unlink") as unlink:
            for operation in (preset_service.read_preset, preset_service.delete_preset):
                with self.subTest(operation=operation.__name__):
                    with self.assertRaises(InvalidPresetNameError):
                        operation("link.json")
            read.assert_not_called()
            unlink.assert_not_called()
