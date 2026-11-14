"""Narrow, inspectable decision solvers; incomplete premises cause clarification."""
import re
from .toolkit import Result, normalize, number, show, _SCALE

_SCALE_MONEY={'nghin':1000,'ngan':1000,'trieu':10**6}
_MONEY_U=r'dong|vnd|nghin|ngan|trieu'


def order_reasoning(question):
    text = normalize(question)
    targets = {'cao':('height',True),'thap':('height',False),'nang':('weight',True),'nhe':('weight',False)}
    target = re.search(r'\b(?:ai|nao)\s+(cao|thap|nang|nhe)\s+nhat\b',text)
    if target:axis,want_max=targets[target[1]]
    elif re.search(r'(?:ai|hop nao).*ben trai|ngoai cung ben trai',text):axis,want_max='position',True
    elif re.search(r'ai den (?:cuoi cung|sau cung)',text):axis,want_max='arrival',False
    elif re.search(r'ai den (?:dau tien|som nhat)',text):axis,want_max='arrival',True
    else:return None
    if re.search(r'\b(?:khong|chua|chang|neu)\b',text): return None
    name=r'[^\W\d_][\w-]*(?:\s+[^\W\d_][\w-]*){0,3}'
    phrase=r'cao hơn|thấp hơn|nặng hơn|nhẹ hơn|ở bên trái|ở bên phải|đến trước|đến sau'
    pattern=r'(?:^|[.;,\n]\s*)('+name+r')\s+('+phrase+r')\s+('+name+r')(?=[.;,\n]|$)'
    relations=list(re.finditer(pattern,question))
    if not 1 <= len(relations) <= 20: return None
    if len(relations)!=len(re.findall(r'cao hon|thap hon|nang hon|nhe hon|o ben trai|o ben phai|den truoc|den sau',text)):
        return Result('Em chưa đọc đủ mọi quan hệ. Chủ nhân tách mỗi so sánh thành một câu giúp em nhé.','order-reasoning',{'needs_clarification':True})
    graph={}
    relation_types={'cao hon':('height',True),'thap hon':('height',False),'nang hon':('weight',True),'nhe hon':('weight',False),
                    'o ben trai':('position',True),'o ben phai':('position',False),'den truoc':('arrival',True),'den sau':('arrival',False)}
    for match in relations:
        left,word,right=match.groups();relation_axis,positive=relation_types[normalize(word)]
        strip=r'^(?:Hộp|Người|Bạn|Cái|Con)\s+'
        left=re.sub(strip,'',left,flags=re.I);right=re.sub(strip,'',right,flags=re.I)
        if any(token in {'ai','neu','thi','cao','hon','la','co'} for token in normalize(left+' '+right).split()):return None
        if relation_axis!=axis: return None
        higher,lower=(left,right) if positive else (right,left)
        graph.setdefault(higher,set()).add(lower);graph.setdefault(lower,set())
    if len(graph)>12: return None
    def reach(start):
        found=set();pending=list(graph[start])
        while pending:
            item=pending.pop()
            if item in found:continue
            found.add(item);pending.extend(graph[item])
        return found
    closure={node:reach(node) for node in graph}
    if any(node in below for node,below in closure.items()):
        return Result('Các quan hệ đang mâu thuẫn thành vòng; chủ nhân kiểm tra lại dữ kiện nhé.','order-reasoning',{'needs_clarification':True})
    winners=[node for node in graph if (len(closure[node])==len(graph)-1 if want_max else
        all(node in closure[other] for other in graph if other!=node))]
    if len(winners)!=1:
        return Result('Chưa đủ quan hệ để xác định một người đứng đầu/cuối. Chủ nhân bổ sung so sánh giữa các nhóm nhé.','order-reasoning',{'needs_clarification':True})
    winner=winners[0]
    answer=winner if 'chi tra loi ten' in text else f'{winner}, theo các quan hệ chủ nhân đã nêu.'
    return Result(answer,'order-reasoning',{'winner':winner,'axis':axis,'relations':len(relations),'checked':'acyclic_transitive_order'})


def constraint_choice(question):
    text=normalize(question)
    if not re.search(r'\b(?:chon|phuong an)\b',text):return None
    starts=list(re.finditer(r'\b([a-z])\s+(?=(?:gia|can|mat|ton)\s+\d)',text))
    if not 2<=len(starts)<=8:return None
    prefix=text[:starts[0].start()]
    bounds=list(re.finditer(r'\b(?:ngan sach|toi da|gioi han|co)\s+(\d+(?:[.,]\d+)*)\s*('+_MONEY_U+r'|phut|gio|tieng|giay)\b',prefix))
    if not bounds or re.search(r'\b(?:khong|chua|chang)\b',prefix):return None
    # A shared qualifier can govern several limits: "tối đa X đồng và Y phút".
    joint=list(re.finditer(r'\bva\s+(\d+(?:[.,]\d+)*)\s*('+_MONEY_U+r'|phut|gio|tieng|giay)\b',prefix))
    bound_values=[(item[1],item[2]) for item in bounds+joint]
    amounts=list(re.finditer(r'(\d+(?:[.,]\d+)*)\s*('+_MONEY_U+r'|phut|gio|tieng|giay)\b',prefix))
    if any(not any(start.start()<=item.start() and item.end()<=start.end() for start in bounds+joint) for item in amounts):
        return Result('Em chưa xác định đủ các giới hạn. Chủ nhân nêu rõ ngân sách và thời gian tối đa nhé.','constraint-choice',{'needs_clarification':True})
    if re.search(r'%|giam gia|hoan tien|moi chieu|moi lan|song song',text):return None
    limits={}
    for raw,unit in bound_values:
        dim='minutes' if unit in _SCALE else 'currency'
        value=number(raw)*(_SCALE[unit] if dim=='minutes' else _SCALE_MONEY.get(unit,1))
        if dim in limits and limits[dim]!=value:return None
        limits[dim]=value
    attributes={}
    value_pattern=r'(phi giao hang|phi van chuyen|phi giao|gia|can|mat|ton)\s+(\d+(?:[.,]\d+)*)(?:\s*('+_MONEY_U+r'|phut|gio|tieng|giay))?\b'
    for index,start in enumerate(starts):
        label=start[1].upper()
        if label in attributes:return None
        body=text[start.end():starts[index+1].start() if index+1<len(starts) else len(text)]
        matches=list(re.finditer(value_pattern,body));values={};fees=0
        if not matches:return None
        remaining=re.sub(value_pattern,' ',body)
        if re.search(r'\d|[-−]\s*\d',remaining):return None
        for item in matches:
            verb,raw,unit=item.groups()
            if unit is None:
                unit='dong' if verb=='gia' or verb.startswith('phi') else 'phut' if list(limits)==['minutes'] else None
            if unit is None:return None
            dim='minutes' if unit in _SCALE else 'currency'
            value=number(raw)*(_SCALE[unit] if dim=='minutes' else _SCALE_MONEY.get(unit,1))
            if value>10**12:return None
            if verb.startswith('phi'):
                if dim!='currency':return None
                fees+=value
            else:
                if dim in values:return None
                values[dim]=value
        if fees:values['currency']=values.get('currency',0)+fees
        if not all(dim in values for dim in limits):
            return Result('Mỗi phương án cần đủ thông tin cho tất cả giới hạn. Chủ nhân bổ sung giá/thời gian còn thiếu nhé.','constraint-choice',{'needs_clarification':True})
        attributes[label]=values
    feasible=[key for key,values in attributes.items() if all(values[dim]<=limit for dim,limit in limits.items())]
    primary=next(iter(limits))
    facts={'feasible_ids':feasible,'choice':None,'limits':{key:str(value) for key,value in limits.items()},
           'attributes':{key:{dim:str(value) for dim,value in values.items()} for key,values in attributes.items()},
           'values':{key:str(values[primary]) for key,values in attributes.items()},'limit':str(limits[primary]),'dimension':primary}
    if not feasible:return Result('Không có phương án nào thỏa tất cả giới hạn đã nêu.','constraint-choice',facts)
    if len(feasible)>1:
        optimize='currency' if 're nhat' in text else 'minutes' if re.search(r'nhanh nhat|it thoi gian nhat',text) else primary if 'thap nhat' in text else None
        if optimize and all(optimize in attributes[key] for key in feasible):
            best=min(attributes[key][optimize] for key in feasible);feasible=[key for key in feasible if attributes[key][optimize]==best]
        if len(feasible)>1:
            facts['needs_clarification']=True
            return Result('Có nhiều phương án đáp ứng giới hạn: '+', '.join(feasible)+'. Chủ nhân ưu tiên tiêu chí nào?','constraint-choice',facts)
    winner=feasible[0];facts['choice']=winner
    answer=winner if 'chi tra loi' in text else f'Chọn {winner}: thỏa tất cả giới hạn đã nêu.'
    return Result(answer,'constraint-choice',facts)

_SYLLOGISM_ARTICLES = r'^(?:cac|nhung|con|chiec|cai|mot)\s+'
_SYLLOGISM_LEAD = r'^(?:neu|gia su|gia thiet|theo gia dinh)\s+'
_SYLLOGISM_STOP = r'^(?:khi|thi)\b'


def _syllogism_map(text):
    """normalize() plus an index map, so entity names keep their spelling."""
    out, index = [], []
    for position, char in enumerate(text):
        for piece in normalize(char):
            out.append(piece)
            index.append(position)
    return ''.join(out), index


def _syllogism_display(text, index, normalized, part):
    position = normalized.find(part)
    if position < 0 or not index:
        return part
    return text[index[position]:index[position + len(part) - 1] + 1].strip(' .;,:?!')


def _syllogism_key(name):
    return re.sub(_SYLLOGISM_ARTICLES, '', name.strip()).strip(' .;,:?!')


def _syllogism_query(text):
    """(kind, subject, target) for a question clause, else None."""
    for pattern in (r'^(?:co the ket luan|co suy ra|suy ra duoc|co ket luan)\s+(.+?)\s+(?:la|thuoc)\s+(.+?)(?:\s+(?:khong|ko|k))?$',
                    r'^vay\s+(.+?)\s+(?:la|thuoc)\s+(.+?)(?:\s+(?:khong|ko|k))?$',
                    r'^(.+?)\s+co phai\s+(?:la|thuoc)\s+(.+?)(?:\s+(?:khong|ko|k))?$',
                    r'^(.+?)\s+co phai\s+(.+?)(?:\s+(?:khong|ko|k))?$',
                    r'^(.+?)\s+(?:la|thuoc)\s+(.+?)\s+(?:khong|ko|k)$'):
        match = re.match(pattern, text)
        if match:
            return 'is', match[1], match[2]
    match = re.match(r'^(.+?)\s+(?:la|thuoc)\s+(?:gi|nhom nao|loai nao)$', text)
    return ('what', match[1], None) if match else None


def _syllogism_premise(text):
    """(subject, predicate, positive, universal) for a statement, or None."""
    # "một số/nhiều" must be caught before the plain copula, or it becomes a bogus edge.
    if re.match(r'^(?:mot so|mot vai|vai|nhieu|phan lon|da so)\b', text):
        return 'particular'
    for pattern, positive, universal in (
            (r'^(?:khong|chang)\s+(?:co\s+)?(.+?)\s+(?:nao\s+)?(?:la|thuoc)\s+(.+)$', False, True),
            (r'^(?:moi|tat ca|toan bo|het|bat ky)\s+(.+?)\s+(?:deu\s+)?(?:la|thuoc)\s+(.+)$', True, True),
            (r'^(.+?)\s+(?:khong|chang)\s+(?:phai\s+)?(?:la|thuoc)\s+(.+)$', False, False),
            (r'^(.+?)\s+(?:la|thuoc)\s+(.+)$', True, False)):
        match = re.match(pattern, text)
        if match:
            return match[1], match[2], positive, universal
    return None


def syllogism(question):
    """Deterministic "mọi…/không…" reasoning; an unproven claim is questioned, never guessed."""
    # Trailing "?" must go before parsing, or "…không?" no longer matches the question pattern.
    fragments = [part.strip(' \t\n?!.,;:') for part in
                 re.split(r'[.;\n,]|\s+va\s+|\s+và\s+|\s+thì\s+|\s+thi\s+', question)
                 if part.strip(' .;,\t\n?!:')]
    if not 2 <= len(fragments) <= 9:
        return None
    relations, negatives, labels = {}, [], {}
    query, particular = None, False
    for fragment in fragments:
        text, index = _syllogism_map(fragment)
        # "Nếu … thì …" states the same premises as assumptions; index follows the trim.
        lead = re.match(_SYLLOGISM_LEAD, text)
        if lead:
            text, index = text[lead.end():], index[lead.end():]
        if re.match(_SYLLOGISM_STOP, text):
            return None
        ask = _syllogism_query(text)
        if ask:
            if query is not None:
                return None
            kind, subject, target = ask
            subject_key = _syllogism_key(subject)
            if not subject_key:
                return None
            labels[subject_key] = _syllogism_display(fragment, index, text, subject)
            target_key = None
            if target is not None:
                target_key = _syllogism_key(target)
                if not target_key or target_key == subject_key:
                    return None
                labels[target_key] = _syllogism_display(fragment, index, text, target)
            query = (kind, subject_key, target_key)
            continue
        premise = _syllogism_premise(text)
        if premise == 'particular':
            particular = True
            continue
        if not premise:
            return None
        subject, target, positive, _ = premise
        subject_key, target_key = _syllogism_key(subject), _syllogism_key(target)
        if not subject_key or not target_key or subject_key == target_key:
            return None
        labels.setdefault(subject_key, _syllogism_display(fragment, index, text, subject))
        labels.setdefault(target_key, _syllogism_display(fragment, index, text, target))
        if positive:
            relations.setdefault(subject_key, set()).add(target_key)
        else:
            negatives.append((subject_key, target_key))
    if query is None or not labels:
        return None

    def path(start, goal, seen=None):
        seen = seen or {start}
        if start == goal:
            return [start]
        for step in sorted(relations.get(start, ())):
            if step in seen:
                continue
            found = path(step, goal, seen | {step})
            if found:
                return [start] + found
        return None

    def reachable(start):
        """Names implied by start, nearest first."""
        order, seen, queue = [], {start}, [start]
        while queue:
            for step in sorted(relations.get(queue.pop(0), ())):
                if step not in seen:
                    seen.add(step)
                    order.append(step)
                    queue.append(step)
        return order

    def implies(start, goal):
        return start == goal or goal in reachable(start)

    def conflict_between(subject_key, target_key):
        for left, right in negatives:
            if {left, right} == {subject_key, target_key}:
                return left, right
            if implies(subject_key, left) and implies(target_key, right):
                return left, right
        return None

    kind, subject_key, target_key = query
    label = lambda key: labels.get(key, key)
    if kind == 'what':
        above = [label(node) for node in reachable(subject_key)]
        if not above:
            return Result(f"Em chưa có tiền đề nào cho biết {label(subject_key)} thuộc nhóm nào.", 'syllogism',
                          {'needs_clarification': True, 'answer': 'unknown'})
        return Result(f"{label(subject_key)} là {', '.join(above)} (theo tiền đề đã nêu).", 'syllogism',
                      {'answer': 'yes', 'chain': reachable(subject_key)})
    chain, conflict = path(subject_key, target_key), conflict_between(subject_key, target_key)
    walk = ' → '.join(label(node) for node in chain) if chain else ''
    if chain and conflict:
        return Result(f"Tiền đề mâu thuẫn: {walk}, nhưng cũng có phủ định giữa {label(conflict[0])} và {label(conflict[1])}.",
                      'syllogism', {'needs_clarification': True, 'answer': 'conflict'})
    if chain:
        return Result(f"Có. {walk}.", 'syllogism', {'answer': 'yes', 'chain': chain})
    if conflict:
        detail = (f"{label(subject_key)} là {label(conflict[0])}, và " if conflict[0] != subject_key else '')
        return Result(f"Không. {detail}{label(conflict[0])} không là {label(conflict[1])} theo tiền đề đã nêu.",
                      'syllogism', {'answer': 'no', 'chain': [conflict[0], conflict[1]]})
    hint = ' (câu có "một số/nhiều" nên không đủ để kết luận chung)' if particular else ''
    return Result(f"Em chưa đủ tiền đề để kết luận {label(subject_key)} có là {label(target_key)} hay không{hint}. "
                  f"Chủ nhân bổ sung quan hệ giữa hai khái niệm này nhé.", 'syllogism',
                  {'needs_clarification': True, 'answer': 'unknown'})
