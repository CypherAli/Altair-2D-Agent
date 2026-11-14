"""Choose a verified tool first; disclose one bounded skill to the model otherwise."""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import skills
from .toolkit import Result, arithmetic, convert_units, normalize, sudoku, time_plan
from .reasoning import order_reasoning, constraint_choice
from .everyday import (shopping, clock_plan, simultaneous, discount, split_bill,
                       speed, temperature, age, date_offset, compound_time)


@dataclass
class Plan:
    skill: str
    result: Result | None = None
    max_tokens: int = 160
    use_history: bool = False


def uses_history(question):
    text = normalize(question)
    return bool(re.search(r"\b(?:no|vay|tiep|cai nay|cai do|cai tren|nhu tren|them nua|vi sao lai|noi ro hon|rut gon|chi tiet hon|cua toi|so tien do|tien do|ket qua do|thoi gian do|so do|tung ay|luot ve|di va ve|con phuong an|con [a-z])\b", text) or text.startswith("toi "))


def web_followup(question):
    text=normalize(question)
    if re.search(r'\b(?:google|tra cuu|search|tim kiem|tim tren web)\b',text):return False
    return bool(re.search(r'noi ro hon|giai thich them|tong hop|tom tat|cac nguon|nguon nao|nguon nay|nguon do|nguon vua|trang do|cai tren|nhu tren|no la gi',text))


def relevant_notes(question, notes, limit=2):
    stop = {"toi", "minh", "ban", "altair", "thich", "gi", "la", "co", "khong", "cua", "cho", "mot", "cac", "hay", "ve", "nho", "da", "nao", "the"}
    words = set(re.findall(r"[a-z0-9]+", normalize(question))) - stop
    if "uong" in words:
        words.update(("tra", "phe", "nuoc", "sua"))
    ranked = []
    for index, note in enumerate(notes):
        text = str(note.get("text", ""))
        score = len(words & set(re.findall(r"[a-z0-9]+", normalize(text))))
        if score:
            ranked.append((score, index, text))
    return [text for _, _, text in sorted(ranked, reverse=True)[:limit]]


WEEKDAYS = ('thứ Hai', 'thứ Ba', 'thứ Tư', 'thứ Năm', 'thứ Sáu', 'thứ Bảy', 'Chủ nhật')

def clock_question(text):
    """True for "what day/time is it" phrasings, not just two exact sentences."""
    text = re.sub(r"\s+", " ", normalize(text)).strip().rstrip("?!.")
    day = re.search(r"\b(?:hom nay|ngay hom nay|bay gio|hom nay la ngay)\b", text)
    ask_day = re.search(r"\b(?:thu may|thu [2-7]|thu chu nhat|ngay may|ngay bao nhieu|ngay thang|ngay thang nam)\b", text)
    ask_time = re.search(r"\b(?:may gio|gio roi|may gio roi|bao nhieu gio)\b", text)
    if not (ask_day or ask_time):
        return False
    # A day/time question without an explicit subject still reads as "today".
    return bool(day or ask_time or re.search(r"\bthu may roi\b", text))


def plan(question, images=None, notes=(), web=None):
    text = normalize(question).strip().rstrip("?!.")
    text=re.sub(r'^em\b','ban',text)
    if images:
        return Plan("vision", max_tokens=160)
    if text in ("ban ten gi", "ten ban la gi", "ban la ai", "cau la ai", "altair ten gi"):
        return Plan("identity", Result("Em là Altair, trợ lý cá nhân của chủ nhân.", "identity", {"verified": True}))
    if text in ("chao", "xin chao", "hello", "hi", "chao altair", "chao em"):
        return Plan("identity", Result("Chào chủ nhân, Altair đây. Chủ nhân cần em giúp việc gì?", "identity", {"verified": True}))
    if text in ("cam on", "cam on ban", "cam on em", "thanks", "thank you"):
        return Plan("identity", Result("Không có gì nhé.", "identity", {"verified": True}))
    if text in ("ban lam duoc gi", "altair lam duoc gi", "ban co the lam gi"):
        return Plan("identity", Result("Em có thể giúp chủ nhân tìm web kèm nguồn, tính toán, đổi đơn vị, kiểm tra thời gian, giải/gợi ý Sudoku, ghi nhớ, trò chuyện và xem ảnh. Báo thức và điều khiển ứng dụng chưa được kết nối trong bản này.", "identity", {"verified": True}))
    if (re.match(r"^(?:altair[, ]+)?(?:hay )?(?:nhac (?:toi|minh)|dat bao thuc|go game|xoa game|tat game|mo youtube|chuyen video)\b", text)
            or (re.search(r'bao thuc|xoa game|tat game|chuyen video',text) and re.search(r'ban da|chua|cho toi|giup toi|ho toi',text))):
        return Plan("capabilities", Result("Chức năng đó chưa được kết nối trong bản Altair hiện tại, nên em chưa thực hiện thao tác hay đặt lời nhắc.", "capabilities", {"executed": False}))
    if clock_question(text):
        now = datetime.now(timezone(timedelta(hours=7)))
        answer = f"Bây giờ là {now:%H:%M}, ngày {now:%d/%m/%Y} (giờ Việt Nam)."
        if 'thu may' in text:
            answer=f'Hôm nay là {WEEKDAYS[now.weekday()]}, ngày {now:%d/%m/%Y} (giờ Việt Nam).'
        return Plan("clock", Result(answer, "clock", {"timezone": "+07:00"}))
    if text in ("ban nho gi ve toi", "toi da dan gi", "liet ke ghi nho", "xem ghi nho"):
        texts = [str(note.get("text", "")) for note in notes[-5:]]
        answer = "Các ghi nhớ chủ nhân đã lưu:\n" + "\n".join("• " + value for value in texts) if texts else "Chủ nhân chưa lưu ghi nhớ cá nhân nào."
        return Plan("memory", Result(answer, "memory", {"count": len(texts)}))
    if text.startswith(("hay nho rang ", "nho rang ", "ghi nho: ")):
        # Keep the original spelling; runtime commits this explicit user request.
        original = re.sub(r"^(?:hãy\s+)?(?:nhớ\s+rằng\s+|ghi\s+nhớ:\s*)", "", question.strip(), flags=re.I)
        if original != question.strip():
            return Plan("memory", Result("Đã lưu ghi nhớ: " + original, "memory", {"save_note": original}))
    for tool in (sudoku, convert_units, arithmetic, discount, split_bill, speed, temperature,
                 age, date_offset, compound_time, shopping, clock_plan, simultaneous,
                 order_reasoning, constraint_choice, time_plan):
        result = tool(question)
        if result is not None:
            return Plan(result.skill, result)
    if re.search(r'neu .*thi |chi .*neu |tat ca .*deu|co suy ra|du co so ket luan|co the ket luan|theo gia dinh',text):
        return Plan('logic',max_tokens=96,use_history=uses_history(question))
    from .search import requested
    if requested(question, web):
        return Plan("web-search", max_tokens=128, use_history=uses_history(question))
    detailed = any(term in text for term in ("chi tiet", "phan tich ky", "tung buoc", "giai thich dai"))
    skill = skills.select(question)
    limit = 320 if detailed else 160 if skill == "decision" else 128
    if not detailed and "ngan" in text:
        limit = 96
    return Plan(skill, max_tokens=limit, use_history=uses_history(question))


SYSTEM = "Bạn là Altair, trợ lý cá nhân của Trinh. Luôn xưng em, gọi người dùng là chủ nhân. Phong thái điềm tĩnh, tự tin, quan tâm. Trả lời tiếng Việt ngắn gọn, đúng câu hỏi. Không bịa dữ kiện hay việc đã làm. Thiếu điều kiện cần thiết thì hỏi rõ."


def system_prompt(skill):
    body = skills.instructions(skill)
    return SYSTEM + ("\n<skill name=\"" + skill + "\">\n" + body + "\n</skill>" if body else "")
