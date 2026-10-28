import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.preset_service import save_preset
from schemas import InterviewPreset


class PresetDedupTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict('os.environ', {'DATA_DIR': str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        self.preset = InterviewPreset.model_validate({
            'candidate_config': {'language': 'zh-CN', 'education': '本科', 'position': '后端'},
            'interviewer_config': {'role_identity': '面试官', 'role_responsibilities': '技术面试'},
        })

    def test_identical_configuration_reuses_file_without_rewriting(self):
        path = save_preset(self.preset)
        before = path.stat().st_mtime_ns
        self.preset.candidate_config.resume = '/data/swap/another-session/简历.pdf'
        self.assertEqual(save_preset(self.preset), path)
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_language_aliases_and_form_whitespace_do_not_create_copies(self):
        self.preset.candidate_config.language = '中文'
        self.preset.interviewer_config.role_identity = ' 面试官 '
        path = save_preset(self.preset)
        self.preset.candidate_config.language = 'zh-CN'
        self.preset.interviewer_config.role_identity = '面试官'
        self.assertEqual(save_preset(self.preset), path)

    def test_changed_configuration_creates_new_preset_without_overwriting(self):
        original = save_preset(self.preset)
        content = original.read_bytes()
        self.preset.interviewer_config.role_responsibilities = '系统设计'
        changed = save_preset(self.preset)
        self.assertEqual(changed.name, '后端(1).json')
        self.assertEqual(original.read_bytes(), content)
        self.assertEqual(save_preset(self.preset), changed)

    def test_renamed_preset_is_reused_and_corrupt_files_are_left_untouched(self):
        original = save_preset(self.preset)
        renamed = original.with_name('自定义.json')
        original.rename(renamed)
        original.write_text('{broken', encoding='utf-8')
        self.assertEqual(save_preset(self.preset), renamed)
        self.assertEqual(original.read_text(), '{broken')

    def test_simultaneous_identical_saves_create_one_file(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            paths = list(executor.map(lambda _: save_preset(self.preset), range(12)))
        self.assertEqual(len(set(paths)), 1)
        self.assertEqual(len(list(paths[0].parent.glob('*.json'))), 1)
