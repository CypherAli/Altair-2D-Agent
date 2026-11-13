"""Bounded everyday calculations; every amount must have an identified role."""
import re
from fractions import Fraction
from .toolkit import Result,normalize,number,show,durations

_N=r'\d+(?:[.,]\d+)*'
_COUNTS={'mot':1,'hai':2,'ba':3,'bon':4,'nam':5,'sau':6,'bay':7,'tam':8,'chin':9,'muoi':10}

def shopping(question):
    text=normalize(question)
    if not ('mua' in text and re.search(r'tong|het bao nhieu|thoi|tien thua|tra lai',text)):return None
    if re.search(r'%|giam|phi|phu thu|tang|khuyen mai|\bneu\b',text):return None
    money=list(re.finditer('('+_N+r')\s*(?:dong|vnd)\b',text))
    if not 1<=len(money)<=8:return None
    paid=None;items=[]
    for match in money:
        before=text[:match.start()]
        if re.search(r'(?:dua|tra|thanh toan|tra bang)\s*$',before):
            if paid is not None:return None
            paid=number(match[1]);continue
        clause=re.split(r'\bva\b|[.;]',before)[-1]
        counts=list(re.finditer(r'\b('+_N+'|'+ '|'.join(_COUNTS)+r')\b',clause))
        if len(counts)!=1:return None
        token=counts[0][1];count=Fraction(_COUNTS[token]) if token in _COUNTS else number(token)
        price=number(match[1])
        if count.denominator!=1 or not 0<count<=10000 or not 0<=price<=10**12:return None
        items.append((count,price))
    if not items:return None
    total=sum((count*price for count,price in items),Fraction())
    change=bool(re.search(r'thoi|tien thua|tra lai',text))
    if change and paid is None:
        return Result('Chủ nhân đã đưa bao nhiêu tiền để em tính tiền thừa?','everyday-math',{'needs_clarification':True})
    result=paid-total if change else total
    answer=(f'Tiền thừa: **{show(result)} đồng**.' if result>=0 else f'Còn thiếu **{show(-result)} đồng**.') if change else f'Tổng: **{show(total)} đồng**.'
    return Result(answer,'everyday-math',{'result':str(result),'total':str(total),'paid':str(paid) if paid is not None else None,
                   'items':[{'quantity':str(count),'unit_price':str(price)} for count,price in items]})

def clock_plan(question):
    text=normalize(question)
    times=list(re.finditer(r'\b([01]?\d|2[0-3])\s*[:h]\s*([0-5]\d)\b',text))
    if len(times)!=1:return None
    if not re.search(r'may gio|luc nao|gio nao|thoi diem',text):return None
    if re.search(r'\b(?:neu|hoac|moi|song song|cung luc)\b',text):return None
    base=times[0];remaining=text[:base.start()]+' '+text[base.end():]
    spans=durations(remaining)
    if not 1<=len(spans)<=6:return None
    offset=sum((item['minutes'] for item in spans),Fraction())
    if offset.denominator!=1 or offset>1440:return None
    backward=bool(re.search(r'muon nhat|cham nhat',text))
    total=int(base[1])*60+int(base[2])+(-1 if backward else 1)*int(offset)
    day,minute=divmod(total,1440);hour,minute=divmod(minute,60)
    value=f'{hour:02}:{minute:02}'
    suffix=f' ({"ngày sau" if day>0 else "ngày trước"})' if day else ''
    return Result(('Muộn nhất rời đi lúc ' if backward else 'Thời điểm kết thúc: ')+value+suffix+'.','clock-planning',
                  {'time':value,'day_offset':day,'duration_minutes':str(offset),'operation':'subtract' if backward else 'add'})

def simultaneous(question):
    text=normalize(question)
    if not re.search(r'cung luc|song song|dong thoi',text) or not re.search(r'bao lau|tong.*xong',text):return None
    if re.search(r'\b(?:roi|sau|moi lan|moi chieu)\b',text):return None
    spans=durations(text)
    if not 2<=len(spans)<=6:return None
    result=max(item['minutes'] for item in spans)
    return Result(f'Nếu bắt đầu cùng lúc, cả hai/tất cả xong sau **{show(result)} phút**.','clock-planning',
                  {'result':str(result),'operation':'max_parallel','assumption':'same_start'})
