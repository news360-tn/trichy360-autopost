"""owner 14 Nov: daily gold & silver rate post - real data only (2 pages must agree), compared with yesterday"""
import sys, unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "goldrate"))
import gold_sources as S      # noqa: E402
import gold_daily as G      # noqa: E402

GR = ("Gold Price on 14 November 2026 - Goodreturns Today's gold price in Chennai stands at ₹13,900 per gram for 24 karat gold "
      "(99.9% purity), ₹12,745 per gram for 22 karat gold (91.6% purity)")


class Parse(unittest.TestCase):
    def test_goodreturns_and_groww(self):
        self.assertEqual(S.parse_gold(GR), (12745, 13900))
        self.assertEqual(S.parse_gold(GR.replace("₹13,900", "₹13,900.00").replace("₹12,745", "₹12,745.00")), (12745, 13900))

    def test_bankbazaar(self):
        self.assertEqual(S.parse_gold("09 Nov 2026 UPDATED DAILY Gold Rate, Chennai ₹ 13,255/ 1 gram (22K) ₹ 95")[0], 13255)

    def test_silver(self):
        self.assertEqual(S.parse_silver("Today's silver price in Chennai stands at ₹195 per gram and ₹1,95,000 per kg"), 195)

    def test_only_todays_page_counts(self):
        self.assertTrue(S.has_today(GR, date(2026, 11, 14)))
        self.assertFalse(S.has_today(GR, date(2026, 11, 15)))

    def test_24k_read_from_wrong_place_is_dropped(self):
        self.assertEqual(S.parse_gold(GR.replace("₹13,900", "₹19,900"))[1], None)

    def test_two_pages_must_agree(self):
        self.assertEqual(S.agree([12745, 12745, 12800]), (12745, 2))
        self.assertEqual(S.agree([12745, 12800])[0], None)


class Compare(unittest.TestCase):
    def test_yesterday_and_week(self):
        hist = [{"date": "2026-11-07", "g22": 13160}, {"date": "2026-11-13", "g22": 12695, "g24": 13849}]
        r = G.rates_for_slides(hist, date(2026, 11, 14), {"g22": 12745, "g24": 13900, "sources": []}, None)
        self.assertEqual((r["g22_prev"], r["g24_prev"], r["vs"]), (12695, 13849, "நேற்றைய விலையைவிட"))
        self.assertEqual(len(r["week22"]), 7)
        self.assertEqual(r["week22"][0], ("8 நவ", 13160))      # a day with no rate keeps the day before's rate
        self.assertNotIn("silver", r)      # silver not confirmed -> gold slide only

    def test_older_last_day_is_not_called_yesterday(self):
        r = G.rates_for_slides([{"date": "2026-11-11", "g22": 13015, "g24": 14200}], date(2026, 11, 14),
                               {"g22": 12745, "g24": 13900, "sources": []}, None)
        self.assertEqual(r["vs"], "முந்தைய விலையைவிட")

    def test_caption(self):
        r = G.rates_for_slides([{"date": "2026-11-13", "g22": 12695, "g24": 13849, "silver": 195}], date(2026, 11, 14),
                               {"g22": 12745, "g24": 13900, "sources": []}, {"silver": 195, "sources": []})
        cap = G.caption(dict(G.PAGES["namakkal"]), date(2026, 11, 14), r)
        self.assertIn("இன்றைய தங்கம், வெள்ளி விலை | 14 நவம்பர் 2026", cap)
        self.assertIn("₹50 உயர்வு", cap)
        self.assertIn("மாற்றமில்லை", cap)


if __name__ == "__main__":
    unittest.main()
