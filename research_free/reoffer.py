"""python research_free/reoffer.py RN-24 RN-27 ...  -> stories not yet posted go back to 'Awaiting images' + ONE new email with the corrected prompt file."""
import json, os, sys, requests
r = requests.post(os.environ["BRIDGE_URL"], params={"key": os.environ["BRIDGE_KEY"]}, data=json.dumps({"action": "reoffer", "ids": sys.argv[1:]}), timeout=180)
print(r.status_code, r.text[:400])
r.raise_for_status()
