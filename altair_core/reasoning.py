"""Narrow, inspectable decision solvers; incomplete premises cause clarification."""
import re
from .toolkit import Result, normalize, number, show, _SCALE


def order_reasoning(question):
    text = normalize(question)
    targets = {'cao':('height',True),'thap':('height',False),'nang':('weight',True),'nhe':('weight',False)}
    target = re.search(r'\bai\s+(cao|thap|nang|nhe)\s+nhat\b',text)
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
        left=re.sub(r'^(?:Hộp|Người|Bạn)\s+','',left);right=re.sub(r'^(?:Hộp|Người|Bạn)\s+','',right)
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
    bounds=list(re.finditer(r'\b(?:ngan sach|toi da|gioi han|co)\s+(\d+(?:[.,]\d+)*)\s*(dong|vnd|phut|gio|tieng|giay)\b',prefix))
    if not bounds or re.search(r'\b(?:khong|chua|chang)\b',prefix):return None
    # A shared qualifier can govern several limits: "tối đa X đồng và Y phút".
    joint=list(re.finditer(r'\bva\s+(\d+(?:[.,]\d+)*)\s*(dong|vnd|phut|gio|tieng|giay)\b',prefix))
    bound_values=[(item[1],item[2]) for item in bounds+joint]
    amounts=list(re.finditer(r'(\d+(?:[.,]\d+)*)\s*(dong|vnd|phut|gio|tieng|giay)\b',prefix))
    if any(not any(start.start()<=item.start() and item.end()<=start.end() for start in bounds+joint) for item in amounts):
        return Result('Em chưa xác định đủ các giới hạn. Chủ nhân nêu rõ ngân sách và thời gian tối đa nhé.','constraint-choice',{'needs_clarification':True})
    if re.search(r'%|giam gia|hoan tien|moi chieu|moi lan|song song',text):return None
    limits={}
    for raw,unit in bound_values:
        dim='minutes' if unit in _SCALE else 'currency'
        value=number(raw)*(_SCALE[unit] if dim=='minutes' else 1)
        if dim in limits and limits[dim]!=value:return None
        limits[dim]=value
    attributes={}
    value_pattern=r'(phi giao hang|phi van chuyen|phi giao|gia|can|mat|ton)\s+(\d+(?:[.,]\d+)*)(?:\s*(dong|vnd|phut|gio|tieng|giay))?\b'
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
            value=number(raw)*(_SCALE[unit] if dim=='minutes' else 1)
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
