"""Tamil newsreader voice (AI4Bharat Indic-TTS FastPitch + HiFi-GAN, trained on real Tamil speakers).
Usage: python3 tts.py lines.json outdir [female|male]
Model folder: $TA_MODEL (default /home/claude/tts/ta) containing fastpitch/ and hifigan/.
Writes outdir/line{i}.wav (22.05 kHz) for each line, with light broadcast EQ.
"""
import json, sys, os, re, subprocess, tempfile
from pathlib import Path

M = Path(os.environ.get("TA_MODEL", Path(__file__).resolve().parent / "models" / "ta"))
ONES = ["", "ஒன்று", "இரண்டு", "மூன்று", "நான்கு", "ஐந்து", "ஆறு", "ஏழு", "எட்டு", "ஒன்பது"]

def fix_config():
    cfg = M / "fastpitch" / "config.json"
    c = json.loads(cfg.read_text())
    sp = str(M / "fastpitch" / "speakers.pth")
    if c.get("speakers_file") != sp:
        c["speakers_file"] = sp
        if "model_args" in c:
            c["model_args"]["speakers_file"] = sp
        cfg.write_text(json.dumps(c, ensure_ascii=False, indent=1))

DASH = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D"      # hyphen, en/em dash, minus sign and look-alikes
ROUTE = r"(ரயில்|ரெயில்|பேருந்து|பஸ்|விமான)"


def dashes(t):
    """a dash between words is never read out ('சேலம் - நாமக்கல் மாவட்ட எல்லை' -> 'சேலம், நாமக்கல் மாவட்ட எல்லை');
    a route is read 'கோவை முதல் நாகர்கோவில் வரை ரயில்'; a dash inside a word ('டி-20', 'கோவை-திருச்சி') becomes a space"""
    d = "[" + re.escape(DASH) + "]"
    w = r"([\u0B80-\u0BFFA-Za-z]+)"
    t = re.sub(w + r"\s*" + d + r"\s*" + w + r"(\s+)" + ROUTE, r"\1 முதல் \2 வரை\3\4", t)
    t = re.sub(r"\s+" + d + r"+\s*|\s*" + d + r"+\s+", ", ", t)      # spaced dash -> a short pause
    t = re.sub(d + "+", " ", t)                                         # dash inside a word -> space
    return re.sub(r"(,\s*){2,}", ", ", t)


def clean(t):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from tamilnum import speak_numbers
    t = speak_numbers(t)          # whole numbers in Tamil words (was: every digit read separately, "56" -> "ஐந்து ஆறு"); 10-15 -> 10 முதல் 15
    t = re.sub(r"\d", lambda m: ONES[int(m.group())] or "பூஜ்ஜியம்", t)
    t = dashes(t)
    t = t.replace("!", ".").replace("?", ".")
    # no dash of any kind reaches the voice (owner 1 Nov, RN-256: 'சேலம் - நாமக்கல்' was read 'சேலம் மைனஸ் நாமக்கல்')
    allowed = set(" ,.0ஃஅஆஇஈஉஊஎஏஐஒஓஔகஙசஜஞடணதநனபமயரறலளழவஷஸஹாிீுூெேைொோௌ்ௗ¡'(),.:;¿")
    return re.sub(r"\s+", " ", "".join(ch for ch in t if ch in allowed)).strip()

def main(lines_path, outdir, voice="female"):
    fix_config()
    from TTS.utils.synthesizer import Synthesizer
    syn = Synthesizer(
        tts_checkpoint=str(M / "fastpitch" / "best_model.pth"),
        tts_config_path=str(M / "fastpitch" / "config.json"),
        tts_speakers_file=str(M / "fastpitch" / "speakers.pth"),
        vocoder_checkpoint=str(M / "hifigan" / "best_model.pth"),
        vocoder_config=str(M / "hifigan" / "config.json"),
        use_cuda=False,
    )
    names = list(syn.tts_model.speaker_manager.name_to_id) if syn.tts_model.speaker_manager else []
    spk = next((n for n in names if n.lower().startswith(voice.lower())), names[0] if names else None)
    print("speakers:", names, "->", spk)
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    for i, line in enumerate(json.loads(Path(lines_path).read_text())):
        txt = clean(line)
        wav = syn.tts(txt, speaker_name=spk)
        raw = out / f"raw{i}.wav"
        syn.save_wav(wav, str(raw))
        # broadcast polish: trim silence, gentle EQ + compression, slightly faster news pace
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        "atempo=1.06,highpass=f=80,equalizer=f=3000:t=q:w=1:g=3,equalizer=f=200:t=q:w=1:g=2,acompressor=threshold=0.12:ratio=3:attack=5:release=80,"
                        "aecho=0.8:0.3:25:0.08,loudnorm=I=-16:TP=-1.5",
                        "-ar", "22050", str(out / f"line{i}.wav")], check=True)
        print("voice", i, txt)

if __name__ == "__main__":
    main(*sys.argv[1:])
