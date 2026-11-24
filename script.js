
const dateEl = document.getElementById('today');

dateEl.textContent = new Intl.DateTimeFormat('ko-KR', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long'
}).format(new Date());

let allItems = [];
let analysisData = null;
let currentAnalysis = 'daily';

const categoryNames = {
  tech: 'TECHNOLOGY',
  us: 'U.S. MARKET',
  kr: 'KOREA MARKET'
};

const analysisNames = {
  daily: '일일 분석',
  weekly: '주간 분석'
};

// HTML 요소에 안전하게 텍스트 삽입
function setText(id, value, fallback = '') {
  const element = document.getElementById(id);

  if (element) {
    element.textContent = value || fallback;
  }
}

// 뉴스 목록 표시
function render(items) {
  const cards = document.getElementById('cards');
  cards.innerHTML = '';

  if (!items.length) {
    cards.innerHTML = `
      <article class="card">
        <h3>표시할 뉴스가 없습니다.</h3>
        <p>다음 자동 수집 실행 후 다시 확인해 주세요.</p>
      </article>
    `;
    return;
  }

  items.forEach((item, index) => {
    const article = document.createElement('article');
    article.className = 'card';
    article.dataset.category = item.category;

    const tag = document.createElement('span');
    tag.className = 'category ' + item.category;
    tag.textContent = categoryNames[item.category] || 'NEWS';

    const title = document.createElement('h3');
    const link = document.createElement('a');

    link.href = '#';
    link.textContent = item.title || '제목 없음';

    link.addEventListener('click', (event) => {
      event.preventDefault();
      openNewsModal(index);
    });

    title.appendChild(link);

    const desc = document.createElement('p');
    desc.textContent =
      item.summary || '상세 내용은 원문에서 확인해 주세요.';

    const meta = document.createElement('div');
    meta.className = 'card-meta';

    const source = document.createElement('span');
    source.textContent = item.source || '출처 미상';

    const published = document.createElement('span');
    published.textContent = item.published || '';

    meta.append(source, published);

    article.append(tag, title, desc, meta);
    cards.appendChild(article);
  });
}

// 뉴스 카테고리 필터
function setFilter(filter) {
  document.querySelectorAll('.tabs:not(.analysis-tabs) .tab')
    .forEach(tab => {
      tab.classList.toggle(
        'active',
        tab.dataset.filter === filter
      );
    });

  document.querySelectorAll('.card[data-category]')
    .forEach(card => {
      card.hidden =
        filter !== 'all' &&
        card.dataset.category !== filter;
    });
}

document.querySelectorAll('[data-filter]').forEach(tab => {
  tab.addEventListener('click', () => {
    setFilter(tab.dataset.filter);
  });
});

// 뉴스 상세 창
function openNewsModal(index) {
  const item = allItems[index];

  if (!item) return;

  const modal = document.getElementById('news-modal');

  const category = document.getElementById('modal-category');

  category.textContent =
    categoryNames[item.category] || 'NEWS';

  category.className = 'category ' + (item.category || '');

  setText('modal-title', item.title, '제목 없음');
  setText('modal-source', item.source, '출처 미상');
  setText('modal-date', item.published);

  setText(
    'modal-summary',
    item.summary,
    '현재 제공된 기사 요약이 없습니다. 원문을 확인해 주세요.'
  );

  const points = document.getElementById('modal-points');
  points.innerHTML = '';

  const keyPoints = Array.isArray(item.key_points)
    ? item.key_points
    : [];

  if (keyPoints.length > 0) {
    keyPoints.forEach(point => {
      const li = document.createElement('li');
      li.textContent = point;
      points.appendChild(li);
    });
  } else {
    const li = document.createElement('li');
    li.textContent =
      '추가 핵심 내용은 기사 원문에서 확인해 주세요.';
    points.appendChild(li);
  }

  const originalLink =
    document.getElementById('modal-original-link');

  if (item.link) {
    originalLink.href = item.link;
    originalLink.style.display = 'inline-block';
  } else {
    originalLink.removeAttribute('href');
    originalLink.style.display = 'none';
  }

  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}

// 뉴스 상세 창 닫기
function closeNewsModal() {
  const modal = document.getElementById('news-modal');

  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

document.querySelectorAll('[data-close-modal]').forEach(element => {
  element.addEventListener('click', closeNewsModal);
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    closeNewsModal();
  }
});

// 분석 데이터 표시용 요소 생성
function createTextElement(tag, text, className) {
  const element = document.createElement(tag);

  if (className) {
    element.className = className;
  }

  element.textContent = text || '';

  return element;
}

// 시장 분석 출력
function renderMarket(containerId, marketData) {
  const container = document.getElementById(containerId);

  container.innerHTML = '';

  if (!marketData) {
    container.appendChild(
      createTextElement(
        'p',
        '아직 분석 데이터가 없습니다.'
      )
    );
    return;
  }

  // 분석 요약
  if (marketData.summary) {
    container.appendChild(
      createTextElement(
        'p',
        marketData.summary,
        'market-summary'
      )
    );
  }

  // 시장 지표
  if (Array.isArray(marketData.stats)) {
    const statGrid = document.createElement('div');
    statGrid.className = 'market-stat';

    marketData.stats.forEach(stat => {
      const item = document.createElement('div');
      item.className = 'stat-item';

      item.appendChild(
        createTextElement('span', stat.label)
      );

      item.appendChild(
        createTextElement('strong', stat.value)
      );

      statGrid.appendChild(item);
    });

    container.appendChild(statGrid);
  }

  // 주요 이슈
  if (Array.isArray(marketData.key_points)) {
    const list = document.createElement('ul');

    marketData.key_points.forEach(point => {
      list.appendChild(
        createTextElement('li', point)
      );
    });

    container.appendChild(list);
  }

  // 데이터 기준 시점
  if (marketData.as_of) {
    container.appendChild(
      createTextElement(
        'small',
        '기준: ' + marketData.as_of
      )
    );
  }

  if (
    !marketData.summary &&
    !marketData.stats &&
    !marketData.key_points
  ) {
    container.appendChild(
      createTextElement(
        'p',
        '표시할 분석 내용이 없습니다.'
      )
    );
  }
}

// 미국·한국 증시 분석
function renderAnalysis(type) {
  currentAnalysis = type;

  document.querySelectorAll('[data-analysis]').forEach(tab => {
    tab.classList.toggle(
      'active',
      tab.dataset.analysis === type
    );
  });

  if (!analysisData) {
    renderMarket('us-market', null);
    renderMarket('kr-market', null);
    return;
  }

  const selected = analysisData[type];

  if (!selected) {
    renderMarket('us-market', null);
    renderMarket('kr-market', null);
    return;
  }

  renderMarket('us-market', selected.us);
  renderMarket('kr-market', selected.kr);
}

// 분석 탭 이벤트
document.querySelectorAll('[data-analysis]').forEach(tab => {
  tab.addEventListener('click', () => {
    renderAnalysis(tab.dataset.analysis);
  });
});

// 산업별 분석
function renderIndustry(data) {
  const container =
    document.getElementById('industry-analysis');

  container.innerHTML = '';

  if (!Array.isArray(data) || data.length === 0) {
    const panel = document.createElement('article');
    panel.className = 'market-panel';

    panel.appendChild(
      createTextElement(
        'h3',
        '산업 분석 데이터를 준비 중입니다.'
      )
    );

    panel.appendChild(
      createTextElement(
        'p',
        '분석 데이터가 생성되면 이곳에 표시됩니다.'
      )
    );

    container.appendChild(panel);
    return;
  }

  data.forEach(industry => {
    const card = document.createElement('article');
    card.className = 'industry-card';

    if (industry.topic) {
      card.appendChild(
        createTextElement(
          'span',
          industry.topic,
          'category tech'
        )
      );
    }

    card.appendChild(
      createTextElement(
        'h3',
        industry.title || industry.topic || '산업 분석'
      )
    );

    card.appendChild(
      createTextElement(
        'p',
        industry.summary || '분석 내용이 없습니다.'
      )
    );

    if (Array.isArray(industry.key_points)) {
      const list = document.createElement('ul');

      industry.key_points.forEach(point => {
        list.appendChild(
          createTextElement('li', point)
        );
      });

      card.appendChild(list);
    }

    if (industry.as_of) {
      card.appendChild(
        createTextElement(
          'div',
          '기준: ' + industry.as_of,
          'industry-meta'
        )
      );
    }

    container.appendChild(card);
  });
}

// 뉴스 JSON 불러오기
fetch('data/latest.json')
  .then(response => {
    if (!response.ok) {
      throw new Error('뉴스 데이터 없음');
    }

    return response.json();
  })
  .then(data => {
    allItems = Array.isArray(data.items)
      ? data.items
      : [];

    render(allItems);

    setText(
      'updated',
      data.updated_at
        ? '업데이트 ' + data.updated_at
        : '업데이트 완료'
    );

    const status = document.getElementById('status');

    status.innerHTML = '';

    status.append(
      createTextElement('strong', 'RSS 자동 수집'),
      createTextElement(
        'span',
        allItems.length + '개의 뉴스 데이터를 불러왔습니다.'
      )
    );
  })
  .catch(error => {
    console.error('뉴스 데이터 오류:', error);

    setText('updated', '수집 데이터 대기 중');
  });

// 분석 JSON 불러오기
fetch('data/analysis.json')
  .then(response => {
    if (!response.ok) {
      throw new Error('분석 데이터 없음');
    }

    return response.json();
  })
  .then(data => {
    analysisData = data;

    renderAnalysis(currentAnalysis);
    renderIndustry(data.industry);
  })
  .catch(error => {
    console.warn('분석 데이터:', error);

    renderAnalysis(currentAnalysis);
    renderIndustry([]);
  });

// ==================================================
// 경제지표 표시
// economy.json 불러오기
// ==================================================

function formatEconomyNumber(value) {
  return new Intl.NumberFormat('ko-KR', {
    maximumFractionDigits: 3
  }).format(value);
}

function formatEconomySigned(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) return '-';

  const sign = number > 0 ? '+' : '';
  return sign + formatEconomyNumber(number);
}

// 변화량 표시
function formatEconomyChange(change) {
  if (!change || change.difference === null ||
      change.difference === undefined) {
    return '비교 데이터 없음';
  }

  const unit = change.difference_label || change.unit || '';

  let result =
    formatEconomySigned(change.difference) +
    (unit ? ' ' + unit : '');

  // 금리·실업률은 상대 변화율 대신 %p를 표시
  if (
    unit !== '%p' &&
    Number.isFinite(Number(change.percent_change))
  ) {
    result +=
      ' · ' +
      formatEconomySigned(change.percent_change) +
      '%';
  }

  return result;
}

// 경제지표 카드 생성
function createEconomyCard(indicator) {
  const card = document.createElement('article');
  card.className = 'market-panel';

  const category = createTextElement(
    'span',
    indicator.country === 'US' ? 'UNITED STATES' : 'KOREA',
    'category ' + (indicator.country === 'US' ? 'us' : 'kr')
  );

  card.appendChild(category);

  card.appendChild(
    createTextElement(
      'h3',
      indicator.name || '경제지표'
    )
  );

  const latest = indicator.latest || {};

  const stats = document.createElement('div');
  stats.className = 'market-stat';

  const latestItem = document.createElement('div');
  latestItem.className = 'stat-item';

  latestItem.appendChild(
    createTextElement('span', '최신 관측값')
  );

  latestItem.appendChild(
    createTextElement(
      'strong',
      formatEconomyNumber(latest.value) +
      ' ' + (latest.unit || indicator.unit || '')
    )
  );

  const previousItem = document.createElement('div');
  previousItem.className = 'stat-item';

  previousItem.appendChild(
    createTextElement('span', '직전 관측값')
  );

  const previous = indicator.previous_observation;

  previousItem.appendChild(
    createTextElement(
      'strong',
      previous
        ? formatEconomyNumber(previous.value) +
          ' ' + (previous.unit || indicator.unit || '')
        : '-'
    )
  );

  stats.append(latestItem, previousItem);
  card.appendChild(stats);

  // 직전 관측 대비
  card.appendChild(
    createTextElement(
      'p',
      '직전 관측 대비: ' +
      formatEconomyChange(indicator.change_from_previous)
    )
  );

  // 전년 동기 대비
  card.appendChild(
    createTextElement(
      'p',
      '전년 동기 대비: ' +
      formatEconomyChange(indicator.year_over_year)
    )
  );

  // 비교 기준일 표시
  if (indicator.year_over_year?.reference_date) {
    card.appendChild(
      createTextElement(
        'small',
        '전년 비교 기준일: ' +
        indicator.year_over_year.reference_date
      )
    );
  }

  // 관측 기준일과 주기
  card.appendChild(
    createTextElement(
      'small',
      '관측 기준일: ' +
      (latest.date || '확인 불가') +
      ' · ' +
      (indicator.frequency_name || '주기 미상')
    )
  );

  // 데이터 출처
  if (indicator.source_url) {
    const source = document.createElement('a');

    source.href = indicator.source_url;
    source.target = '_blank';
    source.rel = 'noopener noreferrer';
    source.textContent = '데이터 출처 보기';
    source.style.fontSize = '11px';
    source.style.display = 'inline-block';
    source.style.marginTop = '12px';

    card.appendChild(source);
  }

  return card;
}

// 경제지표 전체 화면 표시
function renderEconomy(data) {
  const industryContainer =
    document.getElementById('industry-analysis');

  if (!industryContainer) return;

  const section = document.createElement('section');

  const heading = document.createElement('div');
  heading.className = 'section-heading archive-heading';

  const headingContent = document.createElement('div');

  headingContent.appendChild(
    createTextElement(
      'p',
      'ECONOMIC INDICATORS',
      'eyebrow'
    )
  );

  headingContent.appendChild(
    createTextElement('h2', '주요 경제지표')
  );

  heading.appendChild(headingContent);
  section.appendChild(heading);

  // 수집 상태
  const successData = Array.isArray(data.data)
    ? data.data.filter(item => item.status === 'success')
    : [];

  const errors = Array.isArray(data.errors)
    ? data.errors
    : [];

  const status = document.createElement('div');
  status.className = 'notice';

  status.appendChild(
    createTextElement(
      'strong',
      '경제지표 수집 현황'
    )
  );

  status.appendChild(
    createTextElement(
      'span',
      '정상 수집 ' + successData.length +
      '개 · 수집 실패 ' + errors.length + '개'
    )
  );

  section.appendChild(status);

  // 한국 ECOS 오류 안내
  const ecosErrors = errors.filter(
    item => item.source === 'ECOS'
  );

  if (ecosErrors.length > 0) {
    const warning = document.createElement('p');

    warning.textContent =
      '한국은행 ECOS 지표 ' +
      ecosErrors.length +
      '개를 수집하지 못했습니다. 인증키 설정을 확인해야 합니다.';

    warning.style.fontSize = '12px';
    warning.style.color = '#a16b16';
    warning.style.margin = '12px 0';

    section.appendChild(warning);
  }

  // 지표 카드
  const grid = document.createElement('div');
  grid.className = 'market-grid';

  if (successData.length === 0) {
    grid.appendChild(
      createTextElement(
        'p',
        '표시할 경제지표 데이터가 없습니다.'
      )
    );
  } else {
    successData.forEach(indicator => {
      grid.appendChild(createEconomyCard(indicator));
    });
  }

  section.appendChild(grid);

  // 데이터 수집 시각
  if (data.updated_at) {
    section.appendChild(
      createTextElement(
        'small',
        '수집 시각: ' + data.updated_at
      )
    );
  }

  // 산업별 분석 바로 앞에 삽입
  const industryHeading =
    industryContainer.previousElementSibling;

  if (
    industryHeading &&
    industryHeading.classList.contains('section-heading')
  ) {
    industryHeading.before(section);
  } else {
    industryContainer.before(section);
  }
}

// economy.json 불러오기
fetch('data/economy.json')
  .then(response => {
    if (!response.ok) {
      throw new Error('경제지표 데이터를 불러오지 못했습니다.');
    }

    return response.json();
  })
  .then(data => {
    renderEconomy(data);
    console.log('경제지표 표시 완료:', data);
  })
  .catch(error => {
    console.error('경제지표 오류:', error);
  });

