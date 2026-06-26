import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.sales_log_parser import parse_sales_log


ROOT = Path(__file__).resolve().parents[1]


class SalesLogSchemaTests(unittest.TestCase):
    def test_schema_loads_and_parser_emits_honda_draft(self):
        schema = json.loads((ROOT / "schemas" / "sales_log.schema.json").read_text(encoding="utf-8"))
        record = parse_sales_log("Example sales activity", "example-user", now=datetime(2026, 1, 2, tzinfo=timezone.utc))
        self.assertTrue(set(schema["required"]).issubset(record))
        self.assertEqual(record["status"], "draft")
        self.assertFalse(record["llm_used"])
        self.assertIsNone(record["llm_tokens_estimate"])

    def test_obvious_fields_are_extracted_without_llm(self):
        text = "Spoke to 3 people about a CR-V, one test drive, showed numbers, follow-up tomorrow."
        record = parse_sales_log(text, "example-user")
        parsed = record["parsed"]
        self.assertEqual(record["raw_text"], text)
        self.assertEqual(record["source"], "telegram_dm")
        self.assertEqual(parsed["vehicle_interest"], "CR-V")
        self.assertEqual(parsed["people_spoken_to"], 3)
        self.assertTrue(parsed["test_drive"])
        self.assertTrue(parsed["worksheet_or_offer_presented"])
        self.assertRegex(parsed["followup_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertFalse(record["llm_used"])
        self.assertIsNone(record["llm_tokens_estimate"])

    def test_honda_specific_parsed_fields_exist(self):
        schema = json.loads((ROOT / "schemas" / "sales_log.schema.json").read_text(encoding="utf-8"))
        parsed = schema["properties"]["parsed"]
        expected = {
            "customer_type", "customer_name_or_ref", "vehicle_interest", "lead_source",
            "interaction_type", "appointment_count", "walk_in_count", "people_spoken_to",
            "test_drive", "worksheet_or_offer_presented", "asked_for_business", "outcome",
            "next_step", "followup_date", "notes",
        }
        self.assertEqual(set(parsed["properties"]), expected)

    def test_empty_log_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_sales_log("  ", "example-user")


if __name__ == "__main__":
    unittest.main()
