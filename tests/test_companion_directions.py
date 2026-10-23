import tempfile
import unittest

from companion.service import Companion


class DirectionTests(unittest.TestCase):
    def test_create_route_and_isolate_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Companion(directory)
            for workspace in ("direction-agent", "direction-product"):
                result = service.handle({"workspace":workspace, "direction":{"name":workspace,"target":"准备岗位"},
                                         "action":"save", "approved":True, "page":{"text":workspace}})
                self.assertIn("saved", result)
            first = service.handle({"workspace":"direction-agent", "action":"list"})
            second = service.handle({"workspace":"direction-product", "action":"list"})
            self.assertNotEqual(first["jobs"][0]["id"], second["jobs"][0]["id"])
            self.assertEqual(len(first["jobs"]), 1)
            self.assertEqual(len(second["jobs"]), 1)

    def test_invalid_route_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Companion(directory)
            with self.assertRaises(ValueError):
                service.route("../escape", {"name":"x", "target":"y"})
            with self.assertRaises(ValueError):
                service.route("direction-empty", {"name":"", "target":"y"})
