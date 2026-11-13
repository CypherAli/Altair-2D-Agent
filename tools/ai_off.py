"""Compatibility: python tools/ai_off.py on|off. 'on' means AI off."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from altair_core import runtime

if __name__ == "__main__":
    off = len(sys.argv) < 2 or sys.argv[1].lower() == "on"
    runtime.save_settings({"ai_off": "1" if off else "0"})
    if off:
        runtime.unload()
    print("Altair: AI đã tắt." if off else "Altair: AI đã bật.")
