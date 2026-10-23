import io
import json
import unittest
from unittest.mock import patch

from companion.streaming import chat_stream


class FakeProcess:
    def __init__(self, events):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO("".join(json.dumps(event) + "\n" for event in events))
        self.killed = False

    def poll(self):
        return 0 if self.killed else None

    def kill(self):
        self.killed = True

    def wait(self, timeout):
        return 0


class StreamingTests(unittest.TestCase):
    @patch("companion.providers.shutil.which", return_value="codex")
    def test_course_final_answer_excludes_search_commentary(self, _):
        process = FakeProcess([
            {"method":"item/started","params":{"item":{"type":"webSearch"}}},
            {"method":"item/agentMessage/delta","params":{"delta":"正在搜索"}},
            {"method":"item/completed","params":{"item":{"type":"agentMessage","phase":"commentary","text":"正在搜索"}}},
            {"method":"item/agentMessage/delta","params":{"delta":"{\"title\":\"课程\"}"}},
            {"method":"item/completed","params":{"item":{"type":"agentMessage","phase":"final_answer","text":"{\"title\":\"课程\"}"}}},
            {"method":"turn/completed","params":{"turn":{"status":"completed"}}},
        ])
        with patch("companion.streaming.subprocess.Popen", return_value=process):
            result = list(chat_stream([{"role":"user","content":"生成课"}], [], mode="course", allow_web=True))
        self.assertEqual(result[-1]["reply"], '{"title":"课程"}')

    def stream(self, events):
        process = FakeProcess(events)
        return process, patch("companion.streaming.subprocess.Popen", return_value=process)

    @patch("companion.providers.shutil.which", return_value="codex")
    def test_real_delta_order_and_cleanup(self, _):
        process, mocked = self.stream([
            {"id":1, "result":{}},
            {"id":2, "result":{"thread":{"id":"thread-1"}}},
            {"method":"item/agentMessage/delta", "params":{"delta":"你好"}},
            {"method":"item/agentMessage/delta", "params":{"delta":"，世界"}},
            {"method":"turn/completed", "params":{"turn":{"status":"completed"}}},
        ])
        with mocked:
            events = list(chat_stream([{"role":"user", "content":"hello"}], []))
        self.assertEqual([e["text"] for e in events if e["type"] == "delta"], ["你好", "，世界"])
        self.assertEqual(events[-1], {"type":"done", "reply":"你好，世界"})
        self.assertTrue(process.killed)

    @patch("companion.providers.shutil.which", return_value="codex")
    def test_disconnect_closes_process(self, _):
        process, mocked = self.stream([])
        with mocked:
            stream = chat_stream([{"role":"user", "content":"hello"}], [])
            next(stream)
            stream.close()
        self.assertTrue(process.killed)

    @patch("companion.providers.shutil.which", return_value="codex")
    def test_incomplete_stream_is_not_success(self, _):
        process, mocked = self.stream([
            {"method":"item/agentMessage/delta", "params":{"delta":"部分"}},
        ])
        with mocked, self.assertRaises(ValueError):
            list(chat_stream([{"role":"user", "content":"hello"}], []))
        self.assertTrue(process.killed)
