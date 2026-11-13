"""Compatibility for old integrations; all inference is local Altair."""
from altair_core.runtime import load_settings, save_settings, stream_chat


def api_configured(settings):
    return False


def pick_brain(q, intent, st=None, had_correction=False):
    return "local", "Altair local-only"


def stream_ollama(ctx, num_predict):
    yield from stream_chat(ctx, history=[], remember=False, max_tokens=num_predict)


def stream_answer(pick, ctx, num_predict, st):
    if pick != "local":
        raise RuntimeError("API ngoài đã tắt trong bản Altair local.")
    yield from stream_ollama(ctx, num_predict)


def stream_openai(*args, **kwargs):
    raise RuntimeError("API ngoài đã tắt trong bản Altair local.")


def brain_label(pick, st):
    return "local:altair"
