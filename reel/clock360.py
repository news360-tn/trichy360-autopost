"""owner 20 Nov: the 360-degree clock branding on every news reel ("Create news reels to use the clock for 360 degree branding").
A layer laid OVER the finished reel page - the design, colours, text, voice and timing stay exactly as they are:
 1. logo ring: a gold ring round the top logo fills clockwise 0 -> 360 over the reel (reel progress, like a clock hand)
 2. opening: in the first 0.7 s a bright 360 ring draws round the logo once (the hook text is untouched)
 3. picture change: a clockwise clock-hand sweep (0.35 s) when the picture really changes (not on a one-picture reel)
 4. end card: a gold ring closes 360 round the logo, a faint clock bezel turns behind it

add(page_html) -> the page with the layer. It never fails the reel: anything unexpected (a page without the logo / end card / renderAt)
returns the page unchanged. REEL_CLOCK360=0 switches it off."""
import os

GOLD = "#FFD233"
_TICKS = "".join(f'<line x1="50" y1="{1.5 if i % 5 == 0 else 3}" x2="50" y2="{7 if i % 5 == 0 else 5.5}" '
                 f'stroke-width="{1.6 if i % 5 == 0 else .8}" transform="rotate({i * 6} 50 50)"/>' for i in range(60))
CSS = f"""
.ck{{position:absolute;z-index:31;pointer-events:none;visibility:hidden}}
.ck svg{{position:absolute;inset:0;width:100%;height:100%;overflow:visible}}
.ck .tk line{{stroke:#fff;opacity:.85}} .ck .tr{{fill:none;stroke:rgba(255,255,255,.28);stroke-width:4}}
.ck .pr,.ck .op{{fill:none;stroke:{GOLD};stroke-linecap:round;filter:drop-shadow(0 0 6px rgba(255,210,51,.85))}}
.ck .pr{{stroke-width:5}} .ck .op{{stroke-width:8}}
#ckend{{z-index:41}} #ckend .tk line{{stroke:{GOLD};opacity:.35}}
#ckhand{{position:absolute;left:536px;top:-340px;width:8px;height:1300px;border-radius:4px;z-index:35;visibility:hidden;pointer-events:none;
 transform-origin:50% 100%;background:linear-gradient(0deg,{GOLD} 0%,#FFF3B0 70%,rgba(255,243,176,0) 100%);
 box-shadow:0 0 18px rgba(255,210,51,.9),0 0 46px rgba(255,210,51,.55)}}
#ckpiv{{position:absolute;left:516px;top:936px;width:48px;height:48px;border-radius:50%;background:{GOLD};border:6px solid #071433;z-index:36;visibility:hidden}}
"""


def _ring(i, opening):
    return (f'<div class="ck" id="{i}"><svg viewBox="0 0 100 100"><g class="tk">{_TICKS}</g><circle class="tr" cx="50" cy="50" r="46"/>'
            f'<circle class="pr" cx="50" cy="50" r="46" transform="rotate(-90 50 50)"/>'
            + ('<circle class="op" cx="50" cy="50" r="46" transform="rotate(-90 50 50)"/>' if opening else "") + '</svg></div>')


HTML = _ring("cklogo", True) + _ring("ckend", False) + '<div id="ckhand"></div><div id="ckpiv"></div>'
JS = """<script>
(function(){const old=window.renderAt; if(typeof old!=='function')return;
const C=2*Math.PI*46, cl=x=>Math.max(0,Math.min(1,x)), eo=x=>1-Math.pow(1-x,3);
function fit(ck, el, pad){const r=el.getBoundingClientRect(); ck.style.left=(r.left-pad)+'px'; ck.style.top=(r.top-pad)+'px';
 ck.style.width=(r.width+2*pad)+'px'; ck.style.height=(r.height+2*pad)+'px';}
function arc(c, q){c.style.strokeDasharray=C; c.style.strokeDashoffset=(C*(1-q)).toFixed(2);}
window.renderAt=function(t){old(t);
 try{
  const lg=document.getElementById('plogo'), ck=document.getElementById('cklogo');
  if(lg&&ck){ck.style.visibility=(t<D.end_t||!document.getElementById('end'))?'visible':'hidden'; /* no end card: the full ring stays */ fit(ck, lg, 16); arc(ck.querySelector('.pr'), cl(t/D.end_t));
    const op=ck.querySelector('.op'); arc(op, eo(cl(t/0.7))); op.style.opacity=t<0.7?1:cl(1-(t-0.7)/0.35);}
  const hand=document.getElementById('ckhand'), piv=document.getElementById('ckpiv'); let hv=false;
  if(D.shots&&D.shots.length&&!D.single){
    let ai=D.shots.length-1; D.shots.forEach((s,i)=>{if(t>=s.a&&t<s.b)ai=i});
    const a=D.shots[ai], prev=ai>0?D.shots[ai-1]:null, k=t-a.a, W=0.35;
    for(let i=0;i<D.n;i++){const e=document.getElementById('p'+i); if(e){e.style.webkitMaskImage='none'; e.style.maskImage='none';}}
    const el=a&&document.getElementById('p'+a.img), pe=prev&&document.getElementById('p'+prev.img);
    if(el&&pe&&prev.img!==a.img&&k<W&&t<D.end_t){
      const ang=360*eo(k/W), m='conic-gradient(from 0deg at 50% 50%,#000 0deg '+ang.toFixed(1)+'deg,transparent '+ang.toFixed(1)+'deg 360deg)';
      el.style.opacity=1; el.style.zIndex=2; el.style.webkitMaskImage=m; el.style.maskImage=m; pe.style.opacity=1; pe.style.zIndex=1;
      hand.style.transform='rotate('+ang.toFixed(1)+'deg)'; hv=true;}
  }
  hand.style.visibility=piv.style.visibility=hv?'visible':'hidden';
  const ei=document.querySelector('#end img'), ce=document.getElementById('ckend'), en=document.getElementById('end'), u=t-D.end_t;
  if(ei&&ce&&en){ce.style.visibility=u>0?'visible':'hidden';
    if(u>0){fit(ce, ei, 26); ce.style.opacity=en.style.opacity; arc(ce.querySelector('.pr'), eo(cl((u-0.25)/0.8)));
      ce.querySelector('.tk').setAttribute('transform','rotate('+(u*20).toFixed(2)+' 50 50)');}}
 }catch(e){}
};})();
</script>"""


def on():
    return os.environ.get("REEL_CLOCK360", "1") not in ("0", "false", "no")


def add(page_html):
    """the finished reel page + the 360 clock layer; the page unchanged when it is switched off or the page is not the expected one"""
    try:
        if not on() or 'id="cklogo"' in page_html:
            return page_html
        if any(page_html.count(x) != 1 for x in ("</style>", "</body>")) or 'id="plogo"' not in page_html \
                or "window.renderAt" not in page_html or page_html.count('<div id="end">') > 1:
            return page_html
        page_html = page_html.replace("</style>", CSS + "</style>", 1)
        if '<div id="end">' in page_html:
            page_html = page_html.replace('<div id="end">', HTML + '\n<div id="end">', 1)
        else:      # owner 20 Nov: a design without an end card (design360) - the layer goes on top
            page_html = page_html.replace("</body>", HTML + "\n</body>", 1)
        return page_html.replace("</body>", JS + "</body>", 1)
    except Exception:
        return page_html
