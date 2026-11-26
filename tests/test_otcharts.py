import unittest

from backend.main import OTC_SYMBOLS, OTC_TIMEFRAMES, map_otcharts_candles


class OTChartsCandleTests(unittest.TestCase):
    def test_maps_unix_seconds_to_chart_shape_and_sorts(self):
        payload = {
            "candles": [
                {"open": 1.2, "high": 1.3, "low": 1.1, "close": 1.25, "time": 1788103320},
                {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.2, "time": 1788103260},
            ]
        }
        self.assertEqual(
            map_otcharts_candles(payload),
            [
                {"datetime": "2026-08-30T15:21:00Z", "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.2},
                {"datetime": "2026-08-30T15:22:00Z", "open": 1.2, "high": 1.3, "low": 1.1, "close": 1.25},
            ],
        )

    def test_accepts_millisecond_timestamps(self):
        row = {"open": 1, "high": 2, "low": 0.5, "close": 1.5, "time": 1788103260000}
        self.assertEqual(map_otcharts_candles({"candles": [row]})[0]["datetime"], "2026-08-30T15:21:00Z")

    def test_skips_malformed_rows(self):
        self.assertEqual(map_otcharts_candles({"candles": [{"open": "bad"}]}), [])

    def test_rejects_invalid_payload(self):
        with self.assertRaises(ValueError):
            map_otcharts_candles({"values": []})

    def test_otc_scope_is_limited_to_confirmed_values(self):
        self.assertEqual(OTC_SYMBOLS, {"EURUSD_otc"})
        self.assertEqual(OTC_TIMEFRAMES, {60})


if __name__ == "__main__":
    unittest.main()
