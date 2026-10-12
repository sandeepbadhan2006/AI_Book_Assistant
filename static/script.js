const $ = id => document.getElementById(id);
const booksEl = $('books'), messages = $('messages'), question = $('question'), send = $('send');
let books = [], selected = new Set();

const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const inline = s => s
  .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  .replace(/(^|[^*])\*(?!\s)([^*]+?)\*(?!\*)/g, '$1<em>$2</em>');

function fmt(text) {
  let html = '', list = null;
  const close = () => { if (list) { html += `</${list}>`; list = null; } };
  for (const raw of esc(text).split('\n')) {
    const l = raw.trim(); let m;
    if (!l) { close(); continue; }
    if ((m = l.match(/^#{1,6}\s+(.*)/))) { close(); html += `<h3>${inline(m[1])}</h3>`; }
    else if ((m = l.match(/^[-*\u2022]\s+(.*)/))) { if (list !== 'ul') { close(); html += '<ul>'; list = 'ul'; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = l.match(/^\d+[.)]\s+(.*)/))) { if (list !== 'ol') { close(); html += '<ol>'; list = 'ol'; } html += `<li>${inline(m[1])}</li>`; }
    else if (/^\*\*[^*]+\*\*:?$/.test(l)) { close(); html += `<h3>${inline(l)}</h3>`; }
    else { close(); html += `<p>${inline(l)}</p>`; }
  }
  close();
  return html;
}

function setStatus(msg, err = false) { const s = $('status'); s.textContent = msg; s.className = 'status' + (err ? ' err' : ''); }

async function loadBooks(selectNew = []) {
  books = await (await fetch('/api/books')).json();
  const ids = new Set(books.map(b => b.id));
  selected = new Set([...selected].filter(i => ids.has(i)));
  selectNew.forEach(i => selected.add(i));
  renderBooks();
}

function renderBooks() {
  booksEl.innerHTML = books.length ? '' : '<li class="muted">Your shelf is empty.</li>';
  books.forEach(b => {
    const li = document.createElement('li');
    li.className = 'book';
    li.innerHTML = `<input type="checkbox" ${selected.has(b.id) ? 'checked' : ''} aria-label="Use ${esc(b.name)}">
      <div class="t"><div class="n" title="${esc(b.name)}">${esc(b.name)}</div><div class="m">${b.chunks} passages</div></div>
      <button class="x" title="Remove book" aria-label="Remove ${esc(b.name)}">×</button>`;
    li.querySelector('input').onchange = e => { e.target.checked ? selected.add(b.id) : selected.delete(b.id); updateScope(); };
    li.querySelector('.x').onclick = () => removeBook(b);
    booksEl.appendChild(li);
  });
  updateScope();
}

function updateScope() {
  const n = selected.size;
  $('scope').textContent = !books.length ? 'No books yet'
    : n === 0 ? 'No books selected, tick the books to search'
    : n === 1 ? 'Searching 1 book' : `Searching ${n} books`;
  $('toggleAll').textContent = n === books.length && n ? 'Clear' : 'Select all';
}

$('toggleAll').onclick = () => {
  selected = selected.size === books.length ? new Set() : new Set(books.map(b => b.id));
  renderBooks();
};

async function removeBook(b) {
  if (!confirm(`Remove "${b.name}" from your shelf?`)) return;
  await fetch('/api/books/' + b.id, { method: 'DELETE' });
  loadBooks();
}

async function upload(files) {
  if (!files.length) return;
  const fd = new FormData();
  [...files].forEach(f => fd.append('files', f));
  setStatus(`Reading ${files.length} file(s)... large books can take a minute.`);
  try {
    const r = await (await fetch('/api/upload', { method: 'POST', body: fd })).json();
    await loadBooks(r.added.map(b => b.id));
    if (r.errors.length) setStatus(r.errors.join(' | '), true);
    else setStatus(`Added ${r.added.length} book(s).`);
  } catch { setStatus('Upload failed. Check that the server is running.', true); }
}

const drop = $('drop');
$('fileInput').onchange = e => { upload(e.target.files); e.target.value = ''; };
['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => upload(e.dataTransfer.files));

function add(cls, html) {
  $('empty')?.remove();
  const d = document.createElement('div');
  d.className = 'msg ' + cls; d.innerHTML = html;
  messages.appendChild(d); messages.scrollTop = messages.scrollHeight;
  return d;
}

async function ask() {
  const q = question.value.trim();
  if (!q || send.disabled) return;
  if (!selected.size) { add('ai error', 'Select at least one book on the shelf first.'); return; }
  add('user', esc(q));
  question.value = ''; question.style.height = 'auto';
  send.disabled = true;
  const wait = add('ai', '<span class="dots"><i></i><i></i><i></i></span>');
  try {
    const res = await fetch('/api/ask', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, book_ids: [...selected] })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Something went wrong');
    const chips = (data.sources || []).map(s =>
      `<span class="chip">${esc(s.book)}, p. ${s.pages.join(', ')}</span>`).join('');
    wait.innerHTML = fmt(data.answer) + (chips ? `<div class="srcs">${chips}</div>` : '');
  } catch (e) {
    wait.className = 'msg ai error'; wait.textContent = e.message;
  }
  send.disabled = false; messages.scrollTop = messages.scrollHeight; question.focus();
}

send.onclick = ask;
question.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); } });
question.addEventListener('input', () => { question.style.height = 'auto'; question.style.height = question.scrollHeight + 'px'; });
$('menu').onclick = () => $('shelf').classList.toggle('open');

loadBooks().then(() => { selected = new Set(books.map(b => b.id)); renderBooks(); });