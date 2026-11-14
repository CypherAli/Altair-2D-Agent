"""Bounded everyday calculations; every amount must have an identified role."""
import calendar
import re
from datetime import date as _date, datetime, timedelta
from fractions import Fraction
from .toolkit import Result, normalize, number, show, durations, _SCALE

_N = r'\d+(?:[.,]\d+)*'
_COUNTS = {'mot': 1, 'hai': 2, 'ba': 3, 'bon': 4, 'nam': 5, 'sau': 6, 'bay': 7, 'tam': 8, 'chin': 9, 'muoi': 10}
# Vietnamese writes prices in thousands far more often than in đồng.
_MONEY = {'nghin': 1000, 'ngan': 1000, 'trieu': 10 ** 6, 'tram': 100}
_MONEY_U = r'dong|vnd|nghin|ngan|trieu|tram'
_WEEKDAYS = ('thứ Hai', 'thứ Ba', 'thứ Tư', 'thứ Năm', 'thứ Sáu', 'thứ Bảy', 'Chủ nhật')
_SPAN = {'ngay': 'ngày', 'tuan': 'tuần', 'thang': 'tháng'}


def _money(raw, unit):
    return number(raw) * _MONEY.get(unit, 1)


def _round(value, digits=2):
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    rounded = round(float(value), digits)
    text = f"{rounded:.{digits}f}".rstrip('0').rstrip('.')
    return text.replace('.', ',')


def _vnd(value):
    value = Fraction(value)
    if value.denominator == 1:
        return f"{int(value):,}".replace(",", ".") + " đồng"
    return show(value) + " đồng"


def _amount_pattern():
    return '(' + _N + r')\s*(' + _MONEY_U + r')\b'


def shopping(question):
    text = normalize(question)
    if not ('mua' in text and re.search(r'tong|het bao nhieu|thoi|tien thua|tra lai|con lai', text)):
        return None
    if re.search(r'%|giam|phi|phu thu|tang|khuyen mai|\bneu\b|chia', text):
        return None
    money = list(re.finditer(_amount_pattern(), text))
    if not 1 <= len(money) <= 8:
        return None
    paid = None
    items = []
    masked = text
    for match in money:
        before = text[:match.start()]
        # "đưa 100000" and "tôi có 200 nghìn" both mean money in hand.
        if re.search(r'(?:dua|tra|thanh toan|tra bang|\bco)\s*$', before):
            if paid is not None:
                return None
            paid = _money(match[1], match[2])
            masked = masked[:match.start()] + ' ' * (match.end() - match.start()) + masked[match.end():]
            continue
        clause = re.split(r'\bva\b|[.;]', masked[:match.start()])[-1]
        counts = list(re.finditer(r'\b(' + _N + '|' + '|'.join(_COUNTS) + r')\b', clause))
        if len(counts) != 1:
            return None
        token = counts[0][1]
        count = Fraction(_COUNTS[token]) if token in _COUNTS else number(token)
        price = _money(match[1], match[2])
        if count.denominator != 1 or not 0 < count <= 10000 or not 0 <= price <= 10 ** 12:
            return None
        items.append((count, price))
    if not items:
        return None
    total = sum((count * price for count, price in items), Fraction())
    change = bool(re.search(r'thoi|tien thua|tra lai|con lai', text))
    if change and paid is None:
        return Result('Chủ nhân đã đưa bao nhiêu tiền để em tính tiền thừa?', 'everyday-math', {'needs_clarification': True})
    result = paid - total if change else total
    if change:
        answer = (f'Còn lại: **{_vnd(result)}**.' if result >= 0 else f'Còn thiếu **{_vnd(-result)}**.')
    else:
        answer = f'Tổng: **{_vnd(total)}**.'
    return Result(answer, 'everyday-math', {'result': str(result), 'total': str(total),
                                           'paid': str(paid) if paid is not None else None,
                                           'items': [{'quantity': str(count), 'unit_price': str(price)} for count, price in items]})


def discount(question):
    text = normalize(question)
    if re.search(r'/\s*h\b|km/h|chia|moi nguoi|moi chieu|\bthue\b', text):
        return None
    change = re.search(r'\b(giam|bot|tang|them)\s*(' + _N + r')\s*%', text)
    if not change:
        part = re.search(r'(' + _N + r')\s*%\s*(?:cua|tren)\s*(' + _N + r')\s*(?:' + _MONEY_U + r')\b', text)
        if not part:
            return None
        whole = re.search('(' + _N + r')\s*(' + _MONEY_U + r')\b', text)
        if not whole:
            return None
        base = _money(whole[1], whole[2])
        amount = base * number(part[1]) / 100
        return Result(f"{part[1]}% của {_vnd(base)} = **{_vnd(amount)}**.", 'everyday-math',
                      {'base': str(base), 'rate': str(number(part[1])), 'result': str(amount)})
    price = re.search(_amount_pattern(), text)
    if not price:
        return None
    rate = number(change[2])
    if not 0 <= rate <= 100 or (change[1] in ('tang', 'them') and rate > 1000):
        return None
    base = _money(price[1], price[2])
    amount = base * rate / 100
    up = change[1] in ('tang', 'them')
    final = base + amount if up else base - amount
    head = f"Tăng {change[2]}%: **+{_vnd(amount)}**, giá mới **{_vnd(final)}**." if up else \
           f"Giảm {change[2]}%: **-{_vnd(amount)}**, giá còn **{_vnd(final)}**."
    return Result(head, 'everyday-math', {'base': str(base), 'rate': str(rate), 'delta': str(amount),
                                          'result': str(final), 'direction': 'up' if up else 'down'})


def split_bill(question):
    text = normalize(question)
    if not re.search(r'\bchia\b', text):
        return None
    total = re.search(_amount_pattern(), text)
    people = re.search(r'chia\s*(?:deu\s*)?(?:cho\s*)?(\d+)\s*(?:nguoi|phan|ban|suat)', text)
    if not (total and people):
        return None
    count = int(people[1])
    if not 2 <= count <= 100:
        return None
    whole = _money(total[1], total[2])
    each = whole / count
    return Result(f"Chia {_vnd(whole)} cho {count} người: **{_vnd(each)}** mỗi người.", 'everyday-math',
                  {'total': str(whole), 'people': count, 'each': str(each)})


def speed(question):
    text = normalize(question)
    if not re.search(r'toc do|km/h|km moi gio', text):
        return None
    distance = re.search(r'(' + _N + r')\s*km\b', text)
    span = re.search(r'(' + _N + r')\s*(gio|tieng|phut)\b', text)
    if not (distance and span):
        return None
    km = number(distance[1])
    minutes = number(span[1]) * _SCALE[span[2]]
    if minutes <= 0 or km < 0:
        return None
    value = km / (minutes / 60)
    return Result(f"Tốc độ: **{_round(value)} km/h** ({_round(km)} km trong {_round(minutes)} phút).", 'everyday-math',
                  {'speed_kmh': str(value), 'distance_km': str(km), 'minutes': str(minutes)})


def temperature(question):
    text = normalize(question)
    value = re.search(r'(-?\d+(?:[.,]\d+)?)\s*(?:do\s*)?([cf])\b', text)
    target = re.search(r'\b(?:sang|ra|thanh|bang)\s*(?:bao nhieu\s*)?(?:do\s*)?([cf])\b', text)
    if not (value and target) or value[2] == target[1]:
        return None
    amount = number(value[1])
    result = amount * Fraction(9, 5) + 32 if value[2] == 'c' else (amount - 32) * Fraction(5, 9)
    source, unit = ('°C', 'F') if value[2] == 'c' else ('°F', 'C')
    return Result(f"{_round(amount)}{source} = **{_round(result)}°{unit}**.", 'everyday-math',
                  {'result': str(result), 'unit': unit, 'source': value[2]})


def age(question):
    text = normalize(question)
    if 'tuoi' not in text:
        return None
    born = re.search(r'sinh\s*(?:ngay\s*)?(?:(\d{1,2})/(\d{1,2})/)?(?:nam\s*)?(\d{4})', text)
    if not born:
        return None
    year = int(born[3])
    now = datetime.now()
    if not 1900 <= year <= now.year:
        return None
    years = now.year - year
    if born[1]:
        day, month = int(born[1]), int(born[2])
        if not (1 <= day <= 31 and 1 <= month <= 12):
            return None
        years -= (now.month, now.day) < (month, day)
        return Result(f"Sinh ngày {day:02}/{month:02}/{year}: năm nay **{years} tuổi**.", 'everyday-math',
                      {'age': years, 'born': f'{day:02}/{month:02}/{year}'})
    return Result(f"Sinh năm {year}: năm nay **{years} tuổi** nếu đã qua sinh nhật, còn {years - 1} nếu chưa.",
                  'everyday-math', {'age': years, 'born': str(year)})


def _add_months(start, months):
    total = start.month - 1 + months
    year, month = start.year + total // 12, total % 12 + 1
    return _date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def date_offset(question):
    text = normalize(question)
    if not re.search(r'ngay nao|ngay may|thu may|hom nao', text):
        return None
    base = re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{4}))?', text)
    step = re.search(r'(?:(\d+)\s*(tuan|ngay|thang)|(' + '|'.join(_COUNTS) + r')\s*(tuan|ngay|thang))', text)
    if not step:
        return None
    today = datetime.now()
    if base:
        day, month = int(base[1]), int(base[2])
        year = int(base[3]) if base[3] else today.year
        try:
            start = _date(year, month, day)
        except ValueError:
            return None
    else:
        start = _date(today.year, today.month, today.day)
    count = int(step[1]) if step[1] else _COUNTS[step[3]]
    unit = step[2] or step[4]
    backward = bool(re.search(r'\btruoc\b', text))
    if not 0 < count <= 10000:
        return None
    if unit == 'ngay':
        result = start + (-1 if backward else 1) * timedelta(days=count)
    elif unit == 'tuan':
        result = start + (-1 if backward else 1) * timedelta(weeks=count)
    else:
        result = _add_months(start, -count if backward else count)
    direction = 'trước' if backward else 'sau'
    span = f"{count} {_SPAN[unit]}"
    return Result(f"{span} {direction} {start:%d/%m/%Y} là **{result:%d/%m/%Y}** ({_WEEKDAYS[result.weekday()]}).",
                  'everyday-math', {'date': result.isoformat(), 'weekday': _WEEKDAYS[result.weekday()],
                                    'from': start.isoformat(), 'days': count})


def compound_time(question):
    text = normalize(question)
    target = re.search(r'\b(?:sang|ra|thanh|bang|doi\s*(?:sang|ra))\s*(?:bao nhieu\s*)?(gio|tieng|phut|giay)\b', text)
    if not target:
        return None
    groups = durations(text)
    if len(groups) != 1:
        return None
    minutes = groups[0]['minutes']
    if minutes <= 0:
        return None
    unit = target[1]
    value = minutes / _SCALE[unit]
    label = {'gio': 'giờ', 'tieng': 'giờ', 'phut': 'phút', 'giay': 'giây'}[unit]
    head = 'Kết quả: ' if label == 'phút' else f"{show(minutes)} phút = "
    return Result(head + f"**{_round(value)} {label}**.",
                  'everyday-math', {'minutes': str(minutes), 'result': str(value), 'unit': unit})


def clock_plan(question):
    text = normalize(question)
    times = list(re.finditer(r'\b([01]?\d|2[0-3])\s*[:h]\s*([0-5]\d)\b', text))
    if len(times) != 1:
        return None
    if not re.search(r'may gio|luc nao|gio nao|thoi diem', text):
        return None
    if re.search(r'\b(?:neu|hoac|moi|song song|cung luc)\b', text):
        return None
    base = times[0]
    remaining = text[:base.start()] + ' ' + text[base.end():]
    spans = durations(remaining)
    if not 1 <= len(spans) <= 6:
        return None
    offset = sum((item['minutes'] for item in spans), Fraction())
    if offset.denominator != 1 or offset > 1440:
        return None
    backward = bool(re.search(r'muon nhat|cham nhat', text))
    total = int(base[1]) * 60 + int(base[2]) + (-1 if backward else 1) * int(offset)
    day, minute = divmod(total, 1440)
    hour, minute = divmod(minute, 60)
    value = f'{hour:02}:{minute:02}'
    suffix = f' ({"ngày sau" if day > 0 else "ngày trước"})' if day else ''
    return Result(('Muộn nhất rời đi lúc ' if backward else 'Thời điểm kết thúc: ') + value + suffix + '.', 'clock-planning',
                  {'time': value, 'day_offset': day, 'duration_minutes': str(offset),
                   'operation': 'subtract' if backward else 'add'})


def simultaneous(question):
    text = normalize(question)
    if not re.search(r'cung luc|song song|dong thoi', text) or not re.search(r'bao lau|tong.*xong', text):
        return None
    if re.search(r'\b(?:roi|sau|moi lan|moi chieu)\b', text):
        return None
    spans = durations(text)
    if not 2 <= len(spans) <= 6:
        return None
    result = max(item['minutes'] for item in spans)
    return Result(f'Nếu bắt đầu cùng lúc, cả hai/tất cả xong sau **{show(result)} phút**.', 'clock-planning',
                  {'result': str(result), 'operation': 'max_parallel', 'assumption': 'same_start'})
