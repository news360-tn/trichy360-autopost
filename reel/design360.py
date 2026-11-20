"""owner 20 Nov: the news reel design from the design team's handoff (Coimbatore 360 reel template v1), in Tamil, on every page.
A fixed layout on the 1080x1920 canvas - only the text changes; the voice, the timing and the length are exactly as before:
  yellow bar + page name 35px + tagline (x72/104 y280) · page logo 80px (x928 y280) · yellow location badge (x72 y383) ·
  headline 2 lines 70px (x72 y493) · the photo, full screen, no panel · yellow band x72 y1180 792x104: the key fact of the sentence
  being spoken · 2 supporting lines 32px (x72 y1312): the words being spoken · rule y1420 · "Source: paper" and the date with
  icons (y1442) · dark fade from y1463.
Owner decisions 20 Nov: Tamil; the yellow band and the supporting lines follow the voice (instead of the big captions); no fact cards,
summary or end card; no ad bar until a real sponsor exists; no image-disclosure label; the 360 clock branding is laid over it
(clock360.add); footer "[newspaper] Source: <paper>  [calendar] <date>"; text never overlaps or is cut (fitAll measures every text:
the headline steps down from 70px only when it does not fit 2 lines, the band text from 38px, the supporting lines are cut by
measurement into 2-line pieces). poster/config.json "reel_look": "handoff" (or REEL_LOOK=handoff) switches it on; "classic" (the default) is the earlier look.
  page(spec, shots, sents, caps, end_t, total, page, outro) -> html with window.renderAt(t), window.fitAll(), window.DUR"""
import html as _h
import json
import os
from pathlib import Path

E = _h.escape
HERE = Path(__file__).resolve().parent

CSS = """
:root{--y:#FFD114;--w:#FFFFFF;--k:#000000;--d:#090E14;--m:#A8BACC;--rule:#384754}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1920px;overflow:hidden;background:#090E14}
body{font-family:'NST',sans-serif;color:#fff;position:relative;letter-spacing:normal}
.pic{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover;opacity:0;will-change:transform,opacity}
#fade{position:absolute;left:0;top:1463px;width:1080px;height:457px;opacity:.94;z-index:5;
 background:linear-gradient(180deg,rgba(9,14,20,.10) 0%,rgba(9,14,20,1) 53.0337%,rgba(9,14,20,1) 100%)}
#acc{position:absolute;left:72px;top:283.5px;width:8px;height:76px;background:var(--y);z-index:20}
#pub{position:absolute;left:104px;top:280px;width:648px;font:700 35px/42px 'NST';color:var(--w);white-space:nowrap;z-index:20;text-shadow:0 2px 10px rgba(0,0,0,.45)}
#desc{position:absolute;left:104px;top:340px;width:648px;font:500 19px/23px 'NST';color:var(--k);white-space:nowrap;z-index:20}
#plogo{position:absolute;left:928px;top:280px;width:80px;height:80px;border-radius:50%;background:var(--d);border:2px solid var(--m);overflow:hidden;z-index:20}
#plogo img{width:100%;height:100%;object-fit:cover;display:block}
#loc{position:absolute;left:72px;top:383px;min-height:50px;padding:10px 20px;background:var(--y);border-radius:8px;z-index:20;
 font:700 25px/30px 'NST';color:var(--d);max-width:792px}
#hl{position:absolute;left:72px;top:493px;width:792px;font-weight:700;font-size:70px;line-height:1.2;color:var(--w);z-index:20;text-shadow:0 3px 18px rgba(0,0,0,.45)}
#band{position:absolute;left:72px;top:1180px;width:792px;height:104px;background:var(--y);z-index:20;display:flex;align-items:center;padding:0 24px;overflow:hidden}
#band span{display:block;width:744px;font-weight:700;font-size:38px;line-height:1.2;color:var(--d)}
#sup{position:absolute;left:72px;top:1312px;width:792px;font:500 32px/43.2px 'NST';color:var(--w);z-index:20}
#rule{position:absolute;left:72px;top:1420px;width:792px;height:2px;background:var(--rule);z-index:20}
#foot{position:absolute;left:72px;top:1442px;width:792px;font:500 22px/26px 'NST';color:var(--m);white-space:nowrap;z-index:20;display:flex;gap:34px}
#foot .fi{display:flex;align-items:center;gap:10px}
#foot .ic{width:1em;height:1em;flex:none;color:var(--y);fill:var(--y)}
#meas{position:absolute;left:-5000px;top:0;width:792px;font:500 32px/43.2px 'NST';visibility:hidden}
"""

JS = """
const cl=x=>Math.max(0,Math.min(1,x)), ease=x=>1-Math.pow(1-x,3);
function at(list,t){let k=-1;list.forEach((x,i)=>{if(t>=x.a)k=i});return k}
D.sup=[]; D.bandFs=[];
window.fitAll=function(){
 try{
  // headline: 2 lines at 70px; only if it does not fit, 64 / 58 / 52 px (never cut, never over the photo area)
  const hl=document.getElementById('hl'); for(const fs of [70,64,58,52]){hl.style.fontSize=fs+'px'; if(hl.offsetHeight<=fs*1.2*2+2) break;}
  // location badge and footer: one line, a little smaller when long
  const loc=document.getElementById('loc'); if(loc) for(const fs of [25,23,21,19]){loc.style.fontSize=fs+'px'; if(loc.scrollWidth<=792&&loc.offsetHeight<=52) break;}
  const ft=document.getElementById('foot'); for(const fs of [22,20,18]){ft.style.fontSize=fs+'px'; if(ft.scrollWidth<=792) break;}
  // the yellow band: one line at 38px; a long fact 34 / 30 px, at 30px it may take 2 lines inside the band (never cut)
  const bt=document.getElementById('bt'); bt.style.whiteSpace='nowrap';
  D.bandFs=D.band.map(b=>{bt.textContent=b; for(const fs of [38,34,30]){bt.style.fontSize=fs+'px'; if(bt.scrollWidth<=744) return [fs,0];} return [30,1];});
  bt.textContent=''; bt.dataset.i='';
  // the supporting lines: the spoken words, cut by measurement into pieces of at most 2 lines
  const m=document.getElementById('meas'), lim=43.2*2+2;
  D.words.forEach((ws,si)=>{let cur=[];
    ws.forEach(w=>{const nx=cur.concat([w]); m.textContent=nx.map(x=>x[0]).join(' ');
      if(cur.length&&m.offsetHeight>lim){D.sup.push({a:cur[0][1],t:cur.map(x=>x[0]).join(' ')}); cur=[w];} else cur=nx;});
    if(cur.length) D.sup.push({a:cur[0][1],t:cur.map(x=>x[0]).join(' ')});});
  if(!D.sup.length) D.sup.push({a:0,t:''});
 }catch(e){}
};
window.renderAt=function(t){
 try{
  if(!D.sup.length) fitAll();
  // the picture: full screen, a slow push-in, a soft cross-fade when it changes
  let ai=D.shots.length-1; D.shots.forEach((s,i)=>{if(t>=s.a&&t<s.b)ai=i});
  for(let i=0;i<D.n;i++){const e=document.getElementById('p'+i);if(e){e.style.opacity=0;e.style.zIndex=0}}
  const a=D.shots[ai], pv=ai>0?D.shots[ai-1]:null, k=t-a.a, tr=(pv&&pv.img!==a.img&&k<0.5)?ease(k/0.5):1;
  const el=document.getElementById('p'+a.img);
  if(el){el.style.opacity=tr; el.style.zIndex=2; el.style.transform='scale('+(1+0.06*cl((t-a.a)/Math.max(1,(a.b-a.a))))+')';}
  if(pv&&tr<1){const pe=document.getElementById('p'+pv.img);if(pe){pe.style.opacity=1;pe.style.zIndex=1}}
  // the yellow band: the key fact of the sentence being spoken
  const si=Math.max(0,at(D.sents,t)), bi=Math.min(si,D.band.length-1), bt=document.getElementById('bt');
  if(bi>=0&&bt.dataset.i!==String(bi)){const f=D.bandFs[bi]||[38,0]; bt.textContent=D.band[bi]; bt.style.fontSize=f[0]+'px';
    bt.style.whiteSpace=f[1]?'normal':'nowrap'; bt.dataset.i=bi;}
  if(bi>=0){const same=bi>0&&D.band[bi]===D.band[bi-1]; bt.style.opacity=(same||t<0.3)?1:ease(cl((t-D.sents[bi].a)/0.25));}
  // the supporting lines: the words being spoken
  const ci=Math.max(0,at(D.sup,t)), sp=document.getElementById('sup');
  if(sp.dataset.i!==String(ci)){sp.textContent=D.sup[ci].t; sp.dataset.i=ci;}
  sp.style.opacity=t<0.3?1:ease(cl((t-D.sup[ci].a+0.12)/0.18));
 }catch(e){}
};
window.DUR=D.total;
"""


def on():
    """the handoff look is on only when REEL_LOOK / poster/config.json "reel_look" says "handoff" (owner 20 Nov: "classic" is the default;
    never the "reel_design" key - that one picks reel4.py for the posting job and must stay "v4")"""
    v = os.environ.get("REEL_LOOK", "")
    if not v:
        try:
            v = json.loads((HERE.parent / "poster" / "config.json").read_text(encoding="utf-8")).get("reel_look", "")
        except Exception:
            v = ""
    return str(v or "classic").lower() == "handoff"


def screen(t):
    """the spoken form of the page name back to the screen form"""
    return str(t or "").replace("த்ரீ சிக்ஸ்டி", "360").replace("திரீ சிக்ஸ்டி", "360")


def bands(spec, sents):
    """the yellow band for each sentence: its key fact; a sentence without one keeps the last fact (the first: the hook's 2nd line)"""
    hook = spec.get("hook") or []
    last = str(hook[1]).strip() if len(hook) > 1 else ""
    out = []
    for s in sents:
        f = s.get("band") or s.get("fact") or ""
        f = f.strip() if isinstance(f, str) else ""
        last = f or last
        out.append(last)
    if not any(out):      # no fact at all: the headline's own words are the band
        out = [str(hook[0] if hook else spec.get("mini") or "")] * len(sents)
    first = next((x for x in out if x), "")
    return [x or first for x in out]      # a sentence before the first fact shows the first fact


def words(caps, sents, outro=None):
    """the spoken words (screen form) of each sentence with their start times; the closing line as the last group"""
    ws = [(str(w[0]), float(w[1])) for g in caps for w in g["words"]]
    out = [[w for w in ws if s["a"] - 0.05 <= w[1] < s["b"] + 0.05] for s in sents]
    if outro and outro.get("text"):
        out.append([(screen(outro["text"]), float(outro["a"]))])
    return out


def footer(spec, icons):
    parts = []
    if spec.get("source"):
        parts.append(f'<span class="fi">{icons.get("newspaper", "")}Source: {E(str(spec["source"]))}</span>')
    if spec.get("date"):
        parts.append(f'<span class="fi">{icons.get("calendar", "")}{E(str(spec["date"]))}</span>')
    return "".join(parts)


def page(spec, shots, sents, caps, end_t, total, pg, outro=None):
    import reel as R
    fonts = R.ff("NST", "noto-sans-tamil", [500, 600, 700])
    icons = {}
    for k, name in (("newspaper", "newspaper"), ("calendar", "calendar-days")):
        try:
            icons[k] = R.icon(name)
        except BaseException:      # an icon missing on the machine: the text alone
            icons[k] = ""
    logo = (R.KIT / pg["logo"]).as_posix()
    imgs = spec["images"]
    layers = "".join(f'<img class="pic" id="p{i}" src="file://{Path(p).resolve().as_posix()}">' for i, p in enumerate(imgs))
    hook = spec.get("hook") or []
    head = str(spec.get("cb_head") or (hook[0] if hook else "") or spec.get("mini") or "")
    sl = [{"a": float(s["a"]), "b": float(s["b"])} for s in sents]
    if outro:
        sl.append({"a": float(outro["a"]), "b": float(outro["b"])})
    data = {"total": float(total), "end_t": float(end_t), "n": len(imgs), "shots": shots, "sents": sl,
            "band": bands(spec, sents), "words": words(caps, sents, outro)}
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts}{CSS}</style></head><body>
{layers}<div id="fade"></div>
<div id="acc"></div><div id="pub">{E(pg['name'])}</div><div id="desc">{E(pg.get('tagline', ''))}</div>
<div id="plogo"><img src="file://{logo}"></div>
{f'<div id="loc">{E(str(spec.get("location")))}</div>' if spec.get("location") else ''}
<div id="hl">{E(head)}</div>
<div id="band"><span id="bt"></span></div>
<div id="sup"></div><div id="meas"></div>
<div id="rule"></div><div id="foot">{footer(spec, icons)}</div>
<script>
const D={json.dumps(data, ensure_ascii=False)};
{JS}
</script></body></html>"""
