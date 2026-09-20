import unittest

from token_format import format_token_value, format_tokens, normalize_token_format


class TokenFormatTests(unittest.TestCase):
    def test_full_format_uses_complete_grouped_integer(self):
        self.assertEqual(format_token_value(31_399_745, 'full'), '31,399,745')
        self.assertEqual(format_token_value(186_031_972, 'full'), '186,031,972')

    def test_compact_k_format_has_consistent_precision(self):
        self.assertEqual(format_token_value(1_200, 'compact'), '1.20K')

    def test_compact_m_format_has_consistent_precision(self):
        self.assertEqual(format_token_value(31_399_745, 'compact'), '31.40M')
        self.assertEqual(format_token_value(186_031_972, 'compact'), '186.03M')

    def test_compact_b_format_has_consistent_precision(self):
        self.assertEqual(format_token_value(1_250_000_000, 'compact'), '1.25B')

    def test_compact_t_format_has_consistent_precision(self):
        self.assertEqual(format_token_value(1_200_000_000_000, 'compact'), '1.20T')

    def test_suffix_boundaries_are_deterministic(self):
        self.assertEqual(format_token_value(999, 'compact'), '999')
        self.assertEqual(format_token_value(1_000, 'compact'), '1.00K')
        self.assertEqual(format_token_value(999_999, 'compact'), '1.00M')
        self.assertEqual(format_token_value(1_000_000, 'compact'), '1.00M')
        self.assertEqual(format_token_value(999_999_999, 'compact'), '1.00B')
        self.assertEqual(format_token_value(999_999_999_999, 'compact'), '1.00T')

    def test_nullable_negative_and_unexpected_values_are_unavailable(self):
        for value in (None, -1, 1.5, True, '1200'):
            self.assertEqual(format_token_value(value, 'compact'), 'N/A')

    def test_tokens_unit_and_invalid_mode_fallback(self):
        self.assertEqual(format_tokens(1_200, 'compact'), '1.20K Tokens')
        self.assertEqual(normalize_token_format('future'), 'compact')
        self.assertEqual(format_token_value(1_200, 'future'), '1.20K')


if __name__ == '__main__':
    unittest.main()
