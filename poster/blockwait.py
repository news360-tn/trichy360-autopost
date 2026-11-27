"""owner 27 Nov: when Instagram / Facebook / YouTube temporarily blocks a page, wait the time the platform gives - never try again and
again during a block. When the platform gives no time, wait 2 hours (DEFAULT_HOURS)."""
import re

DEFAULT_HOURS = 2.0
_UNIT_H = {"second": 1 / 3600, "sec": 1 / 3600, "minute": 1 / 60, "min": 1 / 60, "hour": 1.0, "hr": 1.0, "day": 24.0}
_REGAIN = re.compile(r"estimated_time_to_regain_access['\"]?\s*[:=]\s*(\d+)", re.I)      # Meta's usage headers / errors: minutes
_SPOKEN = re.compile(r"(?:try again|retry|wait|blocked|restricted|limited|for|in|after)\D{0,25}?(\d+(?:\.\d+)?)\s*"
                     r"(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b", re.I)


def stated_hours(err):
    """the wait the platform itself states in its error (hours), or None when it states none"""
    t = str(err or "")
    m = _REGAIN.search(t)
    if m and int(m.group(1)) > 0:
        return int(m.group(1)) / 60
    m = _SPOKEN.search(t)
    if m:
        unit = m.group(2).lower().rstrip("s")
        h = float(m.group(1)) * _UNIT_H.get(unit, _UNIT_H.get(unit[:3], 1.0))
        if h > 0:
            return min(h, 24 * 30)
    return None


def wait_hours(err, default=DEFAULT_HOURS):
    """the time to wait after a temporary block: the platform's own time, else 2 hours"""
    h = stated_hours(err)
    return h if h else float(default)
