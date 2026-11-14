"""owner 14 Nov: only important comments are e-mailed (question, fake / doubt claim, complaint, viewer information, abuse)."""
import sys, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "poster"))
import comments      # noqa: E402


class CommentFilter(unittest.TestCase):
    def test_kinds(self):
        for k in ("question", "doubt_or_fake_claim", "complaint", "info_from_viewer", "spam_or_abuse"):
            self.assertIn(k, comments.CRITICAL)
        for k in ("praise", "other"):
            self.assertNotIn(k, comments.CRITICAL)

    def test_only_important_comments_sent(self):
        page = next(iter(comments.HANDLES))
        texts = {"1": "super news", "2": "🙏🙏", "3": "இது உண்மையா? எந்த பேப்பர்?", "4": "fake news"}
        kinds = {"super news": "praise", "இது உண்மையா? எந்த பேப்பர்?": "question", "fake news": "doubt_or_fake_claim"}
        sent = []

        def ig(m, path, tok, **kw):
            if path.endswith("/media"):
                return {"data": [{"id": "M", "caption": "c", "timestamp": comments.datetime.now(comments.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z"), "comments_count": 4}]}
            return {"data": [{"id": i, "text": t, "username": "u"} for i, t in texts.items()]}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(comments.post, "bridge_get", side_effect=lambda a, **k: {"token": "t", "ids": []}), \
                mock.patch.object(comments.post, "ig_account", return_value=("U", "u")), mock.patch.object(comments.post, "ig", side_effect=ig), \
                mock.patch.object(comments, "options_for", side_effect=lambda cap, t: (kinds[t], ["ok"])), \
                mock.patch.object(comments.post, "bridge_post", side_effect=lambda a, p: sent.append(p) or {"ok": True, "added": len(p["items"])}):
            if hasattr(comments, "IGNORED"):
                comments.IGNORED = Path(d) / "i.json"
            comments.run(page)
        self.assertEqual(sorted(x["comment_id"] for x in sent[0]["items"]), ["3", "4"])
