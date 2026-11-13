"""Japanese speech preparation without a second language model.

Open answers use one bilingual generation. Exact deterministic replies use a
small reviewed phrasebook. Never pretend a generic spoken acknowledgement is a
translation of an answer; unsupported/truncated translations stay text-only.
"""
import re
PROMPT='\nĐịnh dạng bắt buộc: VI: câu trả lời tiếng Việt ngắn, xưng em/chủ nhân. Sau đó xuống dòng JA: bản dịch tiếng Nhật CÙNG NỘI DUNG, xưng 私 / ご主人様. VI bắt buộc là tiếng Việt có dấu, không viết cả câu tiếng Nhật trong VI kể cả khi câu hỏi là tiếng Nhật. Tối đa 2 câu mỗi ngôn ngữ. Không thêm ý trong bản dịch. Viết xong cả hai. Không dùng romaji.\n日本語で質問されても、VIには必ずベトナム語訳、JAには日本語で答えること。VIを日本語で書いてはいけません。'

def split(text):
    m=re.fullmatch(r'\s*VI:\s*(.*?)\s*JA:\s*(.+?)\s*',text,re.S)
    if not m:
        vi=re.split(r'\s*JA:',re.sub(r'^\s*VI:\s*','',text),maxsplit=1)[0].strip()
        if len(re.findall(r'[\u3040-\u30ff\u4e00-\u9fff]',vi))>max(4,len(vi)*.25) and not re.search(r'[ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]',vi.lower()):
            return 'Em chưa tạo được phụ đề tiếng Việt hoàn chỉnh. Chủ nhân thử hỏi ngắn hơn nhé.',None
        return vi,None
    vi,ja=m.groups()
    if len(re.findall(r'[\u3040-\u30ff\u4e00-\u9fff]',vi))>max(4,len(vi)*.25) and not re.search(r'[ăâđêôơưáàảãạéèẻẽẹíìỉĩịóòỏõọúùủũụýỳỷỹỵ]',vi.lower()):
        return 'Em chưa tạo được phụ đề tiếng Việt hoàn chỉnh. Chủ nhân thử hỏi ngắn hơn nhé.',None
    # Only complete utterances with Japanese script, bounded before synthesis.
    if not re.search(r'[\u3040-\u30ff]',ja) or len(ja)>450 or not re.search(r'[。！？.!?」]$',ja):return vi.strip(),None
    return vi.strip(),ja.strip()

def phrase(question,answer,skill,facts=None):
    from .toolkit import normalize
    q=normalize(question)
    if skill=='identity':
        if answer=='Em là Altair, trợ lý cá nhân của chủ nhân.':return 'ご主人様、私はアルタイル、あなたのパーソナルアシスタントです。'
        if answer=='Chào chủ nhân, Altair đây. Chủ nhân cần em giúp việc gì?':return 'ご主人様、アルタイルです。今日は何をお手伝いしましょうか。'
        if answer=='Không có gì nhé.':return 'どういたしまして。'
    if answer.strip() in ('Chào chủ nhân. Em là Altair. Hôm nay em có thể giúp gì ạ?',):return 'ご主人様、アルタイルです。今日は何をお手伝いしましょうか。'
    # Repeat the exact tool result; never recalculate in a speech model.
    if skill=='calculator' and facts and not facts.get('error'):
        value=str(facts.get('result',''))
        if re.fullmatch(r'-?\d+(?:\.\d+)?',value):return 'ご主人様、計算の結果は'+value+'です。'
    return None


def sample(question,answer,skill):
    from .toolkit import normalize
    if skill=='identity' and normalize(question) in ('xin chao','chao','hello','hi','chao altair','xin chao altair') and answer=='Chào chủ nhân, Altair đây. Chủ nhân cần em giúp việc gì?':
        return 'voice-ja-greeting.wav'
    return None
