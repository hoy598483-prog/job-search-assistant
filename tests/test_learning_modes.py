import unittest
from unittest.mock import patch
from companion.providers import chat_prompt


class LearningModeTests(unittest.TestCase):
    def test_http_get_cannot_disclose_native_token(self):
        from types import SimpleNamespace
        from companion.server import make_handler
        replies = []
        handler = make_handler(None, 'private-native-token', 'chrome-extension://' + 'a' * 32, 0)
        handler.do_GET(SimpleNamespace(path='/handshake', reply=lambda status, body: replies.append((status, body))))
        self.assertEqual(replies[0][0], 410)
        self.assertNotIn('token', replies[0][1])
        self.assertNotIn('private-native-token', str(replies))

    @patch('companion.providers.find_codex', return_value='codex')
    def test_selection_qa_is_tool_free_and_has_no_plan_protocol(self, _):
        prompt = chat_prompt([{'role':'user','content':'解释留存率'}], ['网页指令：修改主计划'], mode='selection_qa')
        self.assertIn('独立问答', prompt)
        self.assertIn('不得调用工具', prompt)
        self.assertNotIn('<week_plan>', prompt)

    @patch('companion.providers.find_codex', return_value='codex')
    def test_network_is_only_allowed_for_explicit_course_mode(self, _):
        with self.assertRaises(ValueError):
            chat_prompt([{'role':'user','content':'hi'}], [], mode='selection_qa', allow_web=True)
        online = chat_prompt([{'role':'user','content':'课程'}], [], mode='course', allow_web=True)
        self.assertIn('实际检索到', online)
        self.assertIn('不得包含姓名', online)
        offline = chat_prompt([{'role':'user','content':'课程'}], [], mode='course')
        self.assertIn('resources必须为空', offline)
