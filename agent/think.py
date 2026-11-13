"""Legacy mode adapter: one inference, no automatic multi-pass cost."""
from altair_core.runtime import ask, stream_chat


def twopass(prompt, max_tokens=384):
    return ask(prompt, max_tokens=max_tokens)


def twopass_stream(prompt, max_tokens=384):
    for token in stream_chat(prompt, history=[], remember=False, max_tokens=max_tokens):
        yield "answer", token
