"""owner 19 Nov (evening): the daily gold & silver rate REEL in the Kovai Minnal / Chennai Minnal pattern ("Kovai Minnal and Chennai
Minnal page refer ... use that design ... update logo branding all are used in my page").

gold360_render.reel_page(p, r) is the design: a 1080x1920 page in OUR 360 brand whose every frame is set by window.seek(t) - the
numbers land on the confirmed rate, nothing estimated. 10 s (gold 4.3 s + silver 4.3 s + follow card 1.4 s), it opens already
showing today's price, music only (our own reel/music.py, the bright bed), no voice. Here: frames at FPS -> H.264 + the music.
Posted AFTER the carousel, separately (gold_daily.post_reel): a reel problem never touches the carousel or the news posts.

  make(page, rates, slide_jpgs, outdir, log) -> (mp4 path, [])      the same call as before; the carousel slides are not used"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FPS = 30
SR = 44100
W, H = 1080, 1920
COVER_MS = 3400      # the reel's cover frame (gold360_render.COVER): the gold screen fully built - Instagram "thumb_offset"


def ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def soundtrack(dur, path, log=print):
    """our own music bed (reel/music.py, the bright mood) for the reel's length -> a wav file; None when it cannot be made"""
    try:
        sys.path.insert(0, str(ROOT / "reel"))
        import music
        music.main(str(path), dur, seed=7, mood="bright")
        return path
    except Exception as e:
        log("music skipped:", str(e)[:150])
        return None


def make(p, r, jpgs, outdir, log=print):
    import gold360_render
    from playwright.sync_api import sync_playwright      # only here: the test machine has no browser
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    html = outdir / "reel.html"
    html.write_text(gold360_render.reel_page(p, r), encoding="utf-8")
    mp4, wav = outdir / "reel.mp4", outdir / "reel_audio.wav"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(f"file://{html.resolve()}")
        pg.evaluate("document.fonts.ready.then(() => 1)")
        pg.wait_for_timeout(400)
        dur = float(pg.evaluate("window.DUR"))
        audio = soundtrack(dur, wav, log)
        cmd = [ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-"]
        cmd += ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono"]      # never a reel without a sound track
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-ar", str(SR), "-shortest", "-movflags", "+faststart", str(mp4)]
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for i in range(int(round(dur * FPS))):
                pg.evaluate(f"window.seek({i / FPS:.4f})")
                enc.stdin.write(pg.screenshot(type="jpeg", quality=92))
        finally:
            enc.stdin.close()
            enc.wait()
        b.close()
    if enc.returncode:
        raise RuntimeError("ffmpeg could not make the reel")
    log(f"reel {mp4.name}: {dur:.1f} s, {'our music' if audio else 'no music'}")
    return mp4, []
