import copy
import ast
import os
import ssl
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from SchemaDiagnoser import fn
from use_example.adapt import adapt_order

with patch.dict(os.environ, {"API_KEY": "offline-key"}):
    from use_example import validate


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.review = {
            "status": "completed", "cached": False,
            "diagnosis": {"category": "schema_expansion", "probability": 0.95,
                          "check": "Review producer additions."},
        }
        self.ai = self.enterContext(patch.object(fn, "_review", return_value=self.review))
        self.smtp = self.enterContext(patch.object(validate.smtplib, "SMTP"))
        self.enterContext(patch.object(validate, "SMTP_PORT", 1025))
        self.enterContext(patch.object(validate, "SMTP_PASSWORD", None))
        self.logger = self.enterContext(patch.object(validate, "logger"))
        self.send = self.smtp.return_value.__enter__.return_value.send_message

    def test_clean_order_needs_no_review_or_email(self):
        order = {"id": 1}
        result = validate.validate_order(order, {"id": int})
        self.assertEqual(adapt_order(order, result), order)
        self.ai.assert_not_called()
        self.smtp.assert_not_called()

    def test_invalid_orders_return_reports_without_raising_or_repairing(self):
        for order in ({}, {"Id": 1}, {"id": None}, {"id": True}, {"id": "1"}, {"id": 1.0}):
            with self.subTest(order=order):
                self.assertFalse(validate.validate_order(order, {"id": int})["valid"])
        self.assertEqual(self.send.call_count, 6)
        result = validate.validate_order({"id": 1, "extra": None}, {"id": int})
        self.assertTrue(result["valid"])
        self.assertEqual(self.send.call_count, 7)

    def test_consumer_continues_after_rejected_order_and_only_adapts_accepted_orders(self):
        source = Path("use_example/main.py").read_text()
        loop = next(node for node in ast.parse(source).body if isinstance(node, ast.For))
        with patch("use_example.adapt.adapt_order", wraps=adapt_order) as adapt:
            namespace = {
                "consumer": [SimpleNamespace(value={"id": "bad"}), SimpleNamespace(value={"id": 2})],
                "contract": {"schema": {"id": int}}, "validate_order": validate.validate_order,
                "adapt_order": adapt,
            }
            exec(compile(ast.Module(body=[loop], type_ignores=[]), "main.py", "exec"), namespace)
            adapt.assert_called_once()
            self.assertEqual(namespace["data"], {"id": 2})

    def test_declared_nulls_and_alternate_types_pass_without_alerts(self):
        for value in (None, 1, 1.5):
            order = {"id": value}
            report = validate.validate_order(order, {"id": int | float | None})
            self.assertTrue(report["valid"])
            self.assertEqual(adapt_order(order, report), order)
        self.ai.assert_not_called()
        self.smtp.assert_not_called()

    def test_expansion_is_projected_without_upstream_revalidation_or_mutation(self):
        order = {"id": 1, "note": "private"}
        with patch.object(validate, "check_schema", wraps=fn.check_schema) as check:
            result = validate.validate_order(order, {"id": int})
            before = copy.deepcopy(result)
            with patch.object(fn, "check_schema", side_effect=AssertionError("Duplicate validation")):
                self.assertEqual(adapt_order(order, result), {"id": 1})
            check.assert_called_once()
        self.assertEqual(result, before)
        self.assertEqual(order, {"id": 1, "note": "private"})
        message = self.send.call_args.args[0]
        self.assertEqual(message["To"], validate.RECEIVER_EMAIL)
        self.assertEqual(message["From"], validate.SENDER_EMAIL)
        self.assertIn("note: added", message.get_content())
        self.assertIn("Review producer additions.", message.get_content())
        self.assertNotIn("private", message.get_content())

    def test_alias_cleanup_handles_all_supported_contract_forms(self):
        self.review["diagnosis"]["category"] = "naming_change"
        forms = [{"customer_id": int}, [("customer_id", int)],
                 {"schema": {"customer_id": int}}, {"contract": {"customer_id": int}},
                 {"columns": ["customer_id"], "types": [int]}]
        for contract in forms:
            order = {"customer_id": 1, "customerId": 1}
            result = validate.validate_order(order, contract)
            self.assertEqual(adapt_order(order, result), {"customer_id": 1})

    def test_mixed_changes_remove_only_unambiguous_identical_scalar_aliases(self):
        self.review["diagnosis"]["category"] = "mixed_changes"
        for extra, should_remove in ((1, True), (2, False), (True, False), ("1", False), (None, False)):
            order = {"customer_id": 1, "customerId": extra, "unrelated": "keep"}
            result = validate.validate_order(order, {"customer_id": int})
            adapted = adapt_order(order, result)
            self.assertEqual(adapted["customer_id"], 1)
            self.assertEqual(adapted["unrelated"], "keep")
            self.assertEqual("customerId" not in adapted, should_remove)
        order = {"customer_id": 1, "customerid": 1, "CustomerID": 1}
        result = validate.validate_order(order, {"customer_id": int, "customerid": int})
        self.assertEqual(adapt_order(order, result), order)
        order = {"payload": {"v": 1}, "Payload": {"v": True}}
        result = validate.validate_order(order, {"payload": dict})
        self.assertEqual(adapt_order(order, result), order)
        order = {"id": None, "ID": None}
        result = validate.validate_order(order, {"id": int | None})
        self.assertEqual(adapt_order(order, result), {"id": None})

    def test_uncertain_partial_and_failed_reviews_leave_accepted_orders_unchanged(self):
        order = {"id": 1, "extra": "keep"}
        for review in (
            {"status": "failed", "diagnosis": None, "error": "Offline"},
            {**self.review, "coverage": {"fields": {"reviewed": 1, "total": 2}}},
            {**self.review, "diagnosis": {**self.review["diagnosis"], "probability": 0.5}},
            {**self.review, "diagnosis": {**self.review["diagnosis"], "category": "semantic_change"}},
        ):
            self.ai.return_value = review
            result = validate.validate_order(order, {"id": int})
            self.assertTrue(result["valid"])
            self.assertEqual(adapt_order(order, result), order)
        self.assertEqual(self.send.call_count, 4)

    def test_mail_failure_does_not_reject_acceptable_orders(self):
        self.smtp.side_effect = OSError("Mock relay unavailable")
        result = validate.validate_order({"id": 1, "extra": 1}, {"id": int})
        self.assertTrue(result["valid"])
        self.logger.exception.assert_called_once()

    def test_implicit_tls_verifies_certificates_and_authenticates_before_sending(self):
        with patch.object(validate, "SMTP_PORT", 465), \
                patch.object(validate, "SMTP_PASSWORD", "offline-password"), \
                patch.object(validate.smtplib, "SMTP_SSL") as secure:
            self.assertTrue(validate.send_email("Advisory", "New field"))
            self.assertEqual(secure.call_args.kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
            smtp = secure.return_value.__enter__.return_value
            smtp.login.assert_called_once_with(validate.SENDER_EMAIL, "offline-password")
            self.assertEqual([call[0] for call in smtp.method_calls], ["login", "send_message"])
        self.smtp.assert_not_called()

    def test_password_authentication_uses_starttls_on_other_ports(self):
        with patch.object(validate, "SMTP_PORT", 587), \
                patch.object(validate, "SMTP_PASSWORD", "offline-password"):
            self.assertTrue(validate.send_email("Advisory", "New field"))
        smtp = self.smtp.return_value.__enter__.return_value
        self.assertEqual([call[0] for call in smtp.method_calls], ["starttls", "login", "send_message"])
        self.assertEqual(smtp.starttls.call_args.kwargs["context"].verify_mode, ssl.CERT_REQUIRED)

    def test_rejected_order_logs_rename_hypotheses_without_automatically_applying_them(self):
        self.review["renames"] = [{"category": "possible_rename", "change_indices": [1, 0],
                                   "probability": 0.95, "competing_changes": [2]}]
        report = validate.validate_order({"Id": 1}, {"id": int})
        self.assertFalse(report["valid"])
        self.assertRegex(self.send.call_args.args[0].get_content(), "Id -> id.*competing matches")


if __name__ == "__main__":
    unittest.main()
