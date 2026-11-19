const dateEl = document.getElementById('today');
dateEl.textContent = new Intl.DateTimeFormat('ko-KR', {year:'numeric',month:'long',day:'numeric',weekday:'long'}).format(new Date());
let allItems = [];

const categoryNames = {tech:'TECHNOLOGY', us:'U.S. MARKET', kr:'KOREA MARKET'};
function render(items) {
  const cards = document.getElementById('cards');
  cards.innerHTML = '';
  if (!items.length) {
    cards.innerHTML = '<article class="card"><h3>표시할 뉴스가 없습니다.</h3><p>다음 자동 수집 실행 후 다시 확인해 주세요.</p></article>';
    return;
  }
  items.forEach(item => {
    const article = document.createElement('article');
    article.className = 'card';
    article.dataset.category = item.category;
    const title = document.createElement('h3');
    const link = document.createElement('a');
    link.href = item.link || '#'; link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.textContent = item.title; title.appendChild(link);
    const tag = document.createElement('span');
    tag.className = 'category ' + item.category;
    tag.textContent = categoryNames[item.category] || 'NEWS';
    const desc = document.createElement('p');
    desc.textContent = item.summary || '원문을 열어 자세한 내용을 확인하세요.';
    const meta = document.createElement('div'); meta.className = 'card-meta';
    const source = document.createElement('span'); source.textContent = item.source || '출처 미상';
    const published = document.createElement('span'); published.textContent = item.published || '';
    meta.append(source, published); article.append(tag, title, desc, meta); cards.appendChild(article);
  });
}
function setFilter(filter) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.filter === filter));
  document.querySelectorAll('.card[data-category]').forEach(c => c.hidden = filter !== 'all' && c.dataset.category !== filter);
}
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => setFilter(tab.dataset.filter)));
fetch('data/latest.json')
  .then(r => { if (!r.ok) throw new Error('No data'); return r.json(); })
  .then(data => {
    allItems = data.items || [];
    render(allItems);
    document.getElementById('updated').textContent = data.updated_at ? '업데이트 ' + data.updated_at : '업데이트 완료';
    document.getElementById('status').innerHTML = '<strong>RSS 자동 수집</strong><span>뉴스 제목과 요약문을 수집했습니다. 기사 내용은 각 언론사 원문에서 확인해 주세요.</span>';
  })
  .catch(() => {
    document.getElementById('updated').textContent = '수집 데이터 대기 중';
  });
