"""Fetch Coimbatore district news candidates. Free sources only; polite 1.5 s gaps. Used inside GitHub Actions."""
import re, time, html, json
import requests
UA = {"User-Agent": "Mozilla/5.0 (compatible; Coimbatore360-research/1.0)"}
DISTRICT = "tamil-nadu-district-news-coimbatore"      # Dinamalar's Coimbatore district page
LIST_URL = "https://www.dinamalar.com/news/" + DISTRICT


def _get(u):
    time.sleep(1.5)
    r = requests.get(u, headers=UA, timeout=40)
    r.raise_for_status()
    return r.text


def candidate_links(limit=15):
    h = _get(LIST_URL)
    links = []
    for m in re.finditer(r'href="(/news/[^"#?]+?/\d{6,})"', h):
        u = "https://www.dinamalar.com" + m.group(1)
        if u not in links:
            links.append(u)
    # 27 Oct: only the first 8 stories are <a href> links; the rest of the district list sits in the page data as
    # '/news/tamil-nadu-district-news-coimbatore/<id>/<slug>'
    for m in re.finditer(r'/news/(' + DISTRICT + r')/(?:(\d{6,})/([a-z0-9-]+)|([a-z0-9-]+)/(\d{6,}))', h):
        slug, nid = (m.group(3), m.group(2)) if m.group(2) else (m.group(4), m.group(5))
        u = f"https://www.dinamalar.com/news/{m.group(1)}/{slug}/{nid}"
        if u not in links:
            links.append(u)
    return links[:limit]


def article(url):
    """returns dict(title, published, text) parsed from the page"""
    h = _get(url)
    def g(pat):
        m = re.search(pat, h)
        return html.unescape(m.group(1)).strip() if m else ""
    title = g(r'"newstitle"\s*:\s*"([^"]+)"') or g(r"<title>([^<]+)</title>")
    pub = g(r'"publisheddate"\s*:\s*"([^"]+)"')
    # owner 31 Oct (Namakkal RN-241): the WHOLE article. Dinamalar keeps it in "newsdescription"; the old page-line reading kept only lines over
    # 60 letters, and Dinamalar breaks its text into short lines - 26-59% of many articles was lost (RN-241 lost the town, the date and the end)
    text = max((json_field(h, k) for k in ("newsdescription", "articleBody")), key=len)
    if len(text) < 200:
        text = max(text, article_paragraphs(h), key=len)
    if len(text) < 200:
        text = max(text, long_lines(h), key=len)
    return {"url": url, "title": title, "published": pub, "text": text.strip()}


def clean_body(s):
    """article HTML / text -> plain paragraphs. <br> and </p> start a new paragraph; the paper's own line breaks inside a paragraph are joined
    (Dinamalar: 'அரசு பஸ்சை\nசிறைபிடித்தனர்' is one sentence)"""
    s = re.sub(r"(?i)<\s*br\s*/?\s*>|<\s*/?\s*p(?:\s[^>]*)?>", "\n\n", html.unescape(s or "").replace("\r", ""))
    s = re.sub(r"<[^>]+>", " ", s).replace("\u00a0", " ")
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n[ \t]*\n", s)]
    return "\n".join(p for p in paras if p)


def json_field(h, key):
    """a text field of the page's own data ("newsdescription", "articleBody") as clean paragraphs, '' if missing"""
    for m in re.finditer(r'"%s"\s*:\s*"((?:[^"\\]|\\.){40,})"' % key, h):
        try:
            return clean_body(json.loads('"' + m.group(1) + '"'))
        except ValueError:
            continue
    return ""


BODY_TAG = re.compile(r'<(?:div|section)[^>]+(?:itemprop="articleBody"|class="[^"]*(?:article[-_ ]?(?:body|content|desc)|story[-_ ]?(?:body|content|details)|'
                      r'news[-_ ]?(?:body|content|detail)|entry-content|post-content|td-post-content)[^"]*")[^>]*>|<article[^>]*>', re.I)


# owner 31 Oct (Coimbatore RN-102, a Thanthi TV 'breaking' page with only a headline, a video and hashtags): the 'Also Read' /
# related-story cards (other stories' headlines) were taken as the article's text. Everything from that heading on is not the story.
RELATED = re.compile(r">\s*(?:Also Read|Related (?:News|Stories|Articles)|Read More|இதையும் படிக்க|இதையும் படியுங்கள்|"
                     r"தொடர்புடைய செய்திகள்|மேலும் படிக்க)\s*<")


def article_paragraphs(h):
    """every paragraph INSIDE the article body (short ones too) - never the page's side columns or other stories"""
    h2 = re.sub(r"<(style|script|noscript|svg|aside|figure|nav|footer)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    m = BODY_TAG.search(h2)
    if not m:
        return ""
    seg = RELATED.split(h2[m.start():m.start() + 80000], maxsplit=1)[0]
    paras = [clean_body(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", seg, re.S)]
    seen, out = set(), []
    for p in paras:
        if p and re.search(r"[\u0B80-\u0BFF]", p) and p not in seen:
            seen.add(p); out.append(p)
    return "\n".join(out)


def long_lines(h):
    """last resort for a page without article data or body: its long Tamil lines - never the related-story cards, headings or links"""
    h2 = re.sub(r"<(style|script|noscript|svg)[^>]*>.*?</\1>", " ", h, flags=re.S)
    h2 = RELATED.split(h2, maxsplit=1)[0]
    h2 = re.sub(r"<(h[1-6]|a|figcaption|time|button|nav|header|footer)\b[^>]*>.*?</\1>", " ", h2, flags=re.S | re.I)
    paras = [html.unescape(x).strip() for x in re.sub(r"<[^>]+>", "\n", h2).split("\n")]
    paras = [re.sub(r"\s+", " ", x) for x in paras if len(x) > 60 and re.search(r"[\u0B80-\u0BFF]", x) and "{" not in x and "css-" not in x]
    seen, out = set(), []
    for x in paras:
        if x not in seen:
            seen.add(x); out.append(x)
    return "\n".join(out)
