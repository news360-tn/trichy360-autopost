"""owner 20 Nov: the daily rasipalan as a REEL (no carousel) - rasi360_render.reel_page drawn frame by frame (window.seek(t)), H.264,
our own music bed only (reel/music.py, the bright mood), no voice. The same way as the gold rate reel (goldrate/gold_reel.py).
make(p, ctx, outdir, log) -> mp4 path      p: town, name1, handle, logo; ctx: {"p": panchangam, "rasis": the 12 written rasis}"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "goldrate"))
import gold_reel      # noqa: E402  (ffmpeg + the music bed)

FPS, W, H = 30, 1080, 1920
COVER_MS = 500      # the reel's cover: today's panchangam screen (complete from the first frame)


def make(p, ctx, outdir, log=print):
    import rasi360_render
    from playwright.sync_api import sync_playwright
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    html = outdir / "reel.html"
    html.write_text(rasi360_render.reel_page(p, ctx), encoding="utf-8")
    mp4, wav = outdir / "rasipalan_reel.mp4", outdir / "reel_audio.wav"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(f"file://{html.resolve()}")
        pg.evaluate("document.fonts.ready.then(() => 1)")
        pg.wait_for_timeout(500)
        dur = float(pg.evaluate("window.DUR"))
        audio = gold_reel.soundtrack(dur, wav, log)
        cmd = [gold_reel.ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-"]
        cmd += ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]      # never a reel without sound
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-ar", "44100", "-shortest", "-movflags", "+faststart", str(mp4)]
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for i in range(int(round(dur * FPS))):
                pg.evaluate(f"window.seek({i / FPS:.4f})")
                enc.stdin.write(pg.screenshot(type="jpeg", quality=90))
        finally:
            enc.stdin.close()
            enc.wait()
        b.close()
    if enc.returncode or not mp4.exists():
        raise RuntimeError("ffmpeg could not make the rasipalan reel")
    log(f"rasipalan reel {mp4.name}: {dur:.1f} s, {'our music' if audio else 'no music'}")
    return mp4
