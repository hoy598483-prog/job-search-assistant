import unittest
from simulate_terra import markdown, run


class TerraSimulationTests(unittest.TestCase):
    def test_generated_testset_passes_local_validation(self):
        dataset, results = run()
        self.assertEqual(len(dataset["cases"]), 8)
        self.assertTrue(all(result["status"] == "passed" for result in results))

    def test_report_discloses_simulation(self):
        dataset, results = run()
        report = markdown(dataset, results)
        self.assertIn("未调用真实模型", report)
        self.assertIn("T07", report)
        self.assertIn("T08", report)


if __name__ == "__main__":
    unittest.main()
