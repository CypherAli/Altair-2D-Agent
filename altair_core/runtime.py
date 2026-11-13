"""One local model, bounded context, real streaming and cancellation. Stdlib only."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from collections import OrderedDict
from . import harness, skills, judgment, conversation, speech

ROOT = Path(os.environ.get("ALTAIR_ROOT", Path(__file__).resolve().parents[1])).resolve()
DATA = ROOT / ".altair-runtime"
MODEL = "altair"
BACKEND = "litert"
BASE_MODEL = "google/gemma-4-E2B-it (mobile LiteRT)"
CORE_VERSION = "2026.11.04-rig4"
DEFAULTS = {"mode": "local", "ai_off": "0", "num_ctx": 2048,
            "num_predict": 384, "num_thread": 4, "keep_alive": "adaptive"}
SYSTEM = harness.SYSTEM
_state_lock = threading.RLock()
_inference_lock = threading.Lock()
_active = None
_cancelled = threading.Event()
_last_metrics = {}
_last_sources = []
_request_result = threading.local()
_answer_cache = OrderedDict()
_stats = {"model_calls": 0, "tool_calls": 0, "cache_hits": 0, "search_calls": 0}


class BusyError(RuntimeError):
    pass


class CancelledError(RuntimeError):
    pass


def _read(name, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(name, value):
    DATA.mkdir(parents=True, exist_ok=True)
    target = DATA / name
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=None if name=='conversation.json' else 2), encoding="utf-8")
    temp.replace(target)


def load_settings():
    with _state_lock:
        saved = _read("settings.json", {})
        result = dict(DEFAULTS)
        if isinstance(saved, dict):
            result.update({k: saved[k] for k in DEFAULTS if k in saved})
        result["mode"] = "local"
        for key, low, high in (("num_ctx", 2048, 4096), ("num_predict", 64, 768),
                               ("num_thread", 1, 4)):
            try:
                result[key] = max(low, min(high, int(result[key])))
            except (ValueError, TypeError):
                result[key] = DEFAULTS[key]
        result["ai_off"] = "1" if result["ai_off"] == "1" else "0"
        result["keep_alive"] = "adaptive"
        result["model"] = MODEL
        result["api_key"] = ""
        return result


def save_settings(patch):
    with _state_lock:
        current = load_settings()
        if "mode" in patch and patch["mode"] not in ("local", "auto", "nhanh", "ky"):
            raise ValueError("Altair chỉ sử dụng model local, không gọi API trả phí.")
        for key in ("ai_off", "num_ctx", "num_predict", "num_thread"):
            if key in patch:
                current[key] = patch[key]
        for key, low, high in (("num_ctx", 2048, 4096), ("num_predict", 64, 768),
                               ("num_thread", 1, 4)):
            try:
                value = int(current[key])
            except (ValueError, TypeError):
                raise ValueError(f"{key} phải là số nguyên.") from None
            if not low <= value <= high:
                raise ValueError(f"{key} phải nằm trong {low}–{high}.")
            current[key] = value
        current["ai_off"] = "1" if str(current["ai_off"]) == "1" else "0"
        _write("settings.json", {key: current[key] for key in DEFAULTS})
        return load_settings()


def get_history():
    with _state_lock:
        result = _read("history.json", [])
        return result[-6:] if isinstance(result, list) else []


def clear_history():
    with _state_lock:
        if _inference_lock.locked():
            raise BusyError("Hãy dừng câu trả lời hiện tại trước khi tạo phiên mới.")
        _write("history.json", [])
        _write("conversation.json",conversation.empty())
        _answer_cache.clear()
        from . import litert_backend
        litert_backend.reset_session()


def get_notes():
    with _state_lock:
        result = _read("notes.json", [])
        return result[-30:] if isinstance(result, list) else []


def get_context(history=None):
    if history is not None:return conversation.from_history(history)
    with _state_lock:
        path=DATA/'conversation.json'
        try:
            if path.exists() and path.stat().st_size>conversation.MAX_BYTES+1024:return conversation.empty()
            state=_read('conversation.json',None)
            return conversation.bounded(state) if state is not None else conversation.from_history(get_history())
        except (OSError,ValueError,TypeError,KeyError):return conversation.empty()


def add_note(text):
    text = str(text).strip()
    if not text or len(text) > 500:
        raise ValueError("Ghi nhớ cần từ 1 đến 500 ký tự.")
    with _state_lock:
        notes = get_notes()
        notes.append({"type": "note", "title": text[:70], "text": text,
                      "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
        _write("notes.json", notes[-30:])


def _local_request(path, body=None, timeout=5):
    from . import litert_backend
    return litert_backend.request(path, body, timeout)


def status():
    context=get_context()
    out = {"name": "Altair", "version": CORE_VERSION, "model": MODEL, "base_model": BASE_MODEL,
           "backend": BACKEND, "busy": _inference_lock.locked(), "settings": load_settings(),
           "metrics": dict(_last_metrics), "stats": dict(_stats),
           "skills": [{"name": item.name, "description": item.description} for item in skills.catalog().values()],
           "capabilities": ["chat", "image", "notes", "calculator", "time-planning", "unit-conversion", "sudoku", "web-search", "order-reasoning", "constraint-choice", "everyday-math", "clock-planning", "conversation-context"],
           "working_context":{"topics":len(context['frames']),"bytes":len(json.dumps(context,ensure_ascii=False).encode())}}
    from . import tts
    from . import asr
    out['speech_recognition']=asr.status()
    if out['speech_recognition']['installed']:out['capabilities'].append('offline-japanese-asr')
    out['capabilities'].append('joint-2d-avatar')
    out['voice']=tts.status()
    if out['voice']['installed']:out['capabilities'].append('offline-tts')
    try:
        with _local_request("/api/tags") as response:
            models = json.load(response).get("models", [])
        out["installed"] = any(item.get("name") == MODEL for item in models)
        with _local_request("/api/ps") as response:
            out["loaded_models"] = [{k: m.get(k) for k in ("name", "size", "size_vram")}
                                    for m in json.load(response).get("models", [])]
        out["online"] = True
    except (OSError, ValueError, RuntimeError):
        out.update(online=False, installed=False, loaded_models=[])
    return out


def completed_result():
    return getattr(_request_result, "value", {"metrics": {}, "sources": []})


def cancel():
    global _active
    _cancelled.set()
    with _state_lock:
        response = _active
    if response is not None:
        response.close()


def unload():
    cancel()
    with _local_request("/api/generate", {"model": MODEL, "keep_alive": 0}, timeout=30) as response:
        json.load(response)


def _messages(question, history, images, plan=None, context=None):
    question = str(question).strip()
    if not question or len(question) > 3000:
        raise ValueError("Câu hỏi cần từ 1 đến 3.000 ký tự; hãy chia yêu cầu dài thành từng phần.")
    # Byte budgets are conservative heuristics, not an exact tokenizer.
    plan = plan or harness.plan(question, images)
    notes = "\n".join(harness.relevant_notes(question, get_notes()))
    notes = notes.encode("utf-8")[:500].decode("utf-8", errors="ignore")
    system = harness.system_prompt(plan.skill) + ("\n<notes>\n" + notes + "\n</notes>" if notes else "")
    working=conversation.summary(context) if context else ''
    if working:
        system+='\nBối cảnh do người dùng cung cấp: dùng các giá trị hiện tại, không khôi phục giá trị cũ đã bị sửa. Không hỏi lại dữ kiện đã có. Với gợi ý thông thường, đưa một phương án cụ thể trước; chỉ hỏi nếu thiếu điều kiện thiết yếu. Tôn trọng điều người dùng không muốn hoặc không được dùng. Nếu omitted_details=true thì có phần chưa đưa vào, hãy hỏi khi cần.\n<working_context>\n'+working+'\n</working_context>'
    messages = [{"role": "system", "content": system}]
    remaining = 4800 - len(system.encode("utf-8")) - len(question.encode("utf-8"))
    if remaining < 0:
        raise ValueError("Yêu cầu quá dài cho cấu hình nhẹ. Hãy rút gọn hoặc chia nhỏ.")
    selected = []
    topic=context.get('active') if context else None
    relevant=[row for row in (history or []) if not topic or not row.get('topic_id') or row['topic_id']==topic]
    for record in reversed((relevant[-2:]) if plan.use_history else []):
        q, a = str(record.get("q", "")), str(record.get("a", ""))
        needed = len(q.encode("utf-8")) + len(a.encode("utf-8"))
        if needed > 1400:
            break
        if needed > remaining:
            break
        selected[0:0] = [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        remaining -= needed
    messages.extend(selected)
    message = {"role": "user", "content": question}
    if images:
        if not isinstance(images, list) or len(images) != 1:
            raise ValueError("Cấu hình nhẹ nhận tối đa một ảnh mỗi lượt.")
        try:
            raw = base64.b64decode(images[0], validate=True)
        except (ValueError, TypeError):
            raise ValueError("Ảnh không phải base64 hợp lệ.") from None
        if len(raw) > 3 * 1024 * 1024:
            raise ValueError("Ảnh phải nhỏ hơn 3 MB.")
        if not raw.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
            raise ValueError("Chỉ nhận ảnh PNG hoặc JPEG.")
        message["images"] = images
    messages.append(message)
    return messages


def _remember_turn(question, answer, intent, remember, _context=None, _reset=False, **extra):
    if not remember:
        return
    with _state_lock:
        records = [] if _reset else get_history()
        if _context:extra['topic_id']=_context.get('active')
        records.append({"q": question, "a": answer, "intent": intent, **extra})
        _write("history.json", records[-6:])
        if _context is not None:_write('conversation.json',conversation.observe_answer(_context,_last_metrics))
        if _reset:
            _answer_cache.clear()
            from . import litert_backend
            litert_backend.reset_session()


def _stream_web(question, recent, plan, settings, remember, started, max_tokens, prepared=None, bilingual=False):
    from . import search
    global _active, _last_metrics, _last_sources
    query = prepared.search_query if prepared and prepared.search_query else question
    followup = not (prepared and prepared.search_query) and harness.web_followup(question) and recent and recent[-1].get("intent") == "web-search"
    if followup:
        query = recent[-1].get("search_query", recent[-1]["q"])
    _stats["search_calls"] += 1
    bundle = search.search(query, _cancelled)
    answer = search.quick_answer(bundle)
    _last_sources = bundle.sources
    text = harness.normalize(question)
    explicit_summary=bool(followup or any(term in text for term in ("tom tat", "tong hop", "so sanh", "giai thich")))
    quick_only=bool(re.search(r'tim nhanh|chi (?:lay|tim|trich) nguon',text))
    answer_question=bool(re.search(r'\bai\b|la gi|bao nhieu|thu do|nghien cuu gi|khi gi|viet tat',text))
    summarize = not quick_only and (explicit_summary or answer_question)
    metrics = {"route": "web", "skill": "web-search", "verified": False, "model_calls": 0,
               "answer_mode": "excerpt", **bundle.metadata()}
    response = None
    if summarize and bundle.sources and settings["ai_off"] != "1":
        context = search.model_context(bundle)
        limit = min(settings["num_predict"], (128 if explicit_summary else 64) if max_tokens is None else max(32, min(160, int(max_tokens))))
        question_text = question[:350]
        messages = [{"role": "system", "content": harness.system_prompt("web-search")},
                    {"role": "user", "content": "Câu hỏi: " + question_text + "\nDữ liệu nguồn:\n" + context}]
        if bilingual:
            messages[0]["content"]+=speech.PROMPT
            messages[-1]["content"]+="\nTrả lời theo mẫu VI: tiếng Việt có dấu, rồi JA: tiếng Nhật. Hai phần cùng nội dung."
            limit=min(256,limit+96)
        key = hashlib.sha256(json.dumps([messages, limit, settings["num_ctx"]], ensure_ascii=False).encode()).hexdigest()
        cached = _answer_cache.get(key)
        if cached and time.monotonic() - cached[0] < 300:
            answer = cached[1]; metrics.update(answer_mode="summary", answer_cache_hit=True)
            _stats["cache_hits"] += 1
            if bilingual and len(cached)>2 and cached[2]:metrics["speech_text"]=cached[2]
        else:
            try:
                _stats["model_calls"] += 1; metrics["model_calls"] = 1
                response = _local_request("/api/chat", {"model": MODEL, "messages": messages,
                    "stream": True, "think": False, "options": {"num_ctx": settings["num_ctx"],
                    "num_thread": settings["num_thread"], "num_predict": limit}}, timeout=120)
                with _state_lock: _active = response
                parts, complete = [], False
                for line in response:
                    search.check_cancel(_cancelled)
                    if not line.strip(): continue
                    event = json.loads(line)
                    if event.get("error"): raise RuntimeError(event["error"])
                    parts.append(event.get("message", {}).get("content", ""))
                    if event.get("done"):
                        complete = True; break
                summary = "".join(parts).strip()
                spoken=None
                if bilingual:summary,spoken=speech.split(summary)
                if complete and search.valid_summary(summary, bundle):
                    answer = "Tổng hợp từ nguồn (cần đối chiếu):\n" + summary
                    metrics["answer_mode"] = "summary"
                    if spoken:metrics["speech_text"]=spoken
                    _answer_cache[key] = (time.monotonic(), answer, spoken)
                    _answer_cache.move_to_end(key)
                    while len(_answer_cache) > 32: _answer_cache.popitem(last=False)
                else:
                    metrics["summary_rejected"] = True
            except search.SearchCancelled: raise
            except (OSError, ValueError, RuntimeError):
                search.check_cancel(_cancelled)
                metrics["summary_unavailable"] = True
            finally:
                if response is not None: response.close()
                with _state_lock: _active = None
    search.check_cancel(_cancelled)
    elapsed = round(time.monotonic() - started, 4)
    metrics.update(first_token_s=elapsed, elapsed_s=elapsed,
                   judgment=judgment.assess("web", {"summary": metrics["answer_mode"] == "summary"}, sources=bundle.sources))
    _last_metrics = metrics
    yield answer
    search.check_cancel(_cancelled)
    _remember_turn(question, answer, "web-search", remember, _context=prepared.state if prepared else None, sources=bundle.sources, search_query=query)


def stream_chat(question, images=None, *, history=None, remember=True, max_tokens=None, web=None, bilingual=False):
    """Yield text chunks; only persist complete, uncancelled conversations."""
    global _active, _last_metrics, _last_sources
    if not _inference_lock.acquire(blocking=False):
        raise BusyError("Altair đang trả lời một yêu cầu. Hãy chờ hoặc bấm Dừng.")
    _cancelled.clear()
    _last_sources = []
    response = None
    started = time.monotonic()
    chunks, first, final = [], None, None
    try:
        settings = load_settings()
        if not isinstance(question, str) or not question.strip() or len(question) > 3000:
            raise ValueError("Câu hỏi cần từ 1 đến 3.000 ký tự.")
        recent = get_history() if history is None else history
        if web not in (None, True, False):
            raise ValueError("web cần là true, false hoặc null.")
        raw_plan=harness.plan(question,images,get_notes(),web=web)
        prepared=conversation.prepare(question,get_context(history)) if not images else conversation.Prepared(get_context(history),question)
        effective=prepared.question
        plan=harness.plan(effective,images,get_notes(),web=web)
        if prepared.result is not None:
            keep_raw=raw_plan.result is not None and (raw_plan.skill in ('memory','identity','clock','capabilities') or
                (prepared.result.skill=='conversation-context' and not prepared.correction and not prepared.result.facts.get('needs_clarification')))
            if keep_raw:plan=raw_plan
            else:plan=harness.Plan(prepared.result.skill,prepared.result)
        if prepared.search_query and web is not False:plan=harness.Plan('web-search',use_history=True)
        if prepared.relevant and prepared.result is None:plan.use_history=True
        if prepared.correction and prepared.relevant:
            frame=conversation.active(prepared.state)
            if frame and frame.get('last_updated_fields'):plan.use_history=False
        if web is not False and harness.web_followup(question) and recent and recent[-1].get("intent") == "web-search":
            plan.skill = "web-search"
        if plan.use_history and plan.skill == "conversation" and recent and recent[-1].get("intent") in ("conversation", "explain", "decision", "logic"):
            plan.skill = recent[-1]["intent"]
        if plan.result is not None:
            if "save_note" in plan.result.facts:
                add_note(plan.result.facts["save_note"])
            answer = plan.result.text
            _stats["tool_calls"] += 1
            elapsed = time.monotonic() - started
            context_only=plan.skill=='conversation-context'
            _last_metrics = {"route": "context" if context_only else "skill", "skill": plan.skill, "verified": not context_only,
                "model_calls": 0, "first_token_s": round(elapsed, 4), "elapsed_s": round(elapsed, 4),
                "output_tokens": 0, "tokens_per_s": 0, "facts": plan.result.facts,
                "judgment": judgment.assess("context" if context_only else "skill", plan.result.facts),
                "context_bytes":len(json.dumps(prepared.state,ensure_ascii=False).encode())}
            if bilingual:
                spoken=speech.phrase(question,answer,plan.skill,plan.result.facts)
                if spoken:_last_metrics["speech_text"]=spoken
                sample=speech.sample(question,answer,plan.skill)
                if sample:_last_metrics["speech_sample"]=sample
            yield answer
            if _cancelled.is_set():
                raise CancelledError("Đã dừng.")
            _remember_turn(question, answer, plan.skill, remember,_context=prepared.state,_reset=prepared.reset_history)
            return
        if plan.skill == "web-search":
            yield from _stream_web(question, recent, plan, settings, remember, started, max_tokens,prepared,bilingual)
            return
        if settings["ai_off"] == "1":
            raise RuntimeError("AI đang tắt để tiết kiệm RAM. Công cụ tính toán/Sudoku vẫn dùng được; bật AI để hỏi đáp mở.")
        messages = _messages(effective, recent, images, plan,prepared.state if prepared.relevant else None)
        limit = min(settings["num_predict"], plan.max_tokens) if max_tokens is None else max(1, min(768, int(max_tokens)))
        if bilingual:
            messages[0]["content"]+=speech.PROMPT
            messages[-1]["content"]+="\nTrả lời theo mẫu VI: tiếng Việt có dấu, rồi JA: tiếng Nhật. Hai phần cùng nội dung."
            limit=min(256,limit+96)
        cache_key = None if images else hashlib.sha256(json.dumps({"messages": messages, "limit": limit,
                        "ctx": settings["num_ctx"]}, ensure_ascii=False).encode()).hexdigest()
        cached = _answer_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < 300:
            _answer_cache.move_to_end(cache_key)
            _stats["cache_hits"] += 1
            answer = cached[1]
            spoken=None
            if bilingual:answer,spoken=speech.split(answer)
            elapsed = time.monotonic() - started
            _last_metrics = {"route": "cache", "skill": plan.skill, "verified": False, "model_calls": 0,
                "cache_hit": True, "first_token_s": round(elapsed, 4), "elapsed_s": round(elapsed, 4),
                "output_tokens": 0, "tokens_per_s": 0, "judgment": judgment.assess("cache")}
            if spoken:_last_metrics["speech_text"]=spoken
            yield answer
            if _cancelled.is_set():
                raise CancelledError("Đã dừng.")
            _remember_turn(question, answer, plan.skill, remember,_context=prepared.state)
            return
        body = {"model": MODEL, "messages": messages, "stream": True, "think": False,
                "keep_alive": settings["keep_alive"], "options": {
                    "num_ctx": settings["num_ctx"], "num_predict": limit,
                    "num_thread": settings["num_thread"], "num_batch": 64,
                    "temperature": 0.2, "top_p": 0.8, "top_k": 20,
                    "presence_penalty": 0.0}}
        _stats["model_calls"] += 1
        response = _local_request("/api/chat", body, timeout=120)
        with _state_lock:
            _active = response
        for line in response:
            if _cancelled.is_set():
                raise CancelledError("Đã dừng.")
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("error"):
                raise RuntimeError(event["error"])
            token = event.get("message", {}).get("content", "")
            if token:
                if first is None:
                    first = time.monotonic() - started
                chunks.append(token)
                if not bilingual:yield token
            if event.get("done"):
                final = event
                break
        if _cancelled.is_set():
            raise CancelledError("Đã dừng.")
        if final is None:
            raise RuntimeError("Kết nối model kết thúc trước khi trả lời hoàn tất.")
        answer = "".join(chunks).strip()
        if not answer:
            raise RuntimeError("Model trả lời trống.")
        raw_answer=answer;spoken=None
        if bilingual:
            answer,spoken=speech.split(answer)
            if not answer:raise RuntimeError("Chưa tạo được phụ đề tiếng Việt.")
        seconds = final.get("eval_duration", 0) / 1e9
        _last_metrics = {"first_token_s": round(first or 0, 3),
                         "elapsed_s": round(time.monotonic() - started, 3),
                         "output_tokens": final.get("eval_count", 0),
                         "tokens_per_s": round(final.get("eval_count", 0) / seconds, 2) if seconds else 0,
                         "done_reason": final.get("done_reason", ""),
                         "route": "model", "skill": plan.skill, "verified": False, "model_calls": 1,
                         "prefix_reused": final.get("prefix_reused", False),
                         "prompt_bytes": sum(len(item["content"].encode("utf-8")) for item in messages),
                         "judgment": judgment.assess("model")}
        if spoken:_last_metrics["speech_text"]=spoken
        if bilingual:yield answer
        if cache_key and len(answer) <= 4000:
            _answer_cache[cache_key] = (time.monotonic(), raw_answer)
            _answer_cache.move_to_end(cache_key)
            while len(_answer_cache) > 32:
                _answer_cache.popitem(last=False)
        _remember_turn(question, answer, plan.skill, remember,_context=prepared.state)
    except RuntimeError:
        if _cancelled.is_set():
            raise CancelledError("Đã dừng.") from None
        raise
    except (OSError, ValueError):
        if _cancelled.is_set():
            raise CancelledError("Đã dừng.") from None
        raise
    finally:
        if response is not None:
            response.close()
        with _state_lock:
            _active = None
        _request_result.value = {"metrics": copy.deepcopy(_last_metrics), "sources": copy.deepcopy(_last_sources)}
        _inference_lock.release()


def ask(prompt, system=None, max_tokens=384):
    # Compatibility entrypoint; preserve Altair's system identity.
    return "".join(stream_chat(prompt, history=[], remember=False, max_tokens=max_tokens))
