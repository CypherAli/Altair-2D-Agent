document.addEventListener('DOMContentLoaded', () => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);
  const conv = $('#conv'), q = $('#q');

  function bubble(who, text) {
    const d = document.createElement('div');
    d.className = 'msg ' + who;
    d.textContent = text;
    conv.appendChild(d);
    while (conv.children.length > 30) conv.removeChild(conv.firstChild); // gioi han DOM, do lag
    conv.scrollTop = conv.scrollHeight;
    return d;
  }

  let streaming = false, controller = null;
  async function ask() {
    if (streaming && controller) { controller.abort(); return; } // bam ↑ lan nua = Dung
    const text = q.value.trim();
    if (!text) { q.focus(); return; }
    bubble('me', '\u203A ' + text);
    q.value = '';
    const repo = (document.querySelector('#repoPath') || {}).value || '';
    const mode = (document.querySelector('#modeSel') || {}).value || 'auto';
    const btn = $('#btnAsk');
    // stream: chu chay tung chu (cam nhan nhanh gap 3-5x)
    const wait = bubble('ali', '');
    // thanh "dang nghi" rieng (che do ky) -> hien loi nghi roi tu an
    const thinkBar = document.createElement('div');
    thinkBar.className = 'thinkbar';
    thinkBar.style.display = 'none';
    wait.appendChild(thinkBar);
    const thinkTxt = document.createElement('span');
    thinkTxt.className = 'thinktxt';
    thinkBar.appendChild(thinkTxt);
    const metaLine = document.createElement('div');
    metaLine.className = 'metaline';
    wait.appendChild(metaLine);
    const ansSpan = document.createElement('span');
    ansSpan.className = 'anstxt';
    wait.appendChild(ansSpan);
    let acc = '', thinkAcc = '', revising = false;
    const renderAns = () => { ansSpan.textContent = acc; conv.scrollTop = conv.scrollHeight; };
    streaming = true; controller = new AbortController();
    btn.textContent = '■';
    try {
      const r = await fetch('/api/ask_stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q: text, repo, mode }), signal: controller.signal
      });
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split('\n\n');
        buf = parts.pop();
        for (const p of parts) {
          if (!p.startsWith('data:')) continue;
          let j; try { j = JSON.parse(p.slice(5)); } catch (_) { continue; }
          if (j.meta) {
            const lbl = { ask: 'hỏi đáp', review: 'review code', write: 'đề xuất sửa', chat: 'chat' }[j.meta.intent] || j.meta.intent;
            metaLine.textContent = 'hiểu ý định: ' + lbl + ' · não: ' + (j.meta.mode === 'ky' ? 'kỹ (nghi + tự soát)' : j.meta.mode);
          }
          if (j.think) {
            thinkAcc += j.think; thinkBar.style.display = 'block';
            thinkTxt.textContent = '🧠 Ali đang nghĩ…\n' + thinkAcc;
            conv.scrollTop = conv.scrollHeight;
          }
          if (j.token) { acc += j.token; renderAns(); }
          if (j.revise) { if (!revising) { revising = true; acc = ''; } acc += j.revise; renderAns(); }
          if (j.done) {
            if (j.text) { acc = j.text; renderAns(); }
            if (thinkAcc) { thinkTxt.textContent = '🧠 Đã nghĩ xong\n' + thinkAcc.slice(0, 400); }
            if (j.sources && j.sources.length) ansSpan.textContent += '\n\n---\nNguon: ' + j.sources.join(', ');
            window.renderSources(j.sources || []);
          }
        }
      }
      if (!acc && !thinkAcc) throw new Error('stream trong');
    } catch (e) {
      if (e && e.name === 'AbortError') {
        ansSpan.textContent += '\n(đã dừng — server vẫn chạy nền cho xong, không tốn thêm chờ)';
        streaming = false; controller = null; btn.textContent = '↑';
        conv.scrollTop = conv.scrollHeight;
        return;
      }
      // fallback duong cu
      ansSpan.textContent = 'Ali dang doc repo...';
      try {
        const r = await fetch('/api/ask', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ q: text, repo, mode }), signal: controller.signal
        });
        const j = await r.json();
        ansSpan.textContent = j.answer || '(trong)';
        window.renderSources(j.sources || []);
      } catch (e2) { ansSpan.textContent = 'Loi: Ollama/server chua chay? ' + e2; }
    }
    streaming = false; controller = null; btn.textContent = '↑';
    conv.scrollTop = conv.scrollHeight;
  }

  $('#btnAsk').addEventListener('click', ask);
  // Enter gui, Shift+Enter xuong dong
  q.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
  });
  $('#btnNew').addEventListener('click', () => { conv.innerHTML = ''; bubble('ali', 'Session moi. Hoi Ali dieu gi do.'); });
  $('#btnLoop').addEventListener('click', async () => {
    const text = q.value.trim();
    if (!text) { bubble('ali', 'Gõ yêu cầu sửa vào ô chat trước (vd: thêm hàm login vào src/cli.mjs), rồi bấm nút này.'); return; }
    if (!confirm('Ali sẽ tự: nghĩ → ghi file (backup .bak) → chạy kiểm tra → sửa tiếp, tối đa 2 vòng. Bắt đầu?')) return;
    q.value = '';
    const repo = (document.querySelector('#repoPath') || {}).value || '';
    const mode = (document.querySelector('#modeSel') || {}).value || 'auto';
    bubble('me', '› [fixloop] ' + text);
    const box = bubble('ali', 'Bắt đầu vòng sửa...');
    try {
      const r = await fetch('/api/fixloop', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q: text, repo, mode, rounds: 2 })
      });
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = '', acc = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split('\n\n');
        buf = parts.pop();
        for (const p of parts) {
          if (!p.startsWith('data:')) continue;
          const j = JSON.parse(p.slice(5));
          if (j.phase && j.text) { acc += '\n[' + j.phase + (j.round ? ' r' + j.round : '') + '] ' + j.text.slice(0, 600) + '\n'; box.textContent = acc; conv.scrollTop = conv.scrollHeight; }
          if (j.done) break;
        }
      }
    } catch (e) { box.textContent += '\n(Lỗi fixloop: ' + e + ')'; }
  });
  $('#btnAccept').addEventListener('click', async () => {
    const alis = document.querySelectorAll('.msg.ali');
    if (!alis.length) { bubble('ali', 'Chua co de xuat nao de duyet.'); return; }
    const last = alis[alis.length - 1].textContent;
    const files = [];
    const re = /@@\s*FILE:\s*([^\n]+)\n```[\w+-]*\n([\s\S]*?)```/g;
    let m;
    while ((m = re.exec(last))) files.push({ path: m[1].trim(), content: m[2] });
    if (!files.length) { bubble('ali', 'De xuat gan nhat khong co khoi @@ FILE de ap dung. Bao Ali xuat theo format @@ FILE.'); return; }
    if (!confirm('Ghi ' + files.length + ' file?\n' + files.map((f) => '- ' + f.path).join('\n') + '\n(Cu co backup .bak)') ) return;
    const repo = (document.querySelector('#repoPath') || {}).value || '';
    const r = await fetch('/api/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo, files }) });
    const j = await r.json();
    bubble('ali', (j.applied.length ? 'Da ghi: ' + j.applied.join(', ') : 'Chua ghi file nao.') + (j.errors.length ? '\nLoi: ' + j.errors.join(' | ') : ''));
  });

  // repo picker
  async function loadRepo() {
    try {
      const r = await fetch('/api/repo'); const j = await r.json();
      $('#repoPath').value = j.repo || '';
      $('#repoName').textContent = (j.repo || '').split(/[/\\]/).pop() || 'acme-platform';
    } catch (e) {}
  }
  loadRepo();
  $('#btnSetRepo').addEventListener('click', async () => {
    const p = $('#repoPath').value.trim(); if (!p) return;
    const r = await fetch('/api/repo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo: p }) });
    const j = await r.json();
    if (j.ok) { $('#repoName').textContent = p.split(/[/\\]/).pop(); bubble('ali', 'Da chon repo: ' + p); }
    else bubble('ali', 'Duong dan khong ton tai: ' + p);
  });
  $('#btnRepo').addEventListener('click', () => { $('#repoPath').focus(); });
  $('#folderPick').addEventListener('change', (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    // browser khong cho lay full path, lay ten + goi y dan paste
    bubble('ali', 'Ban chon folder "' + (f.webkitRelativePath || '').split('/')[0] + '". Vi bao mat trinh duyet, hay copy duong dan day du vao o tren roi bam Set repo.');
  });

  // cac muc demo con lai cho click duoc
  $$('.sess li').forEach((li) => li.addEventListener('click', () => {
    $$('.sess li').forEach((x) => x.classList.remove('on'));
    li.classList.add('on');
    bubble('ali', 'Da chuyen session: ' + li.textContent.trim().slice(0, 40));
  }));
  $$('.tabs span').forEach((t) => t.addEventListener('click', () => {
    $$('.tabs b, .tabs span').forEach((x) => { x.style.color = ''; });
    t.style.color = '#fff';
    bubble('ali', 'Tab ' + t.textContent.trim() + ' (demo, chua co du lieu that).');
  }));
  $$('.f2, .file').forEach((f) => f.addEventListener('click', () => bubble('ali', 'File ' + f.textContent.trim().slice(0, 50) + ' (demo).')));
  $('#btnLesson').addEventListener('click', async () => {
    const t = $('#lesson').value.trim(); if (!t) return;
    await fetch('/api/lesson', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ q: t, title: t.slice(0, 40) }) });
    $('#lesson').value = '';
    bubble('ali', 'Da nho. Tu gio Ali ap dung bai nay moi cau tra loi.');
  });
  const wrap = document.createElement('button');
  wrap.className = 'wsbtn'; wrap.style.cssText = 'cursor:pointer;margin-top:6px;';
  wrap.textContent = '🧠 Xem Ali đã tự học gì';
  wrap.onclick = async () => {
    const r = await fetch('/api/wrapup'); const j = await r.json();
    if (!j.items.length) { bubble('ali', 'Chua co gi. Hoi vai cau di, Ali tu ghi nho.'); return; }
    bubble('ali', j.items.map((o) => `• [${o.type}] ${o.title}`).join('\n'));
  };
  $('#btnLesson').after(wrap);

  window.renderSources = function (sources) {
    const box = $('#srcList');
    if (!box) return;
    $('#srcCount').textContent = sources.length ? sources.length + ' files' : '';
    if (!sources.length) { box.innerHTML = '<div class="f2">Câu này không dùng file nào.</div>'; return; }
    box.innerHTML = '';
    sources.forEach((p) => {
      const d = document.createElement('div');
      d.className = 'f2'; d.style.cursor = 'pointer';
      d.textContent = '⎙ ' + p;
      d.onclick = async () => {
        const repo = (document.querySelector('#repoPath') || {}).value || '';
        try {
          const r = await fetch('/api/file?repo=' + encodeURIComponent(repo) + '&path=' + encodeURIComponent(p));
          const j = await r.json();
          $('#codeView').textContent = '===== ' + j.path + ' =====\n' + j.content;
        } catch (e) { $('#codeView').textContent = '(loi tai file: ' + e + ')'; }
      };
      box.appendChild(d);
    });
  };
  async function loadSettings() {
    try {
      const r = await fetch('/api/settings'); const j = await r.json();
      const s = j.settings || {};
      if (s.api_base) $('#apiBase').value = s.api_base;
      if (s.api_model) $('#apiModel').value = s.api_model;
      if (s.mode) $('#modeSel').value = s.mode;
      if (typeof s.ai_off !== 'undefined') setAiOffUI(s.ai_off === '1');
      let ks = s.api_key ? 'API: đã có key' : 'API: chưa key';
      if (s.api_calls) ks += ' · ' + s.api_calls + ' gọi/' + (s.api_est_tokens || 0) + ' tok';
      $('#keyState').textContent = ks;
    } catch (e) {}
  }
  loadSettings();
  $('#btnKey').addEventListener('click', async () => {
    const body = { api_base: $('#apiBase').value.trim(), api_model: $('#apiModel').value.trim(), api_key: $('#apiKey').value.trim(), mode: $('#modeSel').value };
    if (!body.api_key) { bubble('ali', 'Nhap key truoc khi luu.'); return; }
    const r = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    await r.json();
    $('#apiKey').value = '';
    $('#keyState').textContent = 'API: đã có key';
    bubble('ali', 'Da luu key local. Che do API san sang.');
  });
  $('#modeSel').addEventListener('change', async () => {
    await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: $('#modeSel').value }) });
  });

  // AI OFF: tat model, goi khoi Ollama -> giai phong RAM
  let aiOff = false;
  function setAiOffUI(off) {
    aiOff = off;
    const b = $('#btnAiOff');
    if (b) b.textContent = off ? '🟢 AI đang TẮT — bấm để bật lại' : '🔴 Tắt AI (giải phóng RAM)';
    const st = document.querySelector('#agentState');
    if (st) {
      st.style.color = off ? '#f2b02e' : '';
      st.innerHTML = off
        ? '● AI ĐANG TẮT (RAM trống) <span>TIẾT KIỆM RAM</span>'
        : '● Agent ready <span>UI PREVIEW</span>';
    }
  }
  $('#btnAiOff').addEventListener('click', async () => {
    const on = !aiOff;
    try {
      const r = await fetch('/api/ai_off', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ on })
      });
      const j = await r.json();
      setAiOffUI(!!j.ai_off);
      bubble('ali', (on ? 'Đã TẮT AI — model được gọi khỏi RAM. ' : 'Đã BẬT AI — model sẽ nạp lại ở câu trả lời tiếp theo. ') + (j.unload || ''));
    } catch (e) { bubble('ali', 'Lỗi bật/tắt AI: ' + e); }
  });
});
