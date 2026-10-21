"""Source number matching must not change units when whitespace or token boundaries change."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location('takeover_evidence', ROOT/'employees/product-project/product-manager/evidence_decision.py')
e = importlib.util.module_from_spec(s); s.loader.exec_module(e)

class NumericBoundaries(unittest.TestCase):
    def test_percent_whitespace_preserves_percent_identity(self):
        for gap in [' ', '  ', '\u2009', '\u202f', '\t', '\n', '\u00a0']:
            with self.subTest(gap=repr(gap)):
                self.assertTrue(e._value_in_quote('7%', 'Rate: 7'+gap+'%.'))
                self.assertFalse(e._value_in_quote('7', 'Rate: 7'+gap+'%.'))

    def test_identifiers_units_signs_and_larger_values_are_not_plain_numbers(self):
        for quote in ['K18', 'metric18', '18kg', '-18', '+18', '118', '18,000', '18%extra']:
            with self.subTest(quote=quote):
                self.assertFalse(e._value_in_quote('18',quote))

    def test_sentence_punctuation_and_decimal_controls(self):
        self.assertTrue(e._value_in_quote('18','The count is 18.'))
        self.assertTrue(e._value_in_quote('18','The count is 18, according to the report.'))
        self.assertTrue(e._value_in_quote('18','The value is 18.0.'))
        self.assertTrue(e._value_in_quote('18000','The count is 18,000.'))
        self.assertFalse(e._value_in_quote('18','The value is 18.5.'))
