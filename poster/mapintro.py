"""owner 28 Nov (approved after the samples, Trichy only - poster/config.json "map_intro": true): the news reel's first 2.6 s become a
district-map zoom to the news town - the district outline draws, the camera zooms to the town, a pin drops with the town's name, the
headline sits on a dark band. The reel's own voice runs from 0 s (the spoken hook is never delayed); from 2.6 s the reel goes on as made.
apply(mp4, location, headline, work, log) replaces the mp4 in place; a news without a known town keeps its reel as it is. Never raises."""
import json
import re
import shutil
import subprocess
import sys
from html import escape as E
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTRO_S, FPS, W, H = 2.6, 30, 1080, 1920


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def town_of(location, towns):
    """the most specific town of the district map named in the location ('ஸ்ரீரங்கம், திருச்சி' -> ஸ்ரீரங்கம்), or ''"""
    loc = str(location or "").strip()
    t = next((t for t in sorted(towns, key=len, reverse=True) if t in loc), "")
    first = loc.split(",")[0].strip()
    if t in ("திருச்சி", "திருச்சிராப்பள்ளி") and not first.startswith(t):      # 'X, திருச்சி' with X not on the map: no pin on the city
        return ""
    return t


def html(m, town, xy, head):
    sys.path.insert(0, str(ROOT / "goldrate"))
    import gold360_render as G
    tx, ty = xy
    css = f"""
body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:radial-gradient(circle at 50% 42%,{G.MAROON2} 0%,{G.MAROON} 70%);
 font-family:'Noto Sans Tamil',sans-serif}}
#map{{position:absolute;left:40px;top:330px;width:1000px;height:1000px;overflow:visible}}
#d{{fill:{G.GOLD};stroke:{G.GOLD};stroke-width:1.6;stroke-linejoin:round;fill-opacity:0}}
#pin circle.dot{{fill:#FF3B30;stroke:#fff;stroke-width:1.6}} .ring{{fill:none;stroke:#FF3B30;stroke-width:1.2}}
#top{{position:absolute;left:0;right:0;top:120px;text-align:center;color:#F6E3A6;font-size:46px;font-weight:800;letter-spacing:2px}}
#lb{{position:absolute;left:0;right:0;top:1080px;text-align:center;transform-origin:50% 50%}}
#lb span{{display:inline-block;background:#fff;color:{G.MAROON};border-radius:60px;padding:14px 46px;font-size:76px;font-weight:900;
 box-shadow:0 18px 40px rgba(0,0,0,.45),inset 0 0 0 6px {G.GOLD}}}
#hd{{position:absolute;left:50px;right:50px;bottom:230px;text-align:center;color:#fff;font-size:56px;font-weight:900;line-height:1.3;z-index:3;
 background:rgba(0,0,0,.62);border-radius:30px;padding:24px 30px;box-shadow:0 14px 34px rgba(0,0,0,.45)}}
#fl{{position:absolute;inset:0;background:#fff;opacity:0}}
"""
    js = (f"window.DUR={INTRO_S};const TX={tx},TY={ty};" + """
const P=document.getElementById('d'),L=P.getTotalLength(),CAM=document.getElementById('cam'),PIN=document.getElementById('pin'),
 R1=document.getElementById('r1'),R2=document.getElementById('r2'),LB=document.getElementById('lb'),HD=document.getElementById('hd'),FL=document.getElementById('fl');
P.style.strokeDasharray=L;
const cl=u=>Math.max(0,Math.min(1,u)),ez=u=>{u=cl(u);return 1-Math.pow(1-u,3)};
window.seek=function(t){
 P.style.strokeDashoffset=L*(1-ez(t/0.8));
 P.style.fillOpacity=0.18*ez((t-0.5)/0.4);
 const q=ez((t-0.7)/1.0),z=1+2.4*q;
 CAM.setAttribute('transform','translate(130 130) scale('+z+') translate('+(-(130+(TX-130)*q))+' '+(-(130+(TY-130)*q))+')');
 const p=ez((t-1.0)/0.35);PIN.style.opacity=p;PIN.setAttribute('transform','translate(0 '+(-30*(1-p))+')');
 [R1,R2].forEach((r,i)=>{const w=((t-1.2-i*0.35)%0.9+0.9)%0.9/0.9;r.setAttribute('r',4+14*w);r.style.opacity=t>1.2+i*0.35?(1-w):0});
 LB.style.opacity=ez((t-1.25)/0.3);LB.style.transform='scale('+(0.7+0.3*ez((t-1.25)/0.3))+')';
 HD.style.opacity=ez((t-0.2)/0.3);
 FL.style.opacity=t>2.35?cl((t-2.35)/0.12)*(1-cl((t-2.47)/0.13)):0;
};
window.seek(0);""")
    pin = ('<svg viewBox="0 0 24 34" width="44" height="62" style="vertical-align:-10px;margin-right:14px"><path d="M12 0C5.4 0 0 5.2 0 11.6 '
           '0 20.3 12 34 12 34s12-13.7 12-22.4C24 5.2 18.6 0 12 0z" fill="#FF3B30"/><circle cx="12" cy="11.5" r="4.6" fill="#fff"/></svg>')
    page = {"name1": "திருச்சி"}
    return G.themed(f"""<!doctype html><html><head><meta charset="utf-8"><style>{G.css()}{css}</style></head><body>
<div id="top">{E(m.get('district_ta', ''))} மாவட்டம்</div>
<svg id="map" viewBox="0 0 260 260"><g id="cam"><path id="d" d="{m['path']}"/>
<g id="pin" style="opacity:0"><circle id="r1" class="ring" cx="{tx}" cy="{ty}" r="4"/><circle id="r2" class="ring" cx="{tx}" cy="{ty}" r="4"/>
<circle class="dot" cx="{tx}" cy="{ty}" r="4.2"/></g></g></svg>
<div id="lb"><span>{pin}{E(town)}</span></div><div id="hd">{E(head)}</div><div id="fl"></div>
<script>{js}</script></body></html>""", page)


def apply(mp4, location, headline, work, log=print):
    try:
        m = json.loads((ROOT / "reel" / "assets" / "district_map.json").read_text(encoding="utf-8"))
        town = town_of(location, m.get("towns", {}))
        if not town:
            log("map opening: no town of the district in the location - the reel stays as it is:", str(location)[:60])
            return False
        head = re.sub(r"^[^஀-௿A-Za-z0-9]+", "", str(headline or "")).strip()
        work = Path(work)
        page = work / "map_intro.html"
        page.write_text(html(m, town, m["towns"][town], head), encoding="utf-8")
        intro = work / "map_intro.mp4"
        from playwright.sync_api import sync_playwright
        ff = _ffmpeg()
        enc_cmd = [ff, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                   "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", str(intro)]
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": W, "height": H})
            pg.goto(f"file://{page.resolve()}")
            pg.evaluate("document.fonts.ready.then(() => 1)")
            pg.wait_for_timeout(600)
            enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)
            try:
                for i in range(int(round(INTRO_S * FPS))):
                    pg.evaluate(f"window.seek({i / FPS:.4f})")
                    enc.stdin.write(pg.screenshot(type="jpeg", quality=90))
            finally:
                enc.stdin.close()
                enc.wait()
            b.close()
        if enc.returncode or not intro.exists():
            raise RuntimeError("the map opening could not be encoded")
        out = work / "reel_with_map.mp4"
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(intro), "-i", str(mp4), "-filter_complex",
                        f"[0:v]fps={FPS},scale={W}:{H},setsar=1,format=yuv420p[i];"
                        f"[1:v]trim=start={INTRO_S},setpts=PTS-STARTPTS,fps={FPS},scale={W}:{H},setsar=1,format=yuv420p[r];[i][r]concat=n=2:v=1:a=0[v]",
                        "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "copy",
                        "-shortest", "-movflags", "+faststart", str(out)], check=True)
        shutil.move(str(out), str(mp4))
        log(f"map opening added: {town}")
        return True
    except Exception as e:
        log("map opening not added (the reel goes out as it is):", str(e)[:200])
        return False
