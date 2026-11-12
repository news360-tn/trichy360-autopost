# minimal stub: the Tamil FastPitch voice does not use torchaudio
import types, sys
class _Dummy:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): raise RuntimeError("torchaudio stub")
class _M(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"): raise AttributeError(k)
        if k[:1].isupper(): return type(k, (_Dummy,), {})
        name = self.__name__ + "." + k
        m = sys.modules.get(name) or _M(name); sys.modules[name] = m; return m
for n in ["functional", "transforms", "compliance", "compliance.kaldi", "io", "backend", "sox_effects", "pipelines", "models"]:
    sys.modules["torchaudio." + n] = _M("torchaudio." + n)
functional = sys.modules["torchaudio.functional"]; transforms = sys.modules["torchaudio.transforms"]
compliance = sys.modules["torchaudio.compliance"]; io = sys.modules["torchaudio.io"]
def load(*a, **k): raise RuntimeError("torchaudio stub")
__version__ = "0.0-stub"
