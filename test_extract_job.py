import copy
import unittest
from unittest.mock import patch
from extract_job import validate, payload, parse_response, extract


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.source = "任职要求：拥有RAG、知识图谱至少一项实战经验。具有海外产品经验者优先。"
        self.candidate = {"items": [
            {"summary": "RAG或知识图谱实战", "quote": "拥有RAG、知识图谱至少一项实战经验。", "kind": "required", "relation": "any_of"},
            {"summary": "海外产品经验", "quote": "具有海外产品经验者优先。", "kind": "preferred", "relation": "single"}]}

    def test_exact_spans(self):
        result = validate(self.source, self.candidate)
        for item in result["items"]:
            self.assertEqual(self.source[item["span"]["start"]:item["span"]["end"]], item["quote"])
        self.assertEqual(result["review_status"], "needs_semantic_review")

    def test_fabricated_quote(self):
        self.candidate["items"][0]["quote"] = "必须熟悉C++"
        with self.assertRaises(ValueError): validate(self.source, self.candidate)

    def test_required_preferred_conflict(self):
        self.candidate["items"][1]["kind"] = "required"
        with self.assertRaises(ValueError): validate(self.source, self.candidate)

    def test_any_of_preserved(self):
        self.candidate["items"][0]["relation"] = "all_of"
        with self.assertRaises(ValueError): validate(self.source, self.candidate)

    def test_bad_structure(self):
        for item in (None, {"items": "text"}, {"items": [{}]}, {"items": [], "extra": True}):
            with self.assertRaises(ValueError): validate(self.source, item)

    def test_duplicate(self):
        self.candidate["items"].append(copy.deepcopy(self.candidate["items"][0]))
        with self.assertRaises(ValueError): validate(self.source, self.candidate)

    def test_incomplete_refusal_and_invalid_json(self):
        for response in ({"status": "incomplete"}, {"status": "completed", "output": []},
                         {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]},
                         {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "bad"}]}]}):
            with self.assertRaises(ValueError): parse_response(response)

    def test_valid_response(self):
        self.assertEqual(parse_response({"status":"completed", "output":[{"type":"message", "content":[{"type":"output_text", "text":'{"items":[]}'}]}]}), {"items": []})

    def test_no_credentials_no_network(self):
        with patch.dict("os.environ", {}, clear=True), patch("extract_job.request.urlopen") as network:
            with self.assertRaises(ValueError): extract(self.source)
            network.assert_not_called()

    def test_payload_only_contains_job(self):
        result = payload(self.source, "configured-model")
        self.assertEqual(result["input"], self.source)
        self.assertFalse(result["store"])
        self.assertTrue(result["text"]["format"]["strict"])


if __name__ == "__main__":
    unittest.main()
