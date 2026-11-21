"""owner 21 Nov: (1) Instagram-safe limits - 'too many posts made' / 'too many requests' pause the page instead of a try every run, and
the story catch-up tries a post at most twice (Trichy 20-21 Nov: 400+ story tries, then Instagram refused every new post);
(2) "do not use Cloudinary" - reels and stories go to Instagram (Instagram API with Facebook login) and Facebook as FILES once the
page's Facebook token can do it; until then, or if a file is refused, the Cloudinary link as before (a post is never lost or doubled);
(3) the YouTube details e-mail and the clean-up are started by the watchdog when GitHub skips them; the e-mail gives Instagram's link."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import facebook      # noqa: E402
import igdirect      # noqa: E402
import localmedia    # noqa: E402
import post          # noqa: E402
import watchdog as W      # noqa: E402
import youtube       # noqa: E402

CREATE = ("Instagram 1/media: {'message': 'User is performing too many actions', 'type': 'OAuthException', 'is_transient': False, 'code': 9, "
          "'error_subcode': 2207069, 'error_user_title': 'Media Creation Limit Exceeded'}")
APP = ("Instagram 1/media_publish: {'message': 'Application request limit reached', 'type': 'OAuthException', 'is_transient': False, "
       "'code': 4, 'fbtrace_id': 'x'}")
BLOCK = "Instagram 1/media_publish: {'message': 'Fatal', 'code': -1, 'error_subcode': 2207051, 'error_user_msg': 'action is blocked'}"
QUOTA = "Instagram 1/media_publish: {'code': 9, 'error_subcode': 2207042, 'message': 'maximum number of posts allowed to be published'}"
FATAL = "Instagram 1/media_publish: {'message': 'Fatal', 'type': 'OAuthException', 'code': -1, 'error_subcode': 2207001}"
LINK = "https://res.cloudinary.com/x/video/upload/v1/page360/r.mp4"


def hours_left(page):
    d = json.loads(post.ig_pause_file(page).read_text(encoding="utf-8"))
    return (datetime.fromisoformat(d["until"]) - datetime.now(timezone.utc)).total_seconds() / 3600, d


class Tmp(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self._p = [mock.patch.object(post, "CACHE", self.d), mock.patch.object(igdirect, "CACHE", self.d),
                   mock.patch.dict(post.LIMIT, {}, clear=True), mock.patch.object(post, "quiet_now", return_value="")]
        for x in self._p:
            x.start()
        igdirect._MEM.clear()
        localmedia._LOCAL.clear()
        localmedia._HOSTED.clear()

    def tearDown(self):
        for x in self._p:
            x.stop()


class Limits(Tmp):
    def test_which_limit(self):
        self.assertEqual([post.ig_limit_kind(e) for e in (CREATE, APP, BLOCK, QUOTA, FATAL, "Instagram container 1 ERROR")],
                         ["create", "rate", "block", "quota", "", ""])

    def test_too_many_posts_made_pauses_the_page_6_hours(self):
        with mock.patch.object(post, "PAGE", "x"):
            self.assertTrue(post.is_limit_error(CREATE))      # waits - never marked failed
        h, d = hours_left("x")
        self.assertAlmostEqual(h, 6, delta=0.1)
        self.assertEqual(d["kind"], "create")
        self.assertIn("paused until", post.ig_paused("x"))
        self.assertTrue(post.limit_reached("x"))

    def test_too_many_requests_pauses_an_hour_and_a_longer_pause_stays(self):
        post.ig_pause("x", APP, "rate")
        self.assertAlmostEqual(hours_left("x")[0], 1, delta=0.05)
        post.ig_pause("x", CREATE, "create")
        post.ig_pause("x", APP, "rate")      # shorter: the 6-hour pause is not shortened
        self.assertEqual(hours_left("x")[1]["kind"], "create")

    def test_the_daily_quota_waits_without_a_pause(self):
        with mock.patch.object(post, "PAGE", "x"):
            self.assertTrue(post.is_limit_error(QUOTA))
        self.assertFalse(post.ig_pause_file("x").exists())

    def test_a_limit_is_tried_once_not_in_other_ways(self):
        calls = []

        def ig(method, path, token, **kw):
            calls.append(kw)
            raise RuntimeError(CREATE)
        with mock.patch.object(post, "ig", side_effect=ig), mock.patch.object(post, "LOC_ID", "123"), \
                mock.patch.object(post, "collab_user", return_value="other"):
            with self.assertRaises(post.IgLimit):
                post.create_with_collab("U", "T", {"media_type": "REELS"}, True)
        self.assertEqual(len(calls), 1)      # not again without the collaborator / the location

    def test_a_reel_with_a_cover_is_not_tried_again_on_a_limit(self):
        made = []

        def ig(method, path, token, **kw):
            made.append(path)
            raise RuntimeError(CREATE)
        with mock.patch.object(post, "ig", side_effect=ig), mock.patch.object(post, "ig_account", return_value=("U", "u")), \
                mock.patch.object(post, "LOC_ID", ""):
            with self.assertRaises(Exception):
                post.publish_reel("T", LINK, "cap", False, "https://res.cloudinary.com/x/c.jpg")
        self.assertEqual(len(made), 1)

    def test_first_comment_is_not_tried_again_on_a_limit(self):
        n = []

        def ig(method, path, token, **kw):
            n.append(1)
            raise RuntimeError(APP)
        row = {"story_id": "RN-1", "source": "https://www.dinamalar.com/news/1", "headline_ta": "செய்தி", "category": "civic"}
        with mock.patch.object(post, "ig", side_effect=ig), mock.patch.object(post.time, "sleep"), mock.patch.object(post, "PAGE", "x"), \
                mock.patch.dict(post.CONFIG, {"first_comment": True}):
            post.first_comment("T", "M", "RN-1", row)
        self.assertEqual(len(n), 1)
        self.assertIn("paused until", post.ig_paused("x"))


class StoryCatchUp(Tmp):
    def run_catchup(self, publish_error, runs):
        now = datetime.now(timezone.utc)
        when = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+0000")
        feed = [{"id": "1", "media_type": "VIDEO", "media_url": "https://cdn/v1.mp4", "timestamp": when, "owner": {"id": "U"}, "caption": "x"}]
        made = []

        def ig(method, path, token, **kw):
            if path == "me":
                return {"id": "U", "user_id": "UU"}
            if path.endswith("content_publishing_limit"):
                return {"data": [{"quota_usage": 5, "config": {"quota_total": 50}}]}
            if path.endswith("/media") and method == "GET":
                return {"data": feed}
            if path.endswith("/stories"):
                return {"data": []}
            if path.endswith("/media") and method == "POST":
                made.append(kw)
                return {"id": "c"}
            if path.endswith("media_publish"):
                raise RuntimeError(publish_error)
            return {}
        with mock.patch.object(post, "DRY", False), mock.patch.object(post, "LABEL", {"x": "X"}), \
                mock.patch.object(post, "SHARED", self.d / "shared.json"), \
                mock.patch.dict(post.CONFIG, {"stories_urgent_only": False, "story_catchup_tries": 2, "post_stories": True}), \
                mock.patch.object(post, "bridge_get", return_value={"token": "t"}), mock.patch.object(post, "ig_account", return_value=("U", "u")), \
                mock.patch.object(post, "ig", side_effect=ig), mock.patch.object(post, "wait_ready"), \
                mock.patch.object(post, "upload", side_effect=lambda p, k: "https://cloud/" + Path(p).name), \
                mock.patch.object(post.requests, "get", return_value=mock.Mock(content=b"x", raise_for_status=lambda: None)):
            for _ in range(runs):
                post.story_catchup()
        return made

    def test_a_failing_story_is_tried_twice_then_given_up(self):
        self.assertEqual(len(self.run_catchup(FATAL, runs=6)), 2)
        shared = json.loads((self.d / "shared.json").read_text(encoding="utf-8"))
        self.assertIn("failed", shared["1"])

    def test_a_limit_stops_the_catch_up_and_pauses_the_page(self):
        self.assertEqual(len(self.run_catchup(APP, runs=4)), 1)      # one try, then the page waits an hour
        self.assertIn("paused until", post.ig_paused("x"))


class Files(Tmp):
    """the page has its Facebook token (instagram_basic + instagram_content_publish) and its Facebook page is linked to its Instagram"""

    def setUp(self):
        super().setUp()
        self.f = self.d / "r.mp4"
        self.f.write_bytes(b"0" * 1000)
        self.linked = "U"
        self.env = mock.patch.dict(os.environ, {"FB_PAGE_ID_X": "PG", "FB_TOKEN_X": "FBT", "DIRECT_UPLOAD": "auto"})
        self.env.start()
        self.calls, self.fb = [], []
        self.refuse = None

        def fbcall(method, path, token, **kw):
            self.fb.append((method, path))
            return {"instagram_business_account": {"id": self.linked}}

        def ig(method, path, token, **kw):
            self.calls.append((post.ig_url(path), method, path, dict(kw), token))
            if path.endswith("/media") and method == "POST":
                if self.refuse and token == "FBT":
                    raise RuntimeError(self.refuse)
                return {"id": "C1"}
            if path.endswith("/media_publish"):
                return {"id": "M1"}
            if path == "M1":
                return {"permalink": "https://instagram.com/reel/x"}
            return {}
        self.ps = [mock.patch.object(facebook, "_call", side_effect=fbcall), mock.patch.object(post, "ig", side_effect=ig),
                   mock.patch.object(post, "ig_account", return_value=("U", "u")), mock.patch.object(post, "wait_ready"),
                   mock.patch.object(post, "PAGE", "x"), mock.patch.object(post, "LOC_ID", "")]
        for x in self.ps:
            x.start()

    def tearDown(self):
        for x in self.ps:
            x.stop()
        self.env.stop()
        super().tearDown()

    def made(self):
        return [c for c in self.calls if c[2].endswith("/media") and c[1] == "POST"]

    def published(self):
        return [c for c in self.calls if c[2].endswith("/media_publish")]

    def test_the_reel_goes_to_instagram_as_a_file(self):
        ref = localmedia.ref(self.f)
        with mock.patch.object(localmedia, "send") as send, mock.patch.object(post, "upload") as up:
            mid, link, _, _ = post.publish_reel("T", ref, "cap", False, "")
        up.assert_not_called()      # nothing to Cloudinary
        self.assertEqual((mid, link), ("M1", "https://instagram.com/reel/x"))
        (url, _, _, prm, tok), = self.made()
        self.assertTrue(url.startswith("https://graph.facebook.com/"))      # the Instagram API with Facebook login
        self.assertEqual((prm.get("upload_type"), prm.get("thumb_offset"), tok), ("resumable", "900", "FBT"))
        self.assertNotIn("video_url", prm)
        self.assertIn("rupload.facebook.com/ig-api-upload/", send.call_args.args[0])
        self.assertEqual(len(self.published()), 1)
        self.assertTrue(post.ig_url("me").startswith(post.IG_HOST))      # every other call: the Instagram login as before

    def test_no_facebook_token_means_the_link_as_before(self):
        with mock.patch.dict(os.environ, {"FB_TOKEN_X": ""}):
            self.assertIsNone(igdirect.ready("x", "U"))
            localmedia.remember(LINK, str(self.f))
            post.publish_reel("T", LINK, "cap", False)
        (url, _, _, prm, tok), = self.made()
        self.assertEqual((prm.get("video_url"), tok), (LINK, "T"))
        self.assertTrue(url.startswith(post.IG_HOST))

    def test_linked_to_another_instagram_account_means_the_link(self):
        self.linked = "OTHER"
        self.assertIsNone(igdirect.ready("x", "U"))

    def test_a_refused_file_goes_by_the_link_once(self):
        ref = localmedia.ref(self.f)
        with mock.patch.object(localmedia, "send", side_effect=RuntimeError("upload refused (HTTP 400): bad")), \
                mock.patch.object(post, "upload", return_value=LINK) as up:
            post.publish_reel("T", ref, "cap", False, "")
        up.assert_called_once()      # Cloudinary only as the last resort
        self.assertEqual([m[3].get("video_url") for m in self.made()], [None, LINK])
        self.assertEqual(len(self.published()), 1)

    def test_no_permission_switches_the_page_to_the_link_for_6_hours(self):
        self.refuse = "Instagram 1/media: {'message': '(#10) Application does not have permission for this action', 'code': 10}"
        ref = localmedia.ref(self.f)
        with mock.patch.object(localmedia, "send"), mock.patch.object(post, "upload", return_value=LINK):
            post.publish_reel("T", ref, "cap", False, "")
        self.assertEqual(len(self.published()), 1)
        igdirect._MEM.clear()
        self.assertIsNone(igdirect.ready("x", "U"))      # saved: no new try every run
        self.assertFalse(igdirect.cached_ok("x"))

    def test_a_published_reel_is_never_posted_again(self):
        orig = post.ig.side_effect

        def ig(method, path, token, **kw):
            if path == "M1":
                raise RuntimeError("permalink not ready")
            return orig(method, path, token, **kw)
        post.ig.side_effect = ig
        with mock.patch.object(localmedia, "send"):
            mid, link, _, _ = post.publish_reel("T", localmedia.ref(self.f), "cap", False, "")
        self.assertEqual((mid, link), ("M1", ""))
        self.assertEqual((len(self.made()), len(self.published())), (1, 1))

    def test_the_story_goes_as_a_file(self):
        with mock.patch.object(localmedia, "send") as send, mock.patch.object(post, "_story_room", return_value=True), \
                mock.patch.dict(post.CONFIG, {"post_stories": True, "stories_urgent_only": False}):
            self.assertEqual(post.publish_story("T", localmedia.ref(self.f), "video"), "M1")
        (url, _, _, prm, _), = self.made()
        self.assertEqual((prm.get("media_type"), prm.get("upload_type")), ("STORIES", "resumable"))
        send.assert_called_once()

    def test_the_check_is_kept_6_hours_and_a_new_token_is_checked_at_once(self):
        self.assertTrue(igdirect.ready("x", "U"))
        igdirect._MEM.clear()
        self.assertTrue(igdirect.ready("x", "U"))
        self.assertEqual(len(self.fb), 1)      # one call, then the saved check
        self.assertTrue(igdirect.cached_ok("x"))
        with mock.patch.dict(os.environ, {"FB_TOKEN_X": "NEW"}):
            igdirect.ready("x", "U")
        self.assertEqual(len(self.fb), 2)

    def test_facebook_gets_the_file(self):
        ref = localmedia.ref(self.f)
        with mock.patch.object(localmedia, "send") as send, mock.patch.object(facebook.requests, "post") as rp:
            facebook._hosted_upload("PT", "V1", ref)
        send.assert_called_once()
        rp.assert_not_called()

    def test_facebook_falls_back_to_a_link(self):
        ref = localmedia.ref(self.f)
        with mock.patch.object(localmedia, "send", side_effect=RuntimeError("no")), mock.patch.object(post, "upload", return_value=LINK), \
                mock.patch.object(facebook.requests, "post", return_value=mock.Mock(status_code=200, json=lambda: {"success": True})) as rp:
            facebook._hosted_upload("PT", "V1", ref)
        self.assertEqual(rp.call_args.kwargs["headers"]["file_url"], LINK)

    def test_facebook_does_not_retry_a_file_that_is_gone(self):
        st = self.d / "fb"
        st.mkdir()
        rec = {"status": "failed", "tries": 1, "media": ["file:///tmp/gone.mp4"], "caption": "c", "page": "x", "story": "RN-1", "kind": "reel",
               "first_try": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        (st / "x-RN-1-reel.json").write_text(json.dumps(rec), encoding="utf-8")
        with mock.patch.object(facebook, "STATE", st), mock.patch.object(facebook, "_attempt") as att, \
                mock.patch.object(facebook, "paused", return_value=""):
            facebook.retry_failed()
        att.assert_not_called()
        self.assertEqual(json.loads((st / "x-RN-1-reel.json").read_text(encoding="utf-8"))["status"], "skipped")

    def test_switched_off(self):
        with mock.patch.dict(os.environ, {"DIRECT_UPLOAD": "0"}):
            self.assertIsNone(igdirect.ready("x", "U"))
            self.assertIsNone(localmedia.get(LINK))

    def test_the_sheet_never_gets_a_local_name(self):
        ref = localmedia.ref(self.f)
        self.assertEqual(localmedia.shown(ref), "")
        self.assertEqual(localmedia.shown(LINK), LINK)


class Workflow(unittest.TestCase):
    def test_files_switched_on_and_pauses_kept(self):
        wf = (ROOT / ".github" / "workflows" / "post.yml").read_text(encoding="utf-8")
        self.assertIn('DIRECT_UPLOAD: "auto"', wf)
        self.assertIn("poster/prebuilt/_ig_paused_*.json", wf)


class SkippedEmails(unittest.TestCase):
    def at(self, h, m):
        return datetime(2026, 11, 21, h, m, tzinfo=W.IST)

    def test_the_youtube_details_email_is_started_when_github_skipped_it(self):
        old = [("completed", self.at(21, 6) - timedelta(days=1))]
        self.assertEqual(W.yt_due(self.at(12, 20), old), "")      # not 25 minutes late yet
        self.assertEqual(W.yt_due(self.at(12, 40), old), "am")
        self.assertEqual(W.yt_due(self.at(12, 40), [("completed", self.at(12, 6))]), "")      # it ran
        self.assertEqual(W.yt_due(self.at(15, 10), old), "")      # too late for the midday one
        self.assertEqual(W.yt_due(self.at(21, 40), [("completed", self.at(12, 40))]), "pm")
        self.assertEqual(W.yt_due(self.at(21, 40), [("queued", self.at(21, 39))]), "")
        self.assertIn("youtube.yml am", W.decide(self.at(12, 40), True, True, [], [], "", None, True, yt_runs=old))

    def test_the_cleanup_is_started_when_github_skipped_it(self):
        now = self.at(14, 0)
        self.assertTrue(W.clean_due(now, [("completed", now - timedelta(hours=7))]))
        self.assertFalse(W.clean_due(now, [("completed", now - timedelta(hours=5))]))
        self.assertFalse(W.clean_due(now, None))
        self.assertIn("cloudclean.yml", W.decide(now, True, True, [], [], "", None, True, clean_runs=[("completed", now - timedelta(hours=8))]))

    def test_a_paused_page_gets_no_gold_or_rasipalan_restart(self):
        at = self.at(9, 50)
        self.assertEqual(W.decide(at, None, False, [], [], "", None, None), ["goldrate.yml"])
        self.assertEqual(W.decide(at, None, False, [], [], "", None, None, paused=True), [])

    def test_gold_and_rasipalan_skip_a_paused_page(self):
        sys.path.insert(0, str(ROOT / "goldrate"))
        import gold_daily
        tmp = Path(tempfile.mkdtemp())
        (tmp / "poster" / "prebuilt").mkdir(parents=True)
        f = tmp / "poster" / "prebuilt" / "_ig_paused_x.json"
        f.write_text(json.dumps({"until": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}), encoding="utf-8")
        with mock.patch.object(gold_daily, "ROOT", tmp):
            self.assertTrue(gold_daily.ig_paused_page("x"))
            self.assertFalse(gold_daily.ig_paused_page("y"))
        src = (ROOT / "rasipalan" / "rasi_daily.py").read_text(encoding="utf-8")
        self.assertIn("if not DRY and ig_paused_page(PAGE):", src)

    def test_the_email_gives_instagrams_own_link(self):
        self.assertEqual(youtube.download_link(post, "any caption"), "")


if __name__ == "__main__":
    unittest.main()
