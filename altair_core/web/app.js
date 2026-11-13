const $ = id => document.getElementById(id);
let busy = false, aiOff = false, image = null, imageName = '', abort = null;
const character=window.altairCharacter;
window.altairListener=window.AltairListener?new window.AltairListener(character):null;
$('listen-ja').onclick=()=>window.altairListener?.toggle();
window.altairSendText=text=>{if(busy){character.bubble.textContent='Em đang xử lý câu trước, chủ nhân đợi một chút nhé.';return;} $('question').value=text;$('chat').requestSubmit();};
window.altairJapaneseInput=text=>window.altairSendText(text);
document.addEventListener('altair:chat',()=>{if(!document.body.classList.contains('pet-ui'))$('question').focus();});

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}

function message(who, text) {
  const box = document.createElement('div'); box.className = 'message ' + who;
  const label = document.createElement('span'); label.className = 'label';
  label.textContent = who === 'user' ? 'Chủ nhân' : 'Altair';
  const content = document.createElement('span'); content.textContent = text;
  box.append(label,content); $('conversation').append(box);
  const list=$('conversation'); list.classList.remove('empty'); list.scrollTop=list.scrollHeight;
  return {box,content};
}

function sources(box, items, metrics={}) {
  if(!items?.length && !metrics.google_url) return;
  const list=document.createElement('div'); list.className='source-list';
  const label=document.createElement('div');
  label.textContent=metrics.provider ? `Nguồn tìm qua ${metrics.provider}${metrics.search_cache_hit ? ' · kết quả đã lưu' : ''}` : 'Nguồn tham khảo';
  list.append(label);
  for(const row of items || []) {
    try {
      const url=new URL(row.url); if(!['http:','https:'].includes(url.protocol)) continue;
      const link=document.createElement('a'); link.href=url.href; link.target='_blank'; link.rel='noopener noreferrer';
      link.textContent=`[${row.id}] ${row.title} · ${url.hostname}${row.read ? '' : ' · chưa đọc được trang'}${row.fetched_at ? ' · đọc lúc '+row.fetched_at : ''}`;
      list.append(link,document.createElement('br'));
    } catch {}
  }
  if(metrics.google_url) {
    const link=document.createElement('a'); link.href=metrics.google_url; link.target='_blank'; link.rel='noopener noreferrer';
    link.textContent='Mở tìm kiếm Google'; list.append(link);
  }
  box.append(list);
}

function setBusy(value) {
  busy=value; $('send').disabled=value; $('new').disabled=value;
  $('stop').hidden=!value; $('image').disabled=value;
  character?.lockDemo(value);
}

function resetImage() {
  image=null; imageName=''; $('image').value=''; $('attachment').textContent='';
  $('clear-image').hidden=true;
}

async function refresh() {
  try {
    const state=await api('/api/status');
    aiOff=state.settings.ai_off === '1';
    $('power').textContent=aiOff ? 'Bật AI' : 'Tắt AI';
    let text=aiOff ? 'Model đang tắt; công cụ và tra cứu web vẫn dùng được.' : !state.online ? 'Runtime chưa sẵn sàng. Mở lại AltairStudio.bat.' :
      !state.installed ? 'Chưa cài model Altair. Chạy SetupAltair.bat.' :
      `Model ${state.model} · ngữ cảnh ${state.settings.num_ctx} · ${state.settings.num_thread} luồng CPU`;
    if (state.loaded_models.length) {
      text += ' · bộ nhớ tiến trình/model: ' + (state.loaded_models[0].size/1024**3).toFixed(2) + ' GiB';
    }
    const metrics=state.metrics || {};
    if(metrics.route === 'context') text += ` · hiểu bối cảnh: ${(metrics.elapsed_s*1000).toFixed(1)} ms`;
    else if(metrics.route === 'web') text += ` · ${metrics.provider || 'tra cứu web'}: ${metrics.elapsed_s?.toFixed(1)} giây` + (metrics.answer_mode === 'summary' ? ' · tổng hợp từ nguồn' : ' · trích nguồn');
    else if(metrics.route === 'skill') text += ` · công cụ ${metrics.skill}: ${(metrics.elapsed_s*1000).toFixed(1)} ms`;
    else if(metrics.route === 'cache') text += ' · trả lời đã lưu, không gọi model';
    else if(metrics.tokens_per_s) text += ` · ${metrics.tokens_per_s} token/s` + (metrics.prefix_reused ? ' · dùng tiếp ngữ cảnh' : '');
    $('status').textContent=text; $('status').title=text;
  } catch(error) { $('status').textContent=error.message; $('status').title=error.message; }
}

$('image').addEventListener('change', async event => {
  const file=event.target.files[0];
  if (!file) return;
  if (!['image/png','image/jpeg'].includes(file.type) || file.size>3*1024*1024) {
    resetImage(); message('error','Chọn ảnh PNG/JPEG dưới 3 MB.'); return;
  }
  const reader=new FileReader();
  reader.onload=() => {
    image=String(reader.result).split(',')[1]; imageName=file.name;
    $('attachment').textContent=file.name; $('clear-image').hidden=false;
  };
  reader.readAsDataURL(file);
});
$('clear-image').onclick=resetImage;

$('chat').onsubmit=async event => {
  event.preventDefault();
  if(busy) return;
  const question=$('question').value.trim();
  if(!question) return;
  const local=window.AltairInteraction?.commandFor(question);
  if(local){message('user',question);message('assistant',local.vi);$('question').value='';character?.demo(local.action);return;}
  $('conversation').querySelector('.empty-state')?.remove();
  await window.altairListener?.cancel();
  if($('read-aloud').checked)character?.unlockAudio().catch(()=>{});
  const body={q:question,bilingual:$('read-aloud').checked}; if(image) body.images=[image];
  if($('search-mode').value !== 'auto') body.web=$('search-mode').value === 'on';
  const user=message('user',question);
  if(image) { const img=document.createElement('img'); img.src='data:image/png;base64,'+image;
    img.alt=imageName; user.box.append(img); }
  $('question').value=''; resetImage();
  const reply=message('assistant','Em đang xử lý…'); let text='',failed=false,completed=false;
  await character?.stopSpeech();character?.set(body.web===true?'searching':'thinking',{text:'Em đang xem yêu cầu của chủ nhân…'});
  setBusy(true); abort=new AbortController();
  try {
    const response=await fetch('/api/ask_stream',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:abort.signal});
    if(!response.ok) throw new Error(`HTTP ${response.status}`);
    const reader=response.body.getReader(), decoder=new TextDecoder(); let buffer='';
    function consume(part) {
      if(!part.startsWith('data: ')) return;
      const result=JSON.parse(part.slice(6));
      if(result.token) { const list=$('conversation');
        const atBottom=list.scrollHeight-list.scrollTop-list.clientHeight<90;
        text+=result.token; reply.content.textContent=text;
        if(atBottom) list.scrollTop=list.scrollHeight;
        if(character?.state!=='speaking')character?.set('speaking'); }
      if(result.error) { failed=true;reply.box.classList.add('error');character?.set('error',{text:result.error,duration:6000});
        reply.content.textContent=(text ? text+'\n\n' : '')+result.error; }
      if(result.cancelled) {failed=true;reply.content.textContent=(text || '')+'\n[Đã dừng]';character?.set('idle');}
      if(result.done)completed=true;
      if(result.done && !result.error && !result.cancelled) {sources(reply.box,result.sources,result.metrics);character?.respond(text,result.metrics);}
    }
    while(true) {
      const result=await reader.read();
      buffer+=decoder.decode(result.value || new Uint8Array(),{stream:!result.done});
      const parts=buffer.split('\n\n'); buffer=parts.pop(); parts.forEach(consume);
      if(result.done) { if(buffer.trim()) consume(buffer); break; }
    }
  } catch(error) {
    failed=true;character?.stopSpeech();character?.set(error.name==='AbortError'?'idle':'error',{duration:5000});
    reply.content.textContent=(text ? text+'\n\n' : '')+
      (error.name==='AbortError' ? '[Đã dừng]' : error.message);
  } finally { if(!failed&&!completed)character?.set('idle');setBusy(false); abort=null; await refresh(); }
};
$('question').addEventListener('keydown', event => {
  if(event.key==='Enter' && !event.shiftKey) { event.preventDefault(); $('chat').requestSubmit(); }
});
$('stop').onclick=async () => {
  await character?.stopSpeech();character?.set('idle');
  try { await api('/api/stop',{}); } catch(error) { $('status').textContent=error.message; }
  if(abort) abort.abort();
};
function emptyState() {
  const box=document.createElement('div'); box.className='empty-state';
  const title=document.createElement('strong'); title.textContent='Bắt đầu thế nào cũng được, chủ nhân.';
  const text=document.createElement('span'); text.textContent='Hỏi em bất cứ điều gì, hoặc thử một trong các việc dưới đây — những câu này em trả lời ngay trên máy, không cần chờ model.';
  const chips=document.createElement('div'); chips.className='chips';
  for(const [label,q] of [['Hôm nay thứ mấy?','hôm nay là thứ mấy'],['Tính 125000 × 3','Tính 125000 * 3'],['Đổi 2,5 km sang m','Đổi 2,5 km sang m']]) {
    const chip=document.createElement('button'); chip.type='button'; chip.textContent=label;
    chip.onclick=()=>{ $('question').value=q; $('chat').requestSubmit(); };
    chips.append(chip);
  }
  box.append(title,text,chips); $('conversation').replaceChildren(box); $('conversation').classList.add('empty');
}

$('new').onclick=async () => {
  try { await api('/api/new',{}); $('conversation').replaceChildren(); emptyState(); resetImage();character?.stopSpeech();character?.set('waving',{text:'Em sẵn sàng cho câu chuyện mới, chủ nhân.',duration:2500}); }
  catch(error) { message('error',error.message); }
};
$('power').onclick=async () => {
  $('power').disabled=true;
  try { await api('/api/ai_off',{on:!aiOff}); }
  catch(error) { message('error',error.message); }
  finally { $('power').disabled=false; await refresh(); }
};
$('notes').onsubmit=async event => {
  event.preventDefault();
  try { await api('/api/notes',{text:$('note').value}); $('note').value='';
    $('note-state').textContent='Đã lưu ghi nhớ vào máy.'; }
  catch(error) { $('note-state').textContent=error.message; }
};
(async () => {
  try { const data=await api('/api/history');
    for(const row of data.history) { message('user',row.q); const reply=message('assistant',row.a); sources(reply.box,row.sources); }
    if(!data.history.length) emptyState();
  } catch(error) { message('error',error.message); }
  await refresh();
})();
