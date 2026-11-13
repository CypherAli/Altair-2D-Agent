"""Bounded working context from user turns, never from retrieved web content.

No model calls, embedding database, network, or executable skills. Changes are
prepared on a copy and committed by runtime only after a completed response.
"""
from __future__ import annotations
import copy
import json
import re
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from fractions import Fraction
from .toolkit import normalize,number,show,Result
from .reasoning import constraint_choice

MAX_TOPICS=4
MAX_BYTES=12_000
MAX_PROMPT_BYTES=1100
_NUM=r'\d+(?:[.,]\d+)*'
_MONEY=re.compile(r'('+_NUM+r')\s*(dong|vnd|k|tr|trieu)\b',re.I)
_DURATION=re.compile(r'('+_NUM+r')\s*(phut|p|gio|tieng)\b',re.I)
_LABEL=re.compile(r'\b(?:phuong an|quan|goi|cai|option)?\s*([a-f])\s*(?=gia\b|can\b|mat\b|ton\b|phi\b|ship\b|\d)',re.I)

def empty():return {'version':1,'turn':0,'active':None,'frames':[],'pending':None,'initialized':True}

def bounded(state):
    if not isinstance(state,dict) or state.get('version')!=1:return empty()
    out=empty();out['turn']=state.get('turn',0) if isinstance(state.get('turn',0),int) else 0
    rows=state.get('frames',[])
    for row in rows[-12:] if isinstance(rows,list) else []:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str):continue
        turn=row.get('updated',0) if isinstance(row.get('updated',0),int) else 0
        frame=frame_new(row['id'][:90],str(row.get('title','chủ đề'))[:90],turn)
        frame['goal']=str(row.get('goal',frame['title']))[:140]
        slots=row.get('slots',{})
        if isinstance(slots,dict):
            for key,value in slots.items():
                if key in ('budget','minutes'):
                    try:
                        if 0<=number(str(value))<=10**12:frame['slots'][key]=str(value)[:24]
                    except (ValueError,ZeroDivisionError):pass
                elif key in ('date','place'):frame['slots'][key]=str(value)[:90]
        options=row.get('options',{})
        if isinstance(options,dict):
            for label,values in options.items():
                if label not in 'ABCDEF' or len(label)!=1 or not isinstance(values,dict):continue
                frame['options'][label]={}
                for key,value in values.items():
                    if key=='excluded':frame['options'][label][key]=bool(value)
                    elif key in ('cost','fee','travel','minutes'):
                        try:
                            if 0<=number(str(value))<=10**12:frame['options'][label][key]=str(value)[:24]
                        except (ValueError,ZeroDivisionError):pass
        facts=row.get('facts',[])
        frame['facts']=[str(value)[:220] for value in facts[-3:]] if isinstance(facts,list) else []
        for key in ('include_fee','include_travel'):frame[key]=bool(row.get(key,False))
        frame['focus']=row.get('focus') if isinstance(row.get('focus'),str) and row.get('focus') in frame['options'] else None
        last=row.get('last_slot')
        if isinstance(last,dict) and last.get('key') in ('budget','minutes','cost','fee','travel','preference'):
            frame['last_slot']={key:last[key] for key in ('key','turn','option') if key in last}
            if 'option' in frame['last_slot'] and frame['last_slot']['option'] not in tuple('ABCDEF'):frame['last_slot']=None
        if isinstance(row.get('public_query'),str):frame['public_query']=row['public_query'][:200]
        frame['last_updated_fields']=[str(v)[:30] for v in row.get('last_updated_fields',[])[:8]] if isinstance(row.get('last_updated_fields',[]),list) else []
        out['frames'].append(frame)
    out['frames']=sorted(out['frames'],key=lambda f:f['updated'])[-MAX_TOPICS:]
    out['active']=state.get('active') if any(f['id']==state.get('active') for f in out['frames']) else None
    pending=state.get('pending')
    if isinstance(pending,dict) and pending.get('kind')=='money_slot':
        try:
            if 0<=number(str(pending.get('value')))<=10**12:out['pending']={'kind':'money_slot','value':str(pending['value'])[:24],'topic':pending.get('topic')}
        except (ValueError,ZeroDivisionError):pass
    while len(json.dumps(out,ensure_ascii=False).encode())>MAX_BYTES and len(out['frames'])>1:
        drop=next((f for f in out['frames'] if f['id']!=out['active']),out['frames'][0]);out['frames'].remove(drop)
    return out

def active(state):return next((f for f in state.get('frames',[]) if f['id']==state.get('active')),None)

def abbreviations(text):
    # Word boundaries protect prices (100k), labels (B), and display sizes (1080p).
    aliases={'ko':'không','khong':'không','khum':'không','đc':'được','dc':'được','cx':'cũng','vs':'với','mik':'mình'}
    text=re.sub(r'\b(?:ko|khong|khum|đc|dc|cx|vs|mik)\b',lambda m:aliases[m[0].lower()],text,flags=re.I)
    text=re.sub(r'^t\s+(?=(?:có|muốn|cần|định|thích)\b)','tôi ',text,flags=re.I)
    return text

def money(match):
    value=number(match[1]);unit=match[2].lower()
    return value*({'k':1000,'tr':1000000,'trieu':1000000}.get(unit,1))

def minutes(match):return number(match[1])*(60 if match[2].lower() in ('gio','tieng') else 1)

def positive_clause(text):
    # Explicit replacement, preserving which side is negated.
    value=re.sub(r'^(?:khong[, ]+)?(?:a,\s*|y toi la\s+|y minh la\s+|nham[, ]*)','',text)
    if re.search(r'khong phai .+?\b(?:ma|la)\b',value):value=re.split(r'khong phai .+?\b(?:ma|la)\b',value,maxsplit=1)[-1]
    elif 'khong phai' in value:value=value.split('khong phai',1)[0]
    return value.strip()

def subject(question):
    text=normalize(question)
    for key,patterns,title in (
        ('dinner',('an toi','di an','quan an','an pho','sushi'),'ăn tối'),
        ('lunch',('an trua',),'ăn trưa'),
        ('phone',('mua dien thoai','chon dien thoai'),'mua điện thoại'),
        ('laptop',('mua laptop','chon laptop','mua may tinh'),'mua laptop'),
        ('headphones',('mua tai nghe','chon tai nghe'),'mua tai nghe'),
        ('trip',('di choi','di cong vien','di thu vien','chuyen di'),'đi chơi'),
        ('bill',('hoa don','chia tien','tien an'),'hóa đơn'),
        ('schedule',('lich hen','gio hen','hen gap'),'lịch hẹn')):
        if any(re.search(r'\b'+re.escape(p)+r'\b',text) for p in patterns):return key,title
    if re.search(r'^(?:toi|minh) thich\b',text):return 'personal','sở thích'
    if re.search(r'^(?:toi|minh) (?:dang|bi|song|hoc|lam)\b',text):return 'personal-context','bối cảnh cá nhân'
    return None

def frame_new(key,title,turn):
    return {'id':key,'title':title[:90],'goal':title[:140],'slots':{},'options':{},'facts':[],'focus':None,'last_slot':None,'updated':turn,'include_fee':False,'include_travel':False}

def slot_put(frame,key,value,turn):
    frame['slots'][key]=str(value);frame['last_slot']={'key':key,'turn':turn}

def option_put(frame,label,key,value,turn):
    frame['options'].setdefault(label,{})[key]=str(value)
    frame['focus']=label;frame['last_slot']={'option':label,'key':key,'turn':turn}

def summary(state):
    frame=active(state)
    if not frame:return ''
    fields={'topic':frame['title'],'goal':frame['goal'],'current_values':dict(frame['slots']),
            'options':frame['options'],'focus':frame.get('focus'),'user_constraints':frame['facts'],
            'include_delivery_fee':frame['include_fee']}
    fields['include_travel']=frame.get('include_travel',False)
    while len(json.dumps(fields,ensure_ascii=False).encode())>MAX_PROMPT_BYTES and fields['user_constraints']:
        fields['user_constraints']=fields['user_constraints'][1:];fields['omitted_details']=True
    while len(json.dumps(fields,ensure_ascii=False).encode())>MAX_PROMPT_BYTES and fields['options']:
        fields['options']=dict(list(fields['options'].items())[:-1]);fields['omitted_details']=True
    if len(json.dumps(fields,ensure_ascii=False).encode())>MAX_PROMPT_BYTES:fields.pop('goal',None);fields['omitted_details']=True
    if len(json.dumps(fields,ensure_ascii=False).encode())>MAX_PROMPT_BYTES:fields['current_values'].pop('place',None);fields['omitted_details']=True
    return json.dumps(fields,ensure_ascii=False,separators=(',',':'))

def describe(frame):
    parts=[f"Đang bàn: {frame['title']}."]
    slots=frame['slots']
    if 'budget' in slots:parts.append(f"Ngân sách: {show(number(slots['budget']))} đồng.")
    if 'minutes' in slots:parts.append(f"Thời gian tối đa: {show(number(slots['minutes']))} phút.")
    if 'date' in slots:parts.append('Ngày dự định: '+slots['date']+'.')
    if 'place' in slots:parts.append('Địa điểm: '+slots['place']+'.')
    if frame['options']:
        details=[]
        for label,option in frame['options'].items():
            values=[]
            for key,unit in (('cost','đồng'),('fee','đồng ship'),('travel','đồng đi về'),('minutes','phút')):
                if key in option:values.append(show(number(option[key]))+' '+unit)
            details.append(label+': '+(', '.join(values) or 'chưa đủ dữ kiện')+(' (đã loại)' if option.get('excluded') else ''))
        parts.append('Phương án: '+'; '.join(details)+'.')
    if frame['facts']:parts.append('Điều chủ nhân đã nói: '+'; '.join(frame['facts'])+'.')
    return ' '.join(parts)

@dataclass
class Prepared:
    state:dict
    question:str
    result:Result|None=None
    correction:bool=False
    relevant:bool=False
    search_query:str|None=None
    reset_history:bool=False

def _result(prepared,text,**facts):
    prepared.result=Result(text,'conversation-context',{'context_only':True,**facts});prepared.relevant=True
    return prepared

def _prepare(question,state=None,today=None):
    state=bounded(state or empty());state['turn']+=1;turn=state['turn']
    cleaned=abbreviations(question.strip());text=normalize(cleaned)
    prepared=Prepared(state,cleaned)
    today=today or datetime.now(timezone(timedelta(hours=7))).date()
    if re.fullmatch(r'(?:hay )?(?:quen|xoa|bo) (?:het )?(?:boi canh|ngu canh)(?: phien nay)?[.!?]*',text):
        prepared.state=empty();prepared.reset_history=True
        return _result(prepared,'Đã xóa bối cảnh hội thoại của phiên này. Ghi nhớ chủ nhân đã lưu riêng vẫn giữ nguyên.',cleared=True)

    # Resume only a topic with one clear match; never invent a missing older topic.
    resume=re.search(r'quay lai|tro lai|tiep tuc chuyen',text)
    if resume:
        candidates=[f for f in state['frames'] if any(word in text for word in (normalize(f['title']),f['id']))]
        if len(candidates)!=1:
            return _result(prepared,'Chủ nhân muốn quay lại chủ đề nào? Em đang giữ: '+(', '.join(f['title'] for f in state['frames']) or 'chưa có chủ đề trước đó')+'.',needs_clarification=True)
        state['active']=candidates[0]['id'];frame=candidates[0];frame['updated']=turn
        return _result(prepared,'Đã quay lại. '+describe(frame),resumed=frame['id'])

    from .search import requested,query_text
    explicit_web=bool(re.search(r'\bgoogle\b|tra cuu|search|tim kiem',text))
    if explicit_web:
        query=query_text(cleaned);key='web:'+normalize(query)[:70]
        frame=next((f for f in state['frames'] if f['id']==key),None)
        if frame is None:frame=frame_new(key,query[:90],turn);state['frames'].append(frame)
        frame['public_query']=query;frame['updated']=turn;state['active']=key
        prepared.state=bounded(state);prepared.relevant=False
        return prepared

    frame=active(state);topic=subject(cleaned);new_topic=False
    correction=bool(re.search(r'khong phai|^(?:a[, ]+)?(?:y toi|y minh|nham|sua|doi|thay)\b|khong[, ]+.*(?:co|thoi)|\b(?:ma|co)\s*$|^(?:chi con|con|len|xuong)\s+\d',text))
    prepared.correction=correction
    if topic and (frame is None or topic[0]!=frame['id']):
        existing=next((f for f in state['frames'] if f['id']==topic[0]),None)
        if existing is None:existing=frame_new(*topic,turn);state['frames'].append(existing)
        frame=existing;state['active']=frame['id'];new_topic=True
    tied=bool(re.search(r'cai do|cai nay|\bno\b|phuong an|lua chon|mon do|viec do|vua noi|vua chon|gioi han|ngan sach|chon\s+[a-f]\b',text))
    if not topic and re.search(r'doi chu de|hoi chuyen khac|nhan tien',text) or (not topic and not tied and re.search(r'^(?:giai thich|tai sao|vi sao)\b',text)):
        key='general:'+text[:60];frame=frame_new(key,cleaned[:90],turn)
        state['frames'].append(frame);state['active']=key;prepared.relevant=False
        return prepared
    if frame and frame.get('public_query'):
        from .harness import web_followup
        if web_followup(cleaned):prepared.search_query=frame['public_query'];prepared.relevant=True;return prepared
        if not topic and re.search(r'^(?:toi|minh) (?:muon|can|dinh|thich)|doi chu de|nhan tien',text):
            frame=None
    has_data=bool(re.search(r'ngan sach|gioi han|toi da|\bco\s+\d|\b[a-f]\s+(?:gia|\d)|\bquan\s+[a-f]',text))
    if frame is None and (has_data or topic):
        key,title=topic or ('planning','kế hoạch hiện tại');frame=frame_new(key,title,turn)
        state['frames'].append(frame);state['active']=key
    if frame is None:
        if re.search(r'cai do|cai kia|phuong an do|sua thanh|doi thanh|\bno\b',text):
            return _result(prepared,'Chủ nhân đang nhắc tới điều/phương án nào? Em chưa có đủ bối cảnh để xác định.',needs_clarification=True)
        return prepared

    frame['updated']=turn;prepared.relevant=True
    value_text=positive_clause(text) if correction else text
    updated=[]
    pending=state.get('pending')
    if pending and pending.get('topic')!=frame['id']:state['pending']=None;pending=None
    if pending and pending.get('kind')=='money_slot':
        if 'ngan sach' in text:slot_put(frame,'budget',pending['value'],turn);updated.append('budget');state['pending']=None
        else:
            label=re.search(r'(?:gia|phuong an|quan)\s+([a-f])\b',text)
            if label:option_put(frame,label[1].upper(),'cost',pending['value'],turn);updated.append('cost');state['pending']=None

    # Capture option clauses before generic budgets, keeping fees distinct from prices.
    labels=[match for match in _LABEL.finditer(value_text) if not re.search(r'(?:gia|ship|phi giao|di ve|di lai)\s+$',value_text[:match.start(1)])];option_spans=[]
    for index,match in enumerate(labels):
        label=match[1].upper();end=labels[index+1].start() if index+1<len(labels) else len(value_text)
        clause=value_text[match.end():end];option_spans.append((match.start(),end))
        money_values=list(_MONEY.finditer(clause))
        for amount in money_values:
            before=clause[max(0,amount.start()-35):amount.start()]
            kind='fee' if re.search(r'(?:ship|phi giao|phi giao hang)\s*(?:la|them|=)?\s*$',before) else 'cost'
            amount_value=money(amount)
            if 0<=amount_value<=10**12:option_put(frame,label,kind,amount_value,turn);updated.append(label+'.'+kind)
        for amount in _DURATION.finditer(clause):
            value=minutes(amount)
            if 0<=value<=10080:option_put(frame,label,'minutes',value,turn);updated.append(label+'.minutes')
        if re.search(r'mien phi (?:giao|ship)|khong (?:mat|ton) phi ship',clause):
            option_put(frame,label,'fee',0,turn);updated.append(label+'.fee')
    if len(labels)>1:frame['focus']=None
    # Also accept a named attribute before a label: "giá B 80k", "ship B 10k".
    for match in re.finditer(r'\b(gia|ship|phi giao|di ve|di lai)\s+([a-f])\s*(?:la|=|thanh)?\s*('+_NUM+r')\s*(dong|vnd|k|tr|trieu)\b',value_text):
        amount=number(match[3])*({'k':1000,'tr':1000000,'trieu':1000000}.get(match[4],1))
        kind='travel' if match[1] in ('di ve','di lai') else 'cost' if match[1]=='gia' else 'fee'
        if 0<=amount<=10**12:option_put(frame,match[2].upper(),kind,amount,turn);updated.append('option')
    outside=''.join(' ' if any(start<=i<end for start,end in option_spans) else ch for i,ch in enumerate(value_text))
    for amount in _MONEY.finditer(outside):
        before=outside[max(0,amount.start()-45):amount.start()]
        if re.search(r'(?:ngan sach|gioi han|toi da|(?:toi|minh|t) co|tien toi co)\s*(?:la|=|thanh|len|con)?\s*$',before):
            value=money(amount)
            if 0<=value<=10**12:slot_put(frame,'budget',value,turn);updated.append('budget')
    for amount in _DURATION.finditer(outside):
        before=outside[max(0,amount.start()-40):amount.start()]
        if re.search(r'(?:gioi han|toi da|(?:toi|minh|t) co|thoi gian|ranh)\s*(?:la|=|thanh|len|con)?\s*$',before):
            value=minutes(amount)
            if 0<=value<=10080:slot_put(frame,'minutes',value,turn);updated.append('minutes')

    if re.search(r'tinh ca (?:ship|phi giao)|kem (?:ship|phi giao)',text):frame['include_fee']=True;updated.append('include_fee')
    if re.search(r'tinh ca (?:tien |chi phi )?(?:di ve|di lai)',text):frame['include_travel']=True;updated.append('include_travel')
    if re.search(r'bo (?:tien )?(?:di ve|di lai)|dung tinh (?:tien )?(?:di ve|di lai)',text):frame['include_travel']=False;updated.append('include_travel')
    if re.search(r'ca (?:hai|tat ca).*mien phi (?:ship|giao)',text):
        for label in frame['options']:option_put(frame,label,'fee',0,turn)
        updated.append('all_fees')
    if re.search(r'bo (?:phi )?ship|dung tinh (?:ship|phi giao)|khong tinh (?:ship|phi giao)',text):frame['include_fee']=False;updated.append('include_fee')
    exclusions=re.search(r'(?:loai|bo|dung chon) (?:phuong an |quan )?([a-f])\b',text)
    if exclusions:
        frame['options'].setdefault(exclusions[1].upper(),{})['excluded']=True;updated.append('excluded')
    restore=re.search(r'cho (?:phuong an |quan )?([a-f]) vao lai',text)
    if restore:frame['options'].setdefault(restore[1].upper(),{}).pop('excluded',None);updated.append('restored')

    # A bare revised amount can target the immediately confirmed field, otherwise ask.
    bare=list(_MONEY.finditer(value_text))
    if correction and len(bare)==1 and not updated:
        value=money(bare[0]);last=frame.get('last_slot')
        negated=re.search(r'khong phai\s+('+_NUM+r')\s*(dong|vnd|k|tr|trieu)\b',text)
        references=[]
        if negated:
            old=money(negated)
            if 'budget' in frame['slots'] and number(frame['slots']['budget'])==old:references.append(('budget',None))
            for label,option in frame['options'].items():
                for key in ('cost','fee','travel'):
                    if key in option and number(option[key])==old:references.append((key,label))
        if len(references)==1:
            key,label=references[0]
            if label:option_put(frame,label,key,value,turn)
            else:slot_put(frame,key,value,turn)
            updated.append('explicit_replacement')
        elif references:
            state['pending']={'kind':'money_slot','value':str(value),'topic':frame['id']}
            return _result(prepared,'Số cũ xuất hiện ở nhiều chỗ. Chủ nhân muốn sửa ngân sách hay giá/phí của phương án nào?',needs_clarification=True)
        elif last and last.get('turn')==turn-1 and last.get('key') in ('budget','cost','fee','travel'):
            if last.get('option'):option_put(frame,last['option'],last['key'],value,turn)
            elif last['key']=='budget':slot_put(frame,'budget',value,turn)
            updated.append('revision')
        elif 'budget' in frame['slots'] and not frame['options']:
            slot_put(frame,'budget',value,turn);updated.append('budget')
        else:
            state['pending']={'kind':'money_slot','value':str(value),'topic':frame['id']}
            return _result(prepared,f'Chủ nhân muốn đổi ngân sách hay giá của phương án nào thành {show(value)} đồng?',needs_clarification=True)

    bare_time=list(_DURATION.finditer(value_text))
    if correction and len(bare_time)==1 and not updated:
        value=minutes(bare_time[0]);last=frame.get('last_slot')
        if last and last.get('key')=='minutes' and last.get('turn')==turn-1 and 0<=value<=10080:
            if last.get('option'):option_put(frame,last['option'],'minutes',value,turn)
            else:slot_put(frame,'minutes',value,turn)
            updated.append('time_revision')
        else:return _result(prepared,'Chủ nhân muốn sửa thời gian tối đa hay thời gian của phương án nào? Hãy nêu rõ để em không đổi nhầm.',needs_clarification=True)

    date_match=re.search(r'ngay kia|ngay mai|\bmai\b|hom nay',value_text)
    if date_match:
        offset=2 if date_match[0]=='ngay kia' else 0 if date_match[0]=='hom nay' else 1
        slot_put(frame,'date',(today+timedelta(days=offset)).isoformat(),turn);updated.append('date')
    place=re.search(r'(?:o|tai|chuyen sang)\s+(quan\s+\d+|thu duc|ha noi|da nang|ho chi minh)\b',value_text)
    if place:slot_put(frame,'place',place[1],turn);updated.append('place')
    if correction and re.search(r'khong (?:an|uong|mua).*(?:nua|ma)',text):
        frame['facts']=[]
    # Non-numeric user constraints only; older numeric values live solely in slots.
    if re.search(r'khong an|di ung|thich|uu tien|muon an|chuyen sang an',value_text) and not re.search(r'\d|bao gio|bao nhieu|gi\b|nao\b',value_text) and '?' not in cleaned:
        if correction:frame['facts']=[]
        frame['facts']=(frame['facts']+[cleaned[-220:]])[-3:];updated.append('preference')
        frame['last_slot']={'key':'preference','turn':turn}
    elif correction and not updated and frame['facts'] and (frame.get('last_slot') or {}).get('key')=='preference' and '?' not in cleaned and not re.search(r'goi y|giai thich|vi sao|tai sao',text):
        payload=re.sub(r'^(?:a[, ]+)?khong[, ]+','',value_text)
        payload=re.sub(r'\s+(?:co|thoi)[.!?]*$','',payload).strip()
        previous=normalize(frame['facts'][-1]);anchor=re.match(r'(.+?\b(?:mau|uong|an)\b)',previous)
        if anchor and len(payload)<=80 and not re.search(r'\d',payload):
            frame['facts']=[anchor[1]+' '+payload];updated.append('preference_revision')
            frame['last_slot']={'key':'preference','turn':turn}
    # Keep a few user-supplied contextual statements for open reasoning too.
    # These are unverified text, never inputs to deterministic arithmetic.
    if not updated and not correction and '?' not in cleaned and not re.search(r'\bchon\b|tom tat|bao nhieu|cai do|\bno\b|quay lai|ngan sach.*nao',text):
        if re.search(r'^(?:toi|minh) (?:dang|bi|song|hoc|lam|can|muon)|^quan .+\d|^nha toi|^con toi',text):
            frame['facts']=(frame['facts']+[cleaned[:220]])[-3:]
            updated.append('user_statement')
    frame['last_updated_fields']=updated[-8:]
    prepared.state=state

    if re.search(r'tom tat boi canh|dang ban chuyen gi|nho boi canh gi|gio ban hieu gi',text):return _result(prepared,describe(frame),recalled=True)
    if re.search(r'ngan sach.*bao nhieu',text) and 'budget' in frame['slots']:
        return _result(prepared,'Ngân sách hiện tại: '+show(number(frame['slots']['budget']))+' đồng.',recalled=True)
    focus=re.search(r'(?:con |cai |quan |phuong an |gia |ship )([a-f])\b',text) if not updated else None
    if re.fullmatch(r'[a-f][.!?]*',text):focus=re.match(r'([a-f])',text)
    if focus:frame['focus']=focus[1].upper()
    vague=bool(re.search(r'cai do|cai kia|phuong an do|\bno\b',text))
    if vague and not frame.get('focus'):
        return _result(prepared,'Chủ nhân đang nói tới phương án nào'+(' ('+', '.join(frame['options'])+')' if frame['options'] else '')+'?',needs_clarification=True)
    detail_request=not re.search(r'goi y|giai thich|vi sao|tai sao|nen lam gi|tu van',text)
    if (focus or vague) and not updated and detail_request:
        label=frame.get('focus');option=frame['options'].get(label)
        if option:
            parts=[f'Phương án {label}:']
            for key,unit in (('cost','đồng'),('fee','đồng phí giao'),('minutes','phút')):
                if key in option:parts.append(show(number(option[key]))+' '+unit)
            if 'cost' in option and (frame['include_fee'] or frame.get('include_travel')):
                needed=['cost']+(['fee'] if frame['include_fee'] else [])+(['travel'] if frame.get('include_travel') else [])
                if all(key in option for key in needed):parts.append('Tổng: '+show(sum(number(option[key]) for key in needed))+' đồng')
                else:parts.append('Chưa đủ phí để tính tổng')
            return _result(prepared,' '.join(parts)+'.',focus=label)
        if focus:return _result(prepared,'Em chưa có dữ kiện của phương án '+label+'. Chủ nhân cho biết giá/thời gian nhé.',needs_clarification=True)
    choose=bool(re.search(r'\bchon\b|phuong an nao|quan nao|vua tui|re nhat|nhanh nhat',text))
    if choose and frame['options']:
        candidates={k:v for k,v in frame['options'].items() if not v.get('excluded')}
        if not candidates:return _result(prepared,'Chủ nhân đã loại hết các phương án. Cần thêm hoặc cho một phương án vào lại.',needs_clarification=True)
        limits=frame['slots'];required=[key for key in ('budget','minutes') if key in limits]
        if not required:return _result(prepared,'Chủ nhân cho em biết ngân sách hoặc thời gian tối đa trước khi chọn nhé.',needs_clarification=True)
        for label,option in candidates.items():
            if ('budget' in required and 'cost' not in option) or ('minutes' in required and 'minutes' not in option):
                return _result(prepared,'Phương án '+label+' còn thiếu giá/thời gian. Chủ nhân bổ sung để em kiểm tra đủ điều kiện nhé.',needs_clarification=True)
            if frame['include_fee'] and 'fee' not in option:
                return _result(prepared,'Phí giao của '+label+' là bao nhiêu? Em chưa thể coi là miễn phí.',needs_clarification=True)
            if frame.get('include_travel') and 'travel' not in option:
                return _result(prepared,'Tiền đi về của '+label+' là bao nhiêu? Em chưa có số này để cộng.',needs_clarification=True)
        prefix=[]
        if 'budget' in limits:prefix.append('Ngân sách '+limits['budget']+' đồng')
        if 'minutes' in limits:prefix.append('tối đa '+limits['minutes']+' phút')
        clauses=[]
        for label,option in candidates.items():
            fields=[]
            if 'cost' in option:fields.append('giá '+str(number(option['cost'])+(number(option.get('fee','0')) if frame['include_fee'] else 0)+(number(option.get('travel','0')) if frame.get('include_travel') else 0))+' đồng')
            if 'minutes' in option:fields.append('mất '+option['minutes']+' phút')
            clauses.append(label+' '+', '.join(fields))
        if len(candidates)==1:
            label=next(iter(candidates));option=candidates[label]
            feasible=all(number(option['cost'])+(number(option.get('fee','0')) if frame['include_fee'] else 0)+(number(option.get('travel','0')) if frame.get('include_travel') else 0)<=number(limits['budget']) if key=='budget' else number(option['minutes'])<=number(limits['minutes']) for key in required)
            return _result(prepared,('Chọn '+label+' theo các giới hạn đã nêu.' if feasible else 'Không có phương án nào thỏa các giới hạn.'),choice=label if feasible else None)
        objective='rẻ nhất' if 're nhat' in text else 'nhanh nhất' if 'nhanh nhat' in text else ''
        canonical=' và '.join(prefix)+'. '+'. '.join(clauses)+'. Chọn phương án '+objective+'.'
        result=constraint_choice(canonical)
        if result:
            if re.search(r'vi sao|tai sao|giai thich',text):
                explanations=[]
                for label,option in candidates.items():
                    parts=[]
                    if 'budget' in limits:
                        total=number(option['cost'])+(number(option.get('fee','0')) if frame['include_fee'] else 0)+(number(option.get('travel','0')) if frame.get('include_travel') else 0)
                        parts.append('tổng '+show(total)+' đồng '+('≤' if total<=number(limits['budget']) else '>')+' '+show(number(limits['budget']))+' đồng')
                    if 'minutes' in limits:
                        parts.append(show(number(option['minutes']))+' phút '+('≤' if number(option['minutes'])<=number(limits['minutes']) else '>')+' '+show(number(limits['minutes']))+' phút')
                    explanations.append(label+': '+', '.join(parts))
                result.text+=' '+'. '.join(explanations)+'.'
            prepared.result=result;return prepared
    if updated:
        if re.search(r'goi y|nen lam gi|tu van|giai thich|vi sao|tai sao',text):return prepared
        return _result(prepared,'Đã hiểu và cập nhật. '+describe(frame),updated=updated)
    if new_topic and not re.search(r'\?|goi y|nen |chon |so sanh',text):
        return _result(prepared,'Em hiểu chủ nhân muốn bàn về '+frame['title']+'. Chủ nhân có giới hạn hoặc tiêu chí nào muốn em giữ không?',topic=frame['id'])
    return prepared

def prepare(question,state=None,today=None):
    prepared=_prepare(question,state,today)
    prepared.state=bounded(prepared.state)
    return prepared

def observe_answer(state,metrics):
    state=bounded(state);frame=active(state)
    choice=metrics.get('facts',{}).get('choice')
    if frame and choice in frame['options']:frame['focus']=choice
    return state

def from_history(history):
    state=empty()
    for row in (history or [])[-6:]:
        question=row.get('q','')
        if isinstance(question,str) and question:state=prepare(question,state).state
    return state
