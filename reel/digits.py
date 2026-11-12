"""Display-only helper: the voice needs numbers written as Tamil words, but the on-screen text should show digits
(10 மணி, not பத்து மணி) and 360 (not த்ரீ சிக்ஸ்டி). Never used for the spoken text."""
import re

UNITS = {"ஒன்று": 1, "ஒண்ணு": 1, "ஒன்றாம்": 1, "ஒண்ணாம்": 1, "இரண்டு": 2, "ரெண்டு": 2, "இரண்டாம்": 2, "மூன்று": 3, "மூணு": 3, "மூன்றாம்": 3,
         "நான்கு": 4, "நாலு": 4, "நான்காம்": 4, "ஐந்து": 5, "அஞ்சு": 5, "ஐந்தாம்": 5, "ஆறு": 6, "ஆறாம்": 6, "ஏழு": 7, "ஏழாம்": 7,
         "எட்டு": 8, "எட்டாம்": 8, "ஒன்பது": 9, "ஒன்பதாம்": 9}
TENS_PREFIX = {"இருபத்தி": 20, "இருபத்து": 20, "முப்பத்தி": 30, "நாற்பத்தி": 40, "ஐம்பத்தி": 50, "அறுபத்தி": 60, "எழுபத்தி": 70, "எண்பத்தி": 80}
SINGLE = {"பத்து": 10, "பதினொன்று": 11, "பதினொரு": 11, "பன்னிரண்டு": 12, "பன்னிரெண்டு": 12, "பதிமூன்று": 13, "பதினான்கு": 14, "பதினைந்து": 15,
          "பதினாறு": 16, "பதினேழு": 17, "பதினெட்டு": 18, "பத்தொன்பது": 19, "இருபது": 20, "முப்பது": 30, "நாற்பது": 40, "ஐம்பது": 50,
          "அறுபது": 60, "எழுபது": 70, "எண்பது": 80, "தொண்ணூறு": 90, "நூறு": 100, "பத்தாம்": 10, "பதினொன்றாம்": 11, "பன்னிரண்டாம்": 12, "பதிமூன்றாம்": 13, "பதினான்காம்": 14, "பதினைந்தாம்": 15, "பதினாறாம்": 16, "பதினேழாம்": 17, "பதினெட்டாம்": 18, "பத்தொன்பதாம்": 19, "நாற்பதாம்": 40, "இருபதாம்": 20, "முப்பதாம்": 30}
UNIT_SKIP = {"ஒரு"}


def _tok(w):
    return w


def to_digits(text):
    text = re.sub(r"த்ரீ\s+சிக்ஸ்டி", "360", text)
    words = text.split(" ")
    out, i = [], 0
    while i < len(words):
        w = words[i]
        core = w.rstrip(".,!?:;")
        tail = w[len(core):]
        if core in TENS_PREFIX:
            n = TENS_PREFIX[core]
            nxt = words[i + 1].rstrip(".,!?:;") if i + 1 < len(words) else ""
            if nxt in UNITS:
                tail2 = words[i + 1][len(nxt):]
                suffix = "ஆம்" if nxt.endswith("ாம்") or nxt.endswith("ம்") and nxt in ("ஒன்றாம்", "ஒண்ணாம்") else ""
                out.append(str(n + UNITS[nxt]) + ("ஆம்" if nxt.endswith("ாம்") or nxt.endswith("ணாம்") else "") + tail2)
                i += 2
                continue
            out.append(str(n) + tail)
        elif core in SINGLE:
            out.append(str(SINGLE[core]) + ("ஆம்" if core.endswith("ாம்") else "") + tail)
        elif core in UNITS and core not in UNIT_SKIP and core not in ("ஒன்று", "ஒண்ணு"):
            out.append(str(UNITS[core]) + ("ஆம்" if core.endswith("ாம்") else "") + tail)
        else:
            out.append(w)
        i += 1
    return " ".join(out)


if __name__ == "__main__":
    for t in ["காலை பத்து மணி முதல் மாலை ஐந்து மணி வரை", "அக்டோபர் இருபத்தி ஒண்ணாம் தேதி", "கோயம்புத்தூர் த்ரீ சிக்ஸ்டி பக்கம்", "ஒரு மணி நேரம்", "ஏழு பேர் காயம்."]:
        print(to_digits(t))
