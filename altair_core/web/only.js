/* Character-only surface. No chat panel here: talking happens in chat.html. */
(() => {
 'use strict';
 const pet = window.altairCharacter;
 if (!pet) return;
 const dock = document.getElementById('only-dock');
 const voice = document.getElementById('only-voice');
 let bubbleTimer = null;

 const showBubble = (ms = 12000) => {
  if (!pet.bubble.textContent.trim()) return;
  clearTimeout(bubbleTimer);
  document.body.dataset.bubble = 'true';
  bubbleTimer = setTimeout(() => { document.body.dataset.bubble = 'false'; }, ms);
 };
 new MutationObserver(() => showBubble(pet.root.dataset.audio === 'playing' ? 45000 : 12000))
  .observe(pet.bubble, { childList: true, characterData: true, subtree: true });
 new MutationObserver(() => { if (pet.root.dataset.audio === 'ended') showBubble(9000); })
  .observe(pet.root, { attributes: true, attributeFilter: ['data-audio'] });

 const openChat = () => {
  if (window.pywebview?.api?.chat) return window.pywebview.api.chat();
  const w = window.open('chat.html', 'altair-chat', 'popup=yes,width=430,height=700');
  if (!w) location.href = 'chat.html';
 };
 document.getElementById('only-chat').addEventListener('click', openChat);
 document.addEventListener('altair:chat', openChat);

 voice.addEventListener('click', () => {
  const on = !pet.voiceInput.checked;
  pet.voiceInput.checked = on;
  pet.voiceInput.dispatchEvent(new Event('change'));
  if (!on) pet.stopSpeech();
  voice.setAttribute('aria-pressed', String(on));
  voice.textContent = on ? 'Giọng' : 'Tắt tiếng';
 });

 dock.addEventListener('click', event => {
  const demo = event.target.closest('[data-demo]')?.dataset.demo;
  if (demo) { pet.unlockAudio().catch(() => {}); pet.demo(demo); }
 });
 dock.addEventListener('pointerdown', () => { document.body.dataset.touched = 'true'; });

 /* First touch anywhere: browsers only allow audio after a gesture. */
 pet.stage.addEventListener('pointerdown', () => {
  if (pet.root.dataset.armed === 'true') return;
  pet.root.dataset.armed = 'true';
  pet.unlockAudio().catch(() => {});
 }, { once: false });

 voice.setAttribute('aria-pressed', String(pet.voiceInput.checked));
 pet.set('idle');
})();
