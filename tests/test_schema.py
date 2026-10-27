import copy
import json
import os
import unittest
from itertools import product
from types import SimpleNamespace
from typing import Optional
from unittest.mock import patch

from SchemaDiagnoser import fn

try:
    import httpx2
    from typesafe_sdk import TypeSafeClient
except ImportError:
    TypeSafeClient = None


class SchemaTests(unittest.TestCase):
    def test_batch_validity_equals_every_row_validity(self):
        rows = [{}, *({"x": value} for value in (0, True, 1.0, "1", None, [], {}))]
        for dtype, allow_extra, first, second, extra in product(
            (int, bool, float, str, list, dict, int | None, int | float,
             int | float | None, type(None), str | None),
            (True, False), rows, rows, ({}, {"extra": None})
        ):
            contract, batch = {"x": dtype}, [first | extra, second]
            expected = all(fn.check_schema(contract, [row], allow_extra=allow_extra)["valid"]
                           for row in batch)
            self.assertEqual(fn.check_schema(contract, batch, allow_extra=allow_extra)["valid"],
                             expected, (contract, batch))

    def test_nulls_block_nonnullable_fields(self):
        for rows in ([{"id": None}], [{"id": 1}, {"id": None}]):
            result = fn.check_schema({"id": int}, rows)
            self.assertFalse(result["valid"])
            self.assertIn("null_values", result["changes"][0]["issues"])
            self.assertTrue(result["changes"][0]["blocking"])
            self.assertEqual(result["changes"][0]["evidence"]["null_count"], 1)

    def test_explicit_unions_allow_only_declared_types_without_coercion(self):
        for dtype in (int | float | None, "integer | float64 | None", Optional[int | float]):
            rows = [{"x": 1}, {"x": 1.5}, {"x": None}]
            original = copy.deepcopy(rows)
            report = fn.check_schema({"x": dtype}, rows, ai_review=True)
            self.assertTrue(report["valid"])
            self.assertEqual(report["changes"], [])
            self.assertEqual(report["review"]["status"], "not_needed")
            self.assertEqual(rows, original)
            for value in (True, "1"):
                self.assertFalse(fn.check_schema({"x": dtype}, [{"x": value}])["valid"])
            self.assertFalse(fn.check_schema({"x": dtype}, [{}])["valid"])
        for dtype in (None, type(None), "null", "NoneType"):
            self.assertTrue(fn.check_schema({"x": dtype}, [{"x": None}])["valid"])
            self.assertFalse(fn.check_schema({"x": dtype}, [{"x": 1}])["valid"])

    def test_metadata_unions_use_subset_compatibility(self):
        contract = {"x": "int|float|null"}
        for dtype in (int, float, None, "float|int", "int|null"):
            self.assertTrue(fn.check_schema(contract, {"x": dtype})["valid"])
        for dtype in (bool, "int|str", "unknown", "mixed", "unknown|null"):
            self.assertFalse(fn.check_schema(contract, {"x": dtype})["valid"])
        self.assertEqual(fn._schema({"x": "integer|int|float64"}), {"x": "float|int"})

    def test_supported_contract_forms_and_empty_incoming_schemas(self):
        forms = [{"id": "INTEGER"}, [("id", int)], {"schema": {"id": int}},
                 {"contract": {"schema": [("id", int)]}},
                 {"columns": ["id"], "dtypes": [int]}, {"columns": ["id"], "types": [int]}]
        for contract in forms:
            self.assertTrue(fn.check_schema(contract, [{"id": 1}])["valid"])
            for incoming in ({}, {"columns": [], "dtypes": []}, {"columns": [], "types": []}):
                result = fn.check_schema(contract, incoming)
                self.assertFalse(result["valid"])
                self.assertEqual(result["changes"][0]["issues"], ["missing"])
        fields = {name: str for name in ("schema", "contract", "columns", "dtypes", "types")}
        self.assertTrue(fn.check_schema(fields, fields)["valid"])

    def test_ambiguous_empty_and_inference_only_contracts_are_rejected(self):
        bad = [{}, [], [("x", int), ("x", str)], {"": int},
               {"schema": {"x": int}, "contract": {"x": str}},
               {"columns": ["x"], "dtypes": [], "types": [int]},
               {"columns": ["x"], "dtypes": [int], "types": [str]},
               {"columns": ["x"], "dtypes": []}]
        bad.extend({"x": dtype} for dtype in ("unknown", "mixed", "int|unknown", "mixed|null", "int|", ""))
        for contract in bad:
            with self.subTest(contract=contract), self.assertRaises((ValueError, TypeError)):
                fn.check_schema(contract, [{"x": None}])

    def test_malformed_incoming_is_an_input_error_not_a_schema_report(self):
        for incoming in ([], [1], [{"": 1}], "not a schema"):
            with self.subTest(incoming=incoming), self.assertRaises((TypeError, ValueError)):
                fn.check_schema({"x": int}, incoming)

    def test_type_and_presence_changes_remain_strict(self):
        for incoming in ([{"id": True}], [{"id": "1"}], [{"id": 1.0}], [{"Id": 1}], [{}]):
            self.assertFalse(fn.check_schema({"id": int}, incoming, allow_extra=True)["valid"])
        for incoming in ({"id": "unknown"}, {"id": "mixed"}):
            self.assertFalse(fn.check_schema({"id": int}, incoming)["valid"])
        self.assertFalse(fn.check_schema({"id": int}, [{"id": 1, "extra": 1}])["valid"])
        self.assertTrue(fn.check_schema({"id": int}, [{"id": 1, "extra": None}], allow_extra=True)["valid"])

    def test_evidence_is_fresh_bounded_and_does_not_expose_values(self):
        rows = [{"id": "private"} for _ in range(10)] + [{}, {"id": None}]
        original = copy.deepcopy(rows)
        result = fn.check_schema({"id": int}, rows)
        self.assertEqual(rows, original)
        self.assertNotIn("private", json.dumps(result))
        evidence = result["changes"][0]["evidence"]
        self.assertEqual(evidence["example_rows"]["str"], [0, 1, 2])
        self.assertEqual((evidence["missing_count"], evidence["null_count"]), (1, 1))

    def test_invalid_ai_distributions_are_rejected(self):
        options = {"a": "First", "b": "Second"}
        for probabilities, confidence in (({"a": True, "b": False}, 1),
                ({"a": 0, "b": 0}, 0), ({"a": 0.9, "b": 0.9}, 1),
                ({"a": float("nan"), "b": 0}, 1), ({"a": float("inf"), "b": 0}, 1),
                ({"a": 0.9, "b": 0.1}, True), ({"a": "0.9", "b": 0.1}, 1)):
            with self.subTest(probabilities=probabilities), self.assertRaises(ValueError):
                fn._decision(SimpleNamespace(choice="a", probabilities=probabilities,
                                             confidence=confidence), options)
        answer = SimpleNamespace(choice="a", probabilities={"a": 0.9, "b": 0.1}, confidence=0.8)
        self.assertEqual(fn._decision(answer, options)["probability"], 0.9)


@unittest.skipIf(TypeSafeClient is None, "Install typesafe-sdk for offline SDK tests")
class JevTests(unittest.TestCase):
    def setUp(self):
        fn._reviews.clear()
        self.calls, self.failure, self.status = [], None, 200
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.enterContext(patch("typesafe_sdk.TypeSafeClient", side_effect=self.make_client))

    def make_client(self, **kwargs):
        return TypeSafeClient(**kwargs, compression=False, transport=httpx2.MockTransport(self.respond))

    def respond(self, request):
        payload = json.loads(request.content)
        self.calls.append(payload)
        if self.failure:
            raise self.failure
        answers = {}
        for name, question in payload["questions"].items():
            options = question["criteria"]
            choice = "schema_expansion" if name == "diagnosis" else next(iter(options))
            probabilities = {option: 0.1 / (len(options) - 1) for option in options}
            probabilities[choice] = 0.9
            answers[name] = {"type": "choice", "choice": choice, "confidence": 0.8,
                             "probabilities": probabilities}
        return httpx2.Response(self.status, json={"model": "jev-test", "answers": answers,
                                                  "usage": {"input_tokens": 123}})

    def check(self, contract, incoming, **kwargs):
        return fn.check_schema(contract, incoming, ai_review=True, api_key="offline-key", **kwargs)

    def test_ai_cannot_override_blocking_or_advisory_facts(self):
        for order in ({}, {"id": None}, {"id": "bad"}):
            result = self.check({"id": int}, [order])
            self.assertFalse(result["valid"])
            self.assertEqual(result["review"]["status"], "completed")
        result = self.check({"id": int}, [{"id": 1, "extra": "private"}], allow_extra=True)
        self.assertTrue(result["valid"])
        self.assertNotIn("private", json.dumps(self.calls))
        self.assertNotIn("coverage", result["review"])
        self.assertNotIn("renames", result["review"])

    def test_failed_reviews_preserve_facts_and_do_not_retry_or_cache(self):
        for failure, status in ((httpx2.ReadTimeout("offline"), 200), (None, 503)):
            self.failure, self.status = failure, status
            before = len(self.calls)
            result = self.check({"id": int}, [{"id": None}])
            self.assertFalse(result["valid"])
            self.assertEqual(result["review"]["status"], "failed")
            self.assertEqual(len(self.calls), before + 1)
        self.assertEqual(fn._reviews, {})

    def test_cache_reuses_only_the_review_and_expires(self):
        with patch.object(fn, "monotonic", return_value=0):
            first = self.check({"id": int}, [{"id": None}, {"id": 1}])
        first["review"]["diagnosis"]["category"] = "corrupted"
        with patch.object(fn, "monotonic", return_value=299):
            second = self.check({"id": int}, [{"id": 1}, {"id": None}])
        self.assertFalse(second["valid"])
        self.assertTrue(second["review"]["cached"])
        self.assertEqual(second["review"]["input_tokens"], 0)
        self.assertEqual(second["review"]["diagnosis"]["category"], "schema_expansion")
        self.assertEqual(second["changes"][0]["evidence"]["example_rows"]["null"], [1])
        with patch.object(fn, "monotonic", return_value=300):
            self.assertFalse(self.check({"id": int}, [{"id": None}, {"id": 1}])["review"]["cached"])
        self.assertEqual(len(self.calls), 2)

    def test_empty_api_key_cannot_reuse_environment_key_review(self):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "environment-key"}):
            fn.check_schema({"id": int}, {}, ai_review=True)
            result = fn.check_schema({"id": int}, {}, ai_review=True, api_key="")
        self.assertFalse(result["review"]["cached"])

    def test_limits_and_competing_rename_hypotheses_are_visible(self):
        result = self.check({f"missing_{i}": int for i in range(25)},
                            {f"added_{i}": int for i in range(40)})
        self.assertFalse(result["valid"])
        self.assertEqual(len(self.calls[0]["questions"]), 17)
        self.assertEqual(result["review"]["coverage"], {
            "fields": {"reviewed": 32, "total": 65},
            "rename_fields": {"reviewed": 16, "total": 25},
            "rename_options": {"reviewed": 32, "total": 40},
        })
        self.assertEqual(len(result["review"]["renames"][0]["competing_changes"]), 15)


if __name__ == "__main__":
    unittest.main()
