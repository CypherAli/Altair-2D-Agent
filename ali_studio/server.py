"""Compatibility entrypoint for old shortcuts; serve the new Altair core."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from altair_core.server import H, ThreadingHTTPServer, serve

if __name__ == "__main__":
    serve()
