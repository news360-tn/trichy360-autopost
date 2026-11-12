"""owner 31 Oct: the reel uses the news's own source photo (relevant only, enhanced when small); otherwise the AI pictures as before."""
import datetime, io, os, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_free"))
import realphoto as R  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

TODAY = datetime.date(2026, 10, 31)


def photo(w, h, seed=1):
    """a busy, sharp test picture (lines and blocks, like a real photo has edges)"""
    im = Image.new("RGB", (w, h), (90, 110, 130))
    d = ImageDraw.Draw(im)
    for i in range(0, w, 17):
        d.line((i, 0, (i * seed) % w, h), fill=((i * 7) % 255, (i * 3) % 255, 200), width=3)
    for j in range(0, h, 23):
        d.rectangle((j % w, j, j % w + 40, j + 12), fill=(250, 240, 20))
    return im


class FilePhotosAreNeverUsed(unittest.TestCase):
    def test_dinamani_representative_photo(self):      # RN-93: an August 'jail' picture labelled பிரதிப் படம்
        page = ('<meta property="og:image" content="https://media.dinamani.com/dinamani/2026-08-23/3h2kmgnz/jail-lockup.jpg">'
                '<img src="https://media.dinamani.com/dinamani/2026-08-23/3h2kmgnz/jail-lockup.jpg?w=800" alt="jail">'
                '<p><span>சிறை</span> - பிரதிப் படம்</p>')
        (u, cap, main), = R.candidates(page, "https://www.dinamani.com/x")
        self.assertTrue(main)
        self.assertTrue(R.is_file_photo(u, cap, TODAY))

    def test_old_upload_date_in_the_link(self):
        self.assertTrue(R.is_file_photo("https://media.dinamani.com/dinamani/2026-07-30/8w64vg5t/application.jpg", "", TODAY))
        self.assertFalse(R.is_file_photo("https://cf-images.assettype.com/thanthitv/2026-10-31/d3b1vro1/maxresdefault.jpg", "", TODAY))
        self.assertFalse(R.is_file_photo("https://images.dinamalar.com/data/large_2025/Tamil_News_lrg_436205120261029051347.jpg", "",
                                         datetime.date(2026, 10, 30)))


class OnlyArticlePictures(unittest.TestCase):
    def test_logos_icons_avatars_are_skipped(self):
        page = ('<img src="https://images.dinamalar.com/icons/cinema-blue.svg"><img src="/static/images/google_news.png">'
                '<img src="https://img-cdn.publive.online/fit-in/100x0/media/member_avatars/2026/02/06/a.jpeg">'
                '<img src="https://stat.dinamalar.com/new/2025/images/dinamalar-pavala-vizha-logo-day.png" width="235" height="60">'
                '<img src="https://img-cdn.publive.online/fit-in/1280x960/filters:format(webp)/indian-express-tamil/media/media_files/2026/10/31/p.jpg">')
        got = [u for u, _, _ in R.candidates(page, "https://tamil.indianexpress.com/a")]
        self.assertEqual(1, len(got))
        self.assertIn("media_files/2026/10/31/p.jpg", got[0])

    def test_one_picture_in_many_sizes_counts_once(self):
        page = ('<meta property="og:image" content="https://cf-images.assettype.com/t/2026-10-31/x/max.jpg?w=1200">'
                '<img src="https://cf-images.assettype.com/t/2026-10-31/x/max.jpg?w=640">')
        self.assertEqual(1, len(R.candidates(page, "https://www.thanthitv.com/a")))

    def test_credit_names_the_paper(self):
        self.assertEqual("Dinamalar", R.credit_of("https://www.dinamalar.com/news/x"))
        self.assertEqual("Thanthi TV", R.credit_of("https://www.thanthitv.com/news/x"))
        self.assertEqual("The New Indian Express", R.credit_of("https://www.newindianexpress.com/cities/x"))


class PresentablePicture(unittest.TestCase):
    def test_outlet_text_panel_is_cut_away(self):      # a Thanthi TV thumbnail: the photo is the left part, the right is red text
        im = photo(1200, 675)
        self.assertEqual((462, 337), R.cut(im, [0, 330, 470, 675]).size)
        self.assertEqual(im.size, R.cut(im, [0, 0, 100, 100]).size)      # a tiny box is not trusted

    def test_small_photo_is_enlarged_to_reel_width(self):
        e = R.enhance(photo(470, 340))
        self.assertEqual(R.W, e.width)

    def test_nine_by_sixteen_with_credit(self):
        for w, h in ((1280, 720), (680, 710), (600, 1100)):
            self.assertEqual((R.W, R.H), R.compose(R.enhance(photo(w, h)), "Dinamalar").size)
        self.assertEqual((R.W, R.H), R.compose(R.enhance(photo(1280, 720)), "X", zoom=1.35).size)

    def test_blurred_picture_scores_low(self):
        from PIL import ImageFilter
        sharp = R.sharpness(R.enhance(photo(900, 600)))
        soft = R.sharpness(R.enhance(photo(900, 600).filter(ImageFilter.GaussianBlur(6))))
        self.assertGreater(sharp, soft)


class NeverBreaksTheStory(unittest.TestCase):
    def setUp(self):
        self.key = os.environ.pop("GEMINI_API_KEY", None)
        self.dl = R.download

    def tearDown(self):
        R.download = self.dl
        if self.key:
            os.environ["GEMINI_API_KEY"] = self.key

    def test_page_that_cannot_be_opened_gives_ai_pictures(self):
        def boom(u):
            raise RuntimeError("403")
        self.assertEqual(([], ""), R.for_story("https://www.dinamalar.com/x", "h", fetch=boom, log=lambda *a: None))

    def test_no_picture_on_the_page(self):
        self.assertEqual(([], ""), R.for_story("https://www.dinamalar.com/x", "h", page="<p>text only</p>", log=lambda *a: None))

    def test_main_picture_without_vision_check(self):      # no Gemini key: only the page's own main (og) picture, never a file photo
        R.download = lambda u, timeout=30: photo(1200, 800)
        page = '<meta property="og:image" content="https://images.dinamalar.com/data/large_2025/Tamil_News_lrg_4363970.jpg">'
        pics, credit = R.for_story("https://www.dinamalar.com/news/x/1", "h", n=2, page=page, published=TODAY, log=lambda *a: None)
        self.assertEqual(2, len(pics))
        self.assertEqual("Dinamalar", credit)
        self.assertEqual((R.W, R.H), Image.open(io.BytesIO(pics[0])).size)

    def test_without_check_an_inline_picture_is_not_trusted(self):
        R.download = lambda u, timeout=30: photo(1200, 800)
        page = '<img src="https://images.dinamalar.com/data/large_2025/other_story.jpg">'
        self.assertEqual(([], ""), R.for_story("https://www.dinamalar.com/news/x/1", "h", page=page, published=TODAY, log=lambda *a: None))

    def test_too_small_photo_is_not_used(self):
        R.download = lambda u, timeout=30: photo(300, 210)
        page = '<meta property="og:image" content="https://www.dinakaran.com/a/b.jpg">'
        self.assertEqual(([], ""), R.for_story("https://www.dinakaran.com/x", "h", page=page, published=TODAY, log=lambda *a: None))

    def test_switch_off(self):
        os.environ["REAL_PHOTOS"] = "0"
        try:
            self.assertEqual(([], ""), R.for_story("https://www.dinamalar.com/x", "h", page="<img src='a.jpg'>", log=lambda *a: None))
        finally:
            os.environ.pop("REAL_PHOTOS")


class WiredInBothSteps(unittest.TestCase):
    def test_writer_and_posting_job_try_the_real_photo_first(self):
        c = (ROOT / "research_free" / "collect.py").read_text(encoding="utf-8")
        p = (ROOT / "poster" / "post.py").read_text(encoding="utf-8")
        self.assertLess(c.index("realphoto.for_story"), c.index("reused = reuse_images(st, len(prompts))"))
        self.assertLess(p.index("realphoto.for_story"), p.index("cand = imagegen.generate("))


if __name__ == "__main__":
    unittest.main()


class WatermarksRemovedNoCredit(unittest.TestCase):
    """owner 31 Oct 18:15: a watermark / channel logo on the source photo is removed; 18:16: no source credit on the picture"""

    def test_logo_at_the_edge_is_cut_away(self):      # Thanthi TV logo, bottom-left of its thumbnail photo
        ph = photo(462, 337)
        c = R.remove_marks(ph, [[10, 588, 92, 665]], (4, 334))
        self.assertIsNotNone(c)
        self.assertEqual(337, c.height)
        self.assertLess(c.width, 462)

    def test_mark_inside_is_painted_over_or_the_photo_is_dropped(self):
        ph = photo(800, 600)
        c = R.remove_marks(ph, [[380, 280, 440, 310]])
        try:
            import cv2  # noqa: F401
            self.assertEqual(ph.size, c.size)
        except ImportError:
            self.assertIsNone(c)      # without OpenCV a photo with a mark inside is not used (AI pictures instead)

    def test_too_much_marked_is_not_used(self):
        self.assertIsNone(R.remove_marks(photo(800, 600), [[100, 100, 700, 300]]))

    def test_marks_outside_the_kept_part_are_ignored(self):
        ph = photo(462, 337)
        self.assertEqual(ph.size, R.remove_marks(ph, [[700, 50, 900, 200]], (4, 334)).size)

    def test_no_credit_written_on_the_picture(self):
        e = R.enhance(photo(1280, 720))
        self.assertEqual(R.compose(e, "Dinamalar").tobytes(), R.compose(e, "").tobytes())


class VisionQuotaIsSpared(unittest.TestCase):
    """owner 31 Oct: Gemini 429 'too many requests' - the photo check stops at once (the free quota is the writer's) and rests 30 min"""

    def test_one_429_stops_everything(self):
        calls = []

        class Resp:
            def raise_for_status(self):
                raise RuntimeError("429 Client Error: Too Many Requests")

        old_post, old_dl = R.requests.post, R.download
        R.requests.post = lambda *a, **k: calls.append(1) or Resp()
        R.download = lambda u, timeout=30: photo(1200, 800)
        os.environ["GEMINI_API_KEY"] = "test"
        R.VISION_DOWN[0] = 0.0
        try:
            page = "".join(f'<img src="https://images.dinamalar.com/data/large_2025/p{i}.jpg">' for i in range(5))
            self.assertEqual(([], ""), R.for_story("https://www.dinamalar.com/x", "h", page=page, published=TODAY, log=lambda *a: None))
            self.assertEqual(1, len(calls))
            self.assertTrue(R.vision_resting())
        finally:
            R.requests.post, R.download = old_post, old_dl
            os.environ.pop("GEMINI_API_KEY", None)
            R.VISION_DOWN[0] = 0.0
