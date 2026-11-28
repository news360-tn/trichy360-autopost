"""owner 28 Nov ("this round shape news reader apply the all the pages"): the NEWS360-TN news reader in a round window on every news
reel. A layer laid OVER the finished reel page, like clock360 and live360 - design A itself stays as it is.

The owner's own picture of the reader comes as 9 drawings (reel/assets/reader/r0.jpg - r8.jpg: mouth closed, a little open, open,
wide open, eyes shut; only the face differs - the owner asked for the second, moving hand to be taken out). For every moment of the
reel the drawing is chosen from the reel's own voice track, so the reader's mouth moves exactly while the news is read: closed in
every pause, open on every spoken syllable (owner: "news reading time correctly that mouth action").

Where: left edge (x 48), under the fact cards and above the captions - inside the area that is free on Instagram, Facebook and
YouTube Shorts and inside the 4:5 feed. While the big headline or the full-details card is on screen the window moves under it; when
the captions come close it gets smaller, and with no room left it is not shown. The place card of live360 moves to its right.

add(page_html, spec, work) -> the page with the reader. It never fails the reel: anything unexpected (no voice file, a drawing
missing, another design) returns the page unchanged. REEL_READER=0, or poster/config.json "reel_reader": false, switches it off;
"reel_reader_serious": false leaves the (smiling) reader out of news about a death."""
import json
import os
import sys
import wave
from array import array
from pathlib import Path

import live360

HERE = Path(__file__).resolve().parent
DIR = HERE / "assets" / "reader"
FPS = 30
SIZE = 250          # the round window, px
MOUTH = {0: [0], 1: [1, 5, 7], 2: [4, 6], 3: [2, 3]}      # mouth closed / a little open / open / wide open -> the drawings that show it
BLINK = 8           # eyes shut, mouth closed
QUIET = 0.14        # below this the voice is silent: mouth closed
NEEDS = ("const D=", "window.renderAt", 'id="hook"', 'id="mini"', 'id="cap"', "</style>", "</body>")

CSS = """
#rdr{position:absolute;left:48px;top:950px;width:%dpx;height:%dpx;border-radius:50%%;overflow:hidden;z-index:26;transform-origin:0 0;opacity:0;
 background:#0B1020;box-shadow:0 12px 30px rgba(0,0,0,.6)}
#rdr img{position:absolute;left:0;top:0;width:100%%;height:100%%;visibility:hidden}
""" % (SIZE, SIZE)

JS = """
<script>
(function(){
const old=window.renderAt, X=__DATA__;
const cl=u=>Math.max(0,Math.min(1,u));
const $=id=>document.getElementById(id), box=e=>e.getBoundingClientRect();
const R=$('rdr'), IM=[...R.querySelectorAll('img')], CAP=$('cap');
const bottomOf=el=>(el&&+getComputedStyle(el).opacity>0.3)?box(el).bottom:0;
let base=null, ay=null, as=1, lt=-1;
window.renderAt=function(t){
 old(t);
 try{
  if(base===null){      /* once: under the lowest fact card */
   let y=box($('mini')).bottom; document.querySelectorAll('.card').forEach(c=>{y=Math.max(y,box(c).bottom)});
   base=y+24; R.style.top=base+'px';
  }
  const k=X.pose[Math.min(X.pose.length-1,Math.max(0,Math.round(t*X.fps)))]||0;
  IM.forEach((im,i)=>{im.style.visibility=(i===k)?'visible':'hidden'});
  /* under the big headline / the full-details card, above the captions (never lower than y 1600); smaller when they come close */
  let top=Math.max(base,Math.max(bottomOf($('hook')),bottomOf($('sum')))+16), capTop=1600;
  CAP.querySelectorAll('[id^=g]').forEach(g=>{if(+g.style.opacity>0.05)capTop=Math.min(capTop,box(g).top)});
  let s=cl((capTop-14-top)/X.size); if(s<0.6)s=0;
  if(ay===null||t<lt||t-lt>0.2){ay=top;as=s}else{ay+=(top-ay)*0.3;as+=(s-as)*0.35}
  lt=t;
  R.style.transform='translateY('+(ay-base)+'px) scale('+as+')';
  R.style.opacity=(t<X.end&&as>0.3)?1:0;
 }catch(e){}
};
})();
</script>"""


def on(cfg=None):
    cfg = live360.config() if cfg is None else cfg
    return os.environ.get("REEL_READER", "1") not in ("0", "false", "no") and cfg.get("reel_reader", True) is not False


def drawings():
    """the 9 drawings, or [] when one is missing"""
    fs = [DIR / f"r{i}.jpg" for i in range(9)]
    return fs if all(f.is_file() and f.stat().st_size > 1000 for f in fs) else []


def loudness(wav_path, total):
    """how loud the voice is in every video frame, 0-1 (1 = about the loudest it gets)"""
    with wave.open(str(wav_path), "rb") as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        if sw != 2:
            raise ValueError("voice file is not 16-bit")
        a = array("h")
        a.frombytes(w.readframes(n))
    if sys.byteorder == "big":
        a.byteswap()
    if ch > 1:
        a = a[::ch]
    hop = max(1, sr // FPS)
    rms = [(sum(x * x for x in a[i:i + hop]) / hop) ** 0.5 / 32768 for i in range(0, len(a) - hop + 1, hop)]
    heard = sorted(r for r in rms if r > 0.005)
    top = heard[min(len(heard) - 1, int(len(heard) * 0.95))] if heard else 1.0
    env = [round(min(1.0, r / top) ** 0.7, 3) for r in rms]
    return env + [0.0] * max(0, int(float(total) * FPS) + 2 - len(env))


def poses(env, hold=2):
    """the drawing for every video frame, from the voice itself: closed in every pause, opening on each syllable (a loud moment)
    and closing a little in the dip between two syllables. One mouth shape is kept for `hold` frames (1/15 s) so it does not
    flicker; the eyes shut for a moment about every 3 s while the mouth is closed."""
    blocks = [max(env[b:b + hold]) for b in range(0, len(env), hold)]
    voiced = sorted(e for e in blocks if e >= QUIET) or [1.0]
    q1, q2 = voiced[int(len(voiced) * 0.35)], voiced[int(len(voiced) * 0.75)]
    out, since_blink = [], 0
    for n, e in enumerate(blocks):
        level = 0 if e < QUIET else 1 if e < q1 else 2 if e < q2 else 3
        prev, nxt = blocks[n - 1] if n else e, blocks[n + 1] if n + 1 < len(blocks) else e
        if level >= 2 and e < 0.85 * (prev + nxt) / 2:      # a dip between two syllables: the mouth closes a little
            level -= 1
        opts = MOUTH[level]
        f = opts[n % len(opts)]
        since_blink += 1
        if level == 0 and since_blink >= 42:
            f, since_blink = BLINK, 0
        out += [f] * hold
    return out[:len(env)]


def add(page_html, spec, work):
    """the finished reel page + the news reader; the page unchanged when switched off or anything is missing"""
    try:
        cfg = live360.config()
        if not on(cfg) or 'id="rdr"' in page_html:
            return page_html
        if 'id="fxloop"' in page_html or any(x not in page_html for x in NEEDS) or page_html.count("</style>") != 1 or page_html.count("</body>") != 1:
            live360.say("news reader not added: the page is not the usual design")
            return page_html
        if cfg.get("reel_reader_serious", True) is False and live360.serious(spec or {}):
            live360.say("news reader left out: news about a death (reel_reader_serious is off)")
            return page_html
        frames, voice = drawings(), Path(work) / "voice.wav"
        if not frames or not voice.is_file():
            live360.say("news reader not added:", "a drawing is missing in reel/assets/reader" if not frames else "no voice file " + voice.name)
            return page_html
        D = live360.page_data(page_html)[0]
        pose = poses(loudness(voice, D["total"]))
        if not any(f not in (0, BLINK) for f in pose):
            live360.say("news reader not added: no voice heard in the voice file")
            return page_html      # no voice heard: no silent reader
        live360.say(f"news reader added: the mouth moves for {sum(f not in (0, BLINK) for f in pose) / FPS:.1f} s of the reel's {len(pose) / FPS:.1f} s")      # in the job's log: proof it was drawn
        data = {"end": float(D["end_t"]), "size": SIZE, "fps": FPS, "pose": pose}
        imgs = "".join(f'<img src="{f.as_uri()}">' for f in frames)
        return page_html.replace("</style>", CSS + "</style>", 1).replace(
            "</body>", f'<div id="rdr">{imgs}</div>' + JS.replace("__DATA__", json.dumps(data)) + "</body>", 1)
    except Exception as e:
        live360.say("news reader not added:", str(e)[:150])
        return page_html
