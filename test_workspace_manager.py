import tempfile
import unittest
from pathlib import Path

from workspace_manager import WorkspaceStore, initialize


class WorkspaceManagerTests(unittest.TestCase):
    def setUp(self):
        output = Path(__file__).resolve().parent / "output"
        output.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=output)
        self.addCleanup(self.temporary.cleanup)
        self.store = WorkspaceStore(self.temporary.name)

    def test_default_workspaces_are_isolated(self):
        initialize(self.store)
        index = self.store._index()
        self.assertEqual(index["active_workspace_id"], "ai-product-job-agent")
        self.assertEqual({item["id"] for item in index["workspaces"]}, {"ai-product-job-agent", "quant-smallcap-strategy"})
        self.store.append("ai-product-job-agent", "plans", {"id": "ai-plan"})
        self.assertEqual(self.store.load("quant-smallcap-strategy")["plans"], [])

    def test_cross_workspace_requires_explicit_share(self):
        initialize(self.store)
        self.store.explicitly_share("quant-smallcap-strategy", "ai-product-job-agent", "复用通用测试设计，不复制求职资料")
        shared = self.store.load("quant-smallcap-strategy")["shared_from"]
        self.assertEqual(shared[0]["workspace_id"], "ai-product-job-agent")
        self.assertEqual(self.store.load("ai-product-job-agent")["shared_from"], [])

    def test_bad_workspace_operations_rejected(self):
        with self.assertRaises(ValueError): self.store.create("BAD_ID", "x", "y")
        with self.assertRaises(ValueError): self.store.activate("missing")
        initialize(self.store)
        with self.assertRaises(ValueError): self.store.append("ai-product-job-agent", "secrets", {})


if __name__ == "__main__":
    unittest.main()
