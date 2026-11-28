"""owner 28 Nov ("use this design for all the page"): design A + three improvements - the sample the owner saw and chose (sample A).
A layer laid OVER the finished reel page, like clock360 - the layout, colours, text, voice and timing of design A stay as they are:
 1. pictures: with 2+ pictures they take turns every second cut, about 4 s (was: each picture once, for a long stretch); the change is
    the page's own soft dissolve (the clock-hand line across the picture is no longer used - reel/clock360.py)
 2. BREAKING tag: only on serious news (a death, a murder, people badly hurt) - above the big headline while it shows, then small at
    the end of the place row
 3. place card: the district outline with the news town pinned and the town's name, for 3 s after the big headline
    (reel/assets/district_map.json; only a town the map knows; not on a page whose reel already opens with the map - "map_intro");
    it sits to the right of the news reader's round window when the reel has one (reel/reader360.py)

The same video goes to Instagram, Facebook and YouTube Shorts (owner 28 Nov): every addition sits where design A already keeps its own
parts - left of x 950 below the logo row and above y 1600, inside the middle the 4:5 feed keeps (y 285-1635). The tag and the card are
placed from the page's own parts when the reel is recorded (the headline, the place row, the fact cards, the captions), so a long
place name or a tall card never ends under them: what does not fit is left out.

add(page_html, spec) -> the page with the layer. It never fails the reel: anything unexpected returns the page unchanged.
REEL_LIVE360=0, or poster/config.json "reel_live": false, switches it off."""
import json
import os
import re
from html import escape as E
from pathlib import Path

HERE = Path(__file__).resolve().parent
TURN = 2            # the picture changes every TURN cuts
MAP_S = 3.0         # the place card stays this long
_TA = "஀-௿"
SERIOUS = re.compile(rf"உயிரிழ|உயிர்\s*இழ|பலியா|பலி(?![{_TA}])|இறந்த|இறப்பு|சடல|படுகாய|கொலை(?!\s*(?:மிரட்ட|முயற்சி|வெறி))")
NEEDS = ("const D=", "window.renderAt", 'id="pin"', 'id="hook"', 'id="mini"', 'id="cap"', "</style>", "</body>")

CSS = """
#lvbrk{position:absolute;z-index:31;background:#D32F2F;color:#fff;font:900 40px/1 'CT','NST';letter-spacing:3px;display:flex;align-items:center;
 gap:14px;padding:6px 24px 0;border-radius:12px;box-shadow:0 8px 22px rgba(0,0,0,.45);opacity:0;white-space:nowrap;box-sizing:border-box;height:66px}
#lvbrk.row{height:58px;font-size:34px}
#lvbrk i{width:18px;height:18px;border-radius:50%;background:#fff;margin-top:-6px}
#lvmap{position:absolute;left:48px;top:944px;height:212px;max-width:880px;z-index:23;background:rgba(8,12,28,.86);border-radius:24px;
 padding:12px 30px 12px 14px;box-shadow:0 14px 34px rgba(0,0,0,.5),0 0 0 3px #FFD233;display:flex;align-items:center;gap:20px;opacity:0;
 box-sizing:border-box;transform-origin:0 0}
#lvmap svg{position:static;width:186px;height:186px;flex:none;overflow:visible}
#lvmap path{fill:rgba(255,210,51,.22);stroke:#FFD233;stroke-width:2.5}
#lvmap .p{fill:#FF3B30;stroke:#fff;stroke-width:2.5} #lvmap .r{fill:none;stroke:#FF3B30;stroke-width:2.5}
#lvmap .t i{display:block;font:800 28px/1.2 'NST','CT';color:#FFD233;font-style:normal}
#lvmap .t b{display:block;font:900 52px/1.25 'NST','CT';color:#fff;white-space:nowrap}
#lvmap .t span{display:block;font:700 28px/1.3 'NST','CT';color:#D5DBEA;white-space:nowrap}
"""

JS = """
<script>
(function(){
const old=window.renderAt, X=__DATA__;
const cl=u=>Math.max(0,Math.min(1,u)), ez=u=>{u=cl(u);return 1-Math.pow(1-u,3)};
const $=id=>document.getElementById(id), box=e=>e.getBoundingClientRect();
let mapTop=null, mapS=1;
window.renderAt=function(t){
 old(t);
 try{
  const live=t<X.end, brk=$('lvbrk'), map=$('lvmap'), pin=$('pin'), hook=$('hook');
  if(brk){
   const p=box(pin);
   if(t<X.hook_end){      /* above the big headline (it moves in with it) */
    const h=box(hook), y=h.top-82;
    brk.className=''; brk.style.right='auto'; brk.style.left=h.left+'px'; brk.style.top=y+'px';
    brk.style.opacity=(y>=p.bottom+10)?(1-cl((t-(X.hook_end-0.25))/0.25)):0;
   }else{                  /* then small at the end of the place row - only when the place name leaves room */
    brk.className='row'; brk.style.left='auto'; brk.style.right='48px'; brk.style.top=(p.top+(p.height-brk.offsetHeight)/2)+'px';
    brk.style.opacity=(live&&p.right+24<=1080-48-brk.offsetWidth)?ez((t-X.hook_end)/0.3):0;
   }
   brk.querySelector('i').style.opacity=(Math.floor(t*2.5)%2)?1:0.3;
  }
  if(map){
   const a=X.map_a, b=X.map_b;
   if(t>=a&&t<b){
    if(mapTop===null){      /* once: under the lowest fact card, above the captions; a long town name is made smaller */
     let y=box($('mini')).bottom; document.querySelectorAll('.card').forEach(c=>{y=Math.max(y,box(c).bottom)});
     const rd=$('rdr'), L=rd?48+rd.offsetWidth+22:48, MW=950-L-(rd?0:42);      /* beside the news reader (reel/reader360.py) when the reel has one */
     map.style.left=L+'px'; map.style.maxWidth=(MW+20)+'px';
     const nm=map.querySelector('b'); let fs=52; while(map.scrollWidth>MW&&fs>26){fs-=2;nm.style.fontSize=fs+'px';}
     mapTop=y+24; mapS=Math.min(1,(box($('cap')).top-12-mapTop)/map.offsetHeight); if(mapS<0.8||map.scrollWidth>MW)mapS=0;
    }
    map.style.top=mapTop+'px';
    map.style.transform='translateX('+(-(1-ez((t-a)/0.3))*80)+'px) scale('+(mapS||1)+')';
    map.style.opacity=mapS?ez((t-a)/0.25)*cl((b-t)/0.25):0;
    const u=(((t-a)%0.9)+0.9)%0.9/0.9, r=map.querySelector('.r'); if(r){r.setAttribute('r',(7+22*u).toFixed(1)); r.style.opacity=(1-u).toFixed(2);}
   }else map.style.opacity=0;
  }
 }catch(e){}
};
})();
</script>"""


def say(*a):
    """one line in the job's log; a log problem never touches the reel"""
    try:
        print(*a, flush=True)
    except Exception:
        pass


def config():
    try:
        return json.loads((HERE.parent / "poster" / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def on(cfg=None):
    cfg = config() if cfg is None else cfg
    return os.environ.get("REEL_LIVE360", "1") not in ("0", "false", "no") and cfg.get("reel_live", True) is not False


def serious(spec):
    """a death, a murder or people badly hurt in the headline -> the BREAKING tag"""
    return bool(SERIOUS.search(" ".join([str(spec.get("mini") or "")] + [re.sub(r"<[^>]+>", "", str(x)) for x in (spec.get("hook") or [])])))


def district_map():
    try:
        m = json.loads((HERE / "assets" / "district_map.json").read_text(encoding="utf-8"))
        return m if m.get("path") and isinstance(m.get("towns"), dict) else None
    except Exception:
        return None


def town_of(location, m):
    """the town of the map this news is from, '' when the map has none. Another town wins over the district's own town
    ("<town>, <district town>" -> the town); a place that only ends with the district town ("<a village>, <district town>") gets no
    pin: the pin would sit on the district town, not on the village."""
    loc = str(location or "").strip()
    towns = m.get("towns") or {}
    centre = towns.get(m.get("district_ta"))
    found = sorted((t for t in towns if t in loc), key=len, reverse=True)
    other = next((t for t in found if towns[t] != centre), "")
    if other or not found:
        return other
    first = re.split(r"[,(/-]", loc)[0].strip()
    return found[0] if first.startswith(found[0]) else ""


def turn_pictures(D):
    """2+ different pictures take turns every TURN cuts while the news is told (the end card keeps the last one)"""
    n = int(D.get("n") or 1)
    if n < 2 or D.get("single") or D.get("cycle") or not D.get("shots"):
        return False
    for k, s in enumerate(D["shots"]):
        if s.get("a", 0) < D.get("end_t", 1e9):
            s["img"] = (k // TURN) % n
    return True


def page_data(page_html):
    """(D, start, end) of the page's own data object"""
    i = page_html.index("{", page_html.index("const D="))
    D, n = json.JSONDecoder().raw_decode(page_html[i:])
    return D, i, i + n


def add(page_html, spec):
    """the finished reel page + the three improvements; the page unchanged when switched off or the page is not design A's"""
    try:
        cfg = config()
        if not on(cfg) or 'id="lvbrk"' in page_html or 'id="lvmap"' in page_html or 'id="fxloop"' in page_html:
            return page_html
        if any(x not in page_html for x in NEEDS) or page_html.count("</style>") != 1 or page_html.count("</body>") != 1:
            return page_html
        D, a, b = page_data(page_html)
        if not isinstance(D, dict) or "hook_end" not in D or "end_t" not in D:
            return page_html
        out = page_html
        turns = turn_pictures(D)
        if turns:
            out = out[:a] + json.dumps(D, ensure_ascii=False).replace("</", "<\\/") + out[b:]
        extra = ""
        if serious(spec):
            extra += '<div id="lvbrk"><i></i>BREAKING</div>'
        hook_end, end_t = float(D["hook_end"]), float(D["end_t"])
        map_a = round(hook_end + 0.3, 2)
        map_b = round(min(map_a + MAP_S, end_t - 0.3, (float(D["sum_a"]) - 0.15) if D.get("rows") and D.get("sum_a") else 1e9), 2)
        m = None if cfg.get("map_intro") else district_map()
        town = town_of(spec.get("location"), m) if m else ""
        if town and map_b - map_a >= 1.6:
            tx, ty = m["towns"][town]
            extra += (f'<div id="lvmap"><svg viewBox="0 0 260 260"><path d="{E(m["path"])}"/><circle class="r" cx="{tx}" cy="{ty}" r="10"/>'
                      f'<circle class="p" cx="{tx}" cy="{ty}" r="7"/></svg><div class="t"><i>இடம்</i><b>{E(town)}</b>'
                      f'<span>{E(str(m.get("district_ta") or ""))} மாவட்டம்</span></div></div>')
        say(f"reel additions: pictures take turns: {'yes' if turns else 'no (one picture)'}; BREAKING tag: {'yes' if 'lvbrk' in extra else 'no'}; "
              f"place card: {town if 'lvmap' in extra else 'no'}")      # in the job's log: what this reel got
        if not extra:
            return out
        data = {"end": end_t, "hook_end": hook_end, "map_a": map_a, "map_b": map_b}
        return out.replace("</style>", CSS + "</style>", 1).replace("</body>", extra + JS.replace("__DATA__", json.dumps(data)) + "</body>", 1)
    except Exception as e:
        say("reel additions not made:", str(e)[:150])
        return page_html
