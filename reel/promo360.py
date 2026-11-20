"""owner 20 Nov: the sponsor ad on a news reel (only for an APPROVED promotion - poster/promo.py decides which reel gets one).
ONE place: the big free space at the BOTTOM of the reel, under the captions; DURING THE NEWS ONLY (from 3 s to the end of the
news). The page's footer logo strip is hidden while the ad shows; the news design and the page's own FOLLOW end card never change;
the reel is not longer. Marked "விளம்பரம் • AD".
add(page_html, promo) -> page_html; promo = {title, message, image (optional)}. Nothing changes if the page is not the expected one."""
import html as _h

E = _h.escape
CSS = """
#adbox{position:absolute;left:40px;top:1548px;width:1000px;height:300px;background:#FF1B1B;border-radius:22px;z-index:45;opacity:0;
 display:flex;align-items:center;gap:30px;padding:26px 34px;box-shadow:0 12px 40px rgba(0,0,0,.45);overflow:hidden}
#adbox .im{flex:none;width:248px;height:248px;border-radius:18px;object-fit:cover;background:#fff;border:4px solid #fff}
#adbox .t{min-width:0;flex:1;display:flex;flex-direction:column;gap:12px}
#adbox .b{align-self:flex-start;background:#FFD114;color:#090E14;font:800 30px/1 'NST','CT',sans-serif;padding:10px 16px;border-radius:8px}
#adbox .t1{font:800 50px/1.18 'NST','CT',sans-serif;color:#fff;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
#adbox .t2{font:600 34px/1.3 'NST','CT',sans-serif;color:#FFF1C2;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
"""
JS = """<script>
(function(){const old=window.renderAt, cl=x=>Math.max(0,Math.min(1,x));
window.renderAt=function(t){old(t); const e=D.end_t, box=document.getElementById('adbox'), ft=document.getElementById('foot');
  const v=(t>=3&&t<e)?cl((t-3)/0.4)*cl((e-t)/0.3):0;      /* during the news only - never on the FOLLOW end card */
  box.style.opacity=v; box.style.transform='translateY('+((1-v)*30).toFixed(1)+'px)';
  if(ft) ft.style.visibility=v>0?'hidden':'visible';      /* the footer logo strip is hidden while the ad shows */
};})();
</script>"""


def add(page_html, promo):
    try:
        if not promo or not page_html or 'id="adbox"' in page_html or "window.renderAt" not in page_html:
            return page_html
        if page_html.count("</style>") < 1 or page_html.count("</body>") != 1:
            return page_html
        pic = f'<img class="im" src="file://{E(promo["image"])}">' if promo.get("image") else ""
        box = (f'<div id="adbox">{pic}<div class="t"><span class="b">விளம்பரம் • AD</span>'
               f'<div class="t1">{E(str(promo.get("title") or ""))}</div><div class="t2">{E(str(promo.get("message") or ""))}</div></div></div>')
        return page_html.replace("</style>", CSS + "</style>", 1).replace("</body>", box + JS + "</body>", 1)
    except Exception:
        return page_html
