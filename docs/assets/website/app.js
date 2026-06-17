// Local-only document loader. It tries relative paths so the same page works
// from the repository root, docs/, or docs/pages/ on GitHub Pages.
const DOCS = {
  en: {
    title: 'English README',
    kind: 'Project documentation',
    candidates: ['../README.md', './README.md', '../../README.md', 'README.md'],
  },
  'zh-CN': {
    title: '简体中文 README',
    kind: '项目文档',
    candidates: [
      './i18n/zh-CN/README.md',
      './docs/i18n/zh-CN/README.md',
      '../../docs/i18n/zh-CN/README.md',
      '../i18n/zh-CN/README.md',
    ],
  },
  ja: {
    title: '日本語 README',
    kind: 'プロジェクト文書',
    candidates: ['./i18n/ja/README.md', './docs/i18n/ja/README.md', '../../docs/i18n/ja/README.md', '../i18n/ja/README.md'],
  },
  manual: {
    title: 'ActionAgent Manual',
    kind: 'AI and advanced usage',
    candidates: ['./ai/actionagent-manual.md', './docs/ai/actionagent-manual.md', '../../docs/ai/actionagent-manual.md', '../ai/actionagent-manual.md'],
  },
};

const LANGUAGE_DOC_KEYS = ['en', 'zh-CN', 'ja'];
const UI_STRINGS = {
  en: {
    brandAria: 'ActionAgent Docs home',
    navAria: 'Primary navigation',
    manualLabel: 'AI Manual',
    languageLabel: 'Language',
    languageSwitcherAria: 'Language switcher',
    tocToggleAria: 'Open page outline',
    sidebarAria: 'Documentation navigation',
    drawerTitle: 'Page outline',
    tocCloseAria: 'Close outline',
    tocEyebrow: 'On this page',
    tocAria: 'Table of contents',
    loadingTitle: 'Loading...',
    initialLoading: 'Loading local documentation...',
    readingDoc: 'Loading local Markdown document...',
    buildingToc: 'Building outline...',
    noSections: 'No sections on this page.',
    loadFailedTitle: 'Local document failed to load',
    loadFailedBody: 'The configured relative paths did not resolve to a readable Markdown file. Make sure the matching README.md is in the expected project location.',
    tocFailed: 'Outline unavailable',
    headingLinkAria: 'Link to this heading',
    themeLabelLight: 'Light',
    themeLabelDark: 'Dark',
    themeSwitchToDark: 'Switch to dark theme',
    themeSwitchToLight: 'Switch to light theme',
  },
  'zh-CN': {
    brandAria: 'ActionAgent 文档首页',
    navAria: '主导航',
    manualLabel: 'AI 手册',
    languageLabel: '语言',
    languageSwitcherAria: '语言切换',
    tocToggleAria: '打开页面目录',
    sidebarAria: '文档导航',
    drawerTitle: '页面目录',
    tocCloseAria: '关闭目录',
    tocEyebrow: '本页目录',
    tocAria: '目录',
    loadingTitle: '正在加载...',
    initialLoading: '正在加载本地文档...',
    readingDoc: '正在读取本地 Markdown 文档...',
    buildingToc: '正在生成大纲...',
    noSections: '暂无对应小节',
    loadFailedTitle: '本地文档加载失败',
    loadFailedBody: '无法在配置的本地相对路径候选集中检索到有效的 Markdown 文件。请确保对应的 README.md 处于正确的项目相对位置。',
    tocFailed: '大纲生成失败',
    headingLinkAria: '跳转到此标题',
    themeLabelLight: '浅色',
    themeLabelDark: '深色',
    themeSwitchToDark: '切换到深色主题',
    themeSwitchToLight: '切换到浅色主题',
  },
  ja: {
    brandAria: 'ActionAgent Docs ホーム',
    navAria: 'メインナビゲーション',
    manualLabel: 'AI マニュアル',
    languageLabel: '言語',
    languageSwitcherAria: '言語切り替え',
    tocToggleAria: 'ページ目次を開く',
    sidebarAria: 'ドキュメントナビゲーション',
    drawerTitle: 'ページ目次',
    tocCloseAria: '目次を閉じる',
    tocEyebrow: 'このページ',
    tocAria: '目次',
    loadingTitle: '読み込み中...',
    initialLoading: 'ローカルドキュメントを読み込んでいます...',
    readingDoc: 'ローカル Markdown ドキュメントを読み込んでいます...',
    buildingToc: '目次を生成しています...',
    noSections: 'このページに対応する節はありません。',
    loadFailedTitle: 'ローカルドキュメントを読み込めませんでした',
    loadFailedBody: '設定された相対パスから有効な Markdown ファイルを読み込めませんでした。対応する README.md が想定どおりの場所にあるか確認してください。',
    tocFailed: '目次を生成できませんでした',
    headingLinkAria: 'この見出しへのリンク',
    themeLabelLight: 'ライト',
    themeLabelDark: 'ダーク',
    themeSwitchToDark: 'ダークテーマに切り替える',
    themeSwitchToLight: 'ライトテーマに切り替える',
  },
};

const content = document.getElementById('content');
const toc = document.getElementById('toc');
const docTitle = document.getElementById('docTitle');
const docKind = document.getElementById('docKind');
const brandLink = document.getElementById('brandLink');
const manualLink = document.getElementById('manualLink');
const themeToggle = document.getElementById('themeToggle');
const languageSelect = document.getElementById('languageSelect');
const languageLabel = document.getElementById('languageLabel');
const languageSwitcher = document.getElementById('languageSwitcher');
const sidebar = document.getElementById('tocDrawer');
const tocToggle = document.getElementById('tocToggle');
const tocClose = document.getElementById('tocClose');
const tocBackdrop = document.getElementById('tocBackdrop');
const topActions = document.getElementById('topActions');
const drawerTitle = document.getElementById('drawerTitle');
const tocEyebrow = document.getElementById('tocEyebrow');
const contentLoading = document.getElementById('contentLoading');

let activeDoc = localStorage.getItem('actionagent-docs-current-doc') || 'en';
let activeHeadingIds = [];
let lastLanguage = localStorage.getItem('actionagent-docs-last-language') || 'en';

const themeMedia = matchMedia('(prefers-color-scheme: dark)');
const themeFromStorage = localStorage.getItem('actionagent-docs-theme');
document.documentElement.dataset.theme = themeFromStorage || (themeMedia.matches ? 'dark' : 'light');

function currentTheme() {
  return document.documentElement.dataset.theme || 'light';
}

function shellLocale() {
  return LANGUAGE_DOC_KEYS.includes(activeDoc) ? activeDoc : lastLanguage || 'en';
}

function uiText() {
  return UI_STRINGS[shellLocale()] || UI_STRINGS.en;
}

function applyShellText() {
  const ui = uiText();
  document.documentElement.lang = shellLocale();
  if (brandLink) brandLink.setAttribute('aria-label', ui.brandAria);
  if (manualLink) {
    manualLink.textContent = ui.manualLabel;
    manualLink.setAttribute('aria-label', ui.manualLabel);
  }
  if (topActions) topActions.setAttribute('aria-label', ui.navAria);
  if (languageLabel) languageLabel.textContent = ui.languageLabel;
  if (languageSwitcher) languageSwitcher.setAttribute('aria-label', ui.languageSwitcherAria);
  if (tocToggle) tocToggle.setAttribute('aria-label', ui.tocToggleAria);
  if (sidebar) sidebar.setAttribute('aria-label', ui.sidebarAria);
  if (drawerTitle) drawerTitle.textContent = ui.drawerTitle;
  if (tocClose) tocClose.setAttribute('aria-label', ui.tocCloseAria);
  if (tocEyebrow) tocEyebrow.textContent = ui.tocEyebrow;
  if (toc) toc.setAttribute('aria-label', ui.tocAria);
  if (contentLoading) contentLoading.textContent = ui.initialLoading;
  if (docTitle) docTitle.textContent = ui.loadingTitle;
}

function updateThemeLabel() {
  const ui = uiText();
  const next = currentTheme() === 'dark' ? ui.themeLabelLight : ui.themeLabelDark;
  themeToggle.textContent = next;
  themeToggle.setAttribute('aria-label', currentTheme() === 'dark' ? ui.themeSwitchToLight : ui.themeSwitchToDark);
}

applyShellText();
updateThemeLabel();

themeToggle.addEventListener('click', () => {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('actionagent-docs-theme', next);
  updateThemeLabel();
});

function syncPreferredTheme() {
  if (localStorage.getItem('actionagent-docs-theme')) return;
  document.documentElement.dataset.theme = themeMedia.matches ? 'dark' : 'light';
  updateThemeLabel();
}

if (themeMedia.addEventListener) {
  themeMedia.addEventListener('change', syncPreferredTheme);
} else {
  themeMedia.addListener(syncPreferredTheme);
}

function parseDocRouteFromHash() {
  const raw = decodeURIComponent(location.hash || '').trim();
  if (!raw) return null;

  if (raw.startsWith('#/')) {
    const key = raw.slice(2).split(/[?#]/)[0];
    return DOCS[key] ? key : null;
  }

  // Keep compatibility with older links such as #en or #zh-CN.
  const maybeDoc = raw.slice(1);
  return DOCS[maybeDoc] ? maybeDoc : null;
}

function getInitialDoc() {
  return parseDocRouteFromHash() || activeDoc || 'en';
}

function updateLanguageSelect(key) {
  if (!languageSelect) return;
  const selected = LANGUAGE_DOC_KEYS.includes(key) ? key : lastLanguage;
  if (selected && languageSelect.value !== selected) {
    languageSelect.value = selected;
  }
}

if (languageSelect) {
  languageSelect.addEventListener('change', () => {
    const selected = languageSelect.value;
    if (DOCS[selected]) {
      location.hash = `/${selected}`;
    }
  });
}

function setTocOpen(open) {
  if (!sidebar || !tocToggle || !tocBackdrop) return;
  sidebar.classList.toggle('open', open);
  document.body.classList.toggle('toc-open', open);
  tocToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  tocBackdrop.hidden = !open;
}

if (tocToggle) {
  tocToggle.addEventListener('click', () => {
    setTocOpen(!sidebar?.classList.contains('open'));
  });
}

if (tocClose) {
  tocClose.addEventListener('click', () => setTocOpen(false));
}

if (tocBackdrop) {
  tocBackdrop.addEventListener('click', () => setTocOpen(false));
}

toc.addEventListener('click', (event) => {
  const link = event.target.closest('a');
  if (link && matchMedia('(max-width: 900px)').matches) {
    setTocOpen(false);
  }
});

window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') setTocOpen(false);
});

window.addEventListener('resize', () => {
  if (!matchMedia('(max-width: 900px)').matches) setTocOpen(false);
});

async function fetchFirst(paths) {
  let lastError;
  for (const path of paths) {
    try {
      const response = await fetch(path, { cache: 'no-cache' });
      if (response.ok) {
        return { text: await response.text(), path };
      }
      lastError = new Error(`${response.status} ${response.statusText}: ${path}`);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error('No matching local document path was found.');
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#096;');
}

function stripInlineHeadingMarkers(value) {
  return String(value).replace(/#{1,6}\s+(\[[^\]]+\]\([^)]+\))\s+#{1,6}/g, '$1');
}

function slugify(text, used) {
  let slug = text
    .replace(/<[^>]*>/g, '')
    .replace(/\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)/g, '')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[`*_~\[\]()#.!?:，。！？、：；]/g, '')
    .trim()
    .toLowerCase()
    .replace(/[\s/\\]+/g, '-')
    .replace(/^-+|-+$/g, '');

  if (!slug) slug = 'section';
  const base = slug;
  let index = 2;
  while (used.has(slug)) {
    slug = `${base}-${index++}`;
  }
  used.add(slug);
  return slug;
}

function renderInline(source) {
  const placeholders = [];
  let text = escapeHtml(stripInlineHeadingMarkers(source));

  function stash(html) {
    const token = `\u0000${placeholders.length}\u0000`;
    placeholders.push(html);
    return token;
  }

  text = text.replace(/`([^`]+)`/g, (_, code) => stash(`<code>${code}</code>`));

  // Linked image badges: [![license](badge.svg)](target)
  text = text.replace(/\[!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (_, alt, imageUrl, targetUrl) => {
    return stash(`<a href="${escapeAttr(targetUrl)}"><img src="${escapeAttr(imageUrl)}" alt="${escapeAttr(alt)}" loading="lazy"></a>`);
  });

  text = text.replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (_, alt, url) => {
    return stash(`<img src="${escapeAttr(url)}" alt="${escapeAttr(alt)}" loading="lazy">`);
  });

  text = text.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (_, label, url) => {
    return `<a href="${escapeAttr(url)}">${label}</a>`;
  });

  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  text = text.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
  text = text.replace(/(?<!_)_([^_]+)_(?!_)/g, '<em>$1</em>');

  placeholders.forEach((html, index) => {
    text = text.replaceAll(`\u0000${index}\u0000`, html);
  });

  return text;
}

function isTableStart(lines, index) {
  return (
    index + 1 < lines.length &&
    /^\s*\|.*\|\s*$/.test(lines[index]) &&
    /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1])
  );
}

function splitTableRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
}

function isLinkRow(line) {
  const trimmed = line.trim();
  return /^#{1,6}\s+\[[^\]]+\]\([^)]+\)\s+#{1,6}(\s*\|\s*#{1,6}\s+\[[^\]]+\]\([^)]+\)\s+#{1,6})+$/.test(trimmed);
}

function renderLinkRow(line) {
  const parts = line.split('|').map((part) => stripInlineHeadingMarkers(part.trim())).filter(Boolean);
  return `<p class="link-row">${parts.map((part) => renderInline(part)).join('')}</p>`;
}

function renderMarkdown(markdown) {
  const lines = markdown.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').split('\n');
  const html = [];
  const headingIds = new Set();
  let paragraph = [];
  let inCode = false;
  let codeLang = '';
  let codeLines = [];
  let listType = null;
  let blockquoteLines = [];

  function flushParagraph() {
    if (!paragraph.length) return;
    html.push(`<p>${renderInline(paragraph.join(' '))}</p>`);
    paragraph = [];
  }

  function closeList() {
    if (!listType) return;
    html.push(`</${listType}>`);
    listType = null;
  }

  function flushCode() {
    const langClass = codeLang ? ` class="language-${escapeAttr(codeLang)}"` : '';
    html.push(`<pre><code${langClass}>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
    codeLines = [];
    codeLang = '';
  }

  function flushBlockquote() {
    if (!blockquoteLines.length) return;
    html.push(`<blockquote><p>${renderInline(blockquoteLines.join(' '))}</p></blockquote>`);
    blockquoteLines = [];
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    const fence = line.match(/^```\s*([^`]*)\s*$/);
    if (fence) {
      if (inCode) {
        flushCode();
        inCode = false;
      } else {
        flushBlockquote();
        flushParagraph();
        closeList();
        inCode = true;
        codeLang = fence[1].trim();
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    if (!line.trim()) {
      flushBlockquote();
      flushParagraph();
      closeList();
      continue;
    }

    if (isLinkRow(line)) {
      flushBlockquote();
      flushParagraph();
      closeList();
      html.push(renderLinkRow(line));
      continue;
    }

    if (isTableStart(lines, i)) {
      flushBlockquote();
      flushParagraph();
      closeList();
      const headers = splitTableRow(lines[i]);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        rows.push(splitTableRow(lines[i]));
        i++;
      }
      i--;
      html.push('<div class="table-wrap"><table><thead><tr>');
      headers.forEach((header) => html.push(`<th>${renderInline(header)}</th>`));
      html.push('</tr></thead><tbody>');
      rows.forEach((row) => {
        html.push('<tr>');
        row.forEach((cell) => html.push(`<td>${renderInline(cell)}</td>`));
        html.push('</tr>');
      });
      html.push('</tbody></table></div>');
      continue;
    }

    if (/^\s*<!--/.test(line)) {
      flushBlockquote();
      flushParagraph();
      closeList();
      const blockLines = [line];
      if (!/-->\s*$/.test(line)) {
        while (++i < lines.length) {
          blockLines.push(lines[i]);
          if (/-->\s*$/.test(lines[i])) break;
        }
      }
      html.push(blockLines.join('\n'));
      continue;
    }

    // HTML block: single-line OR multi-line (collect until closing tag)
    if (/^\s*<[a-zA-Z]/.test(line)) {
      const openTag = line.match(/^\s*<([a-zA-Z][a-zA-Z0-9-]*)/);
      if (openTag) {
        flushBlockquote();
        flushParagraph();
        closeList();
        const tag = openTag[1].toLowerCase();
        const blockLines = [line];
        const selfClose = /\/\s*>\s*$/.test(line);
        const hasClose = new RegExp(`</${tag}\\s*>`, 'i').test(line);

        if (!selfClose && !hasClose) {
          if (tag === 'div') {
            let depth = (line.match(/<div\b/gi) || []).length - (line.match(/<\/div>/gi) || []).length;
            while (++i < lines.length) {
              const currentLine = lines[i];
              blockLines.push(currentLine);
              depth += (currentLine.match(/<div\b/gi) || []).length;
              depth -= (currentLine.match(/<\/div>/gi) || []).length;
              if (depth <= 0) break;
            }
          } else {
            const closingRe = new RegExp(`</${tag}\\s*>`, 'i');
            while (++i < lines.length) {
              blockLines.push(lines[i]);
              if (closingRe.test(lines[i])) break;
            }
          }
        }

        if (tag === 'div' && blockLines.length >= 2 && /^\s*<div\b/i.test(blockLines[0]) && /<\/div>\s*$/i.test(blockLines[blockLines.length - 1])) {
          const openingLine = blockLines[0];
          const closingLine = blockLines[blockLines.length - 1];
          const innerMarkdown = blockLines.slice(1, -1).join('\n').trim();
          html.push(openingLine);
          if (innerMarkdown) {
            html.push(renderMarkdown(innerMarkdown));
          }
          html.push(closingLine);
        } else {
          html.push(blockLines.join('\n'));
        }
        continue;
      }
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushBlockquote();
      flushParagraph();
      closeList();
      const level = heading[1].length;
      const body = heading[2].replace(/\s+#+\s*$/, '').trim();
      const slugSource = level === 1
        ? body
            .replace(/\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)/g, '')
            .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
            .replace(/\[[^\]]+\]\([^)]*\)/g, '')
            .trim()
        : body;
      const id = slugify(slugSource || body, headingIds);
      html.push(`<h${level} id="${escapeAttr(id)}">${renderInline(body)}<a class="anchor" href="#${escapeAttr(id)}" aria-label="${escapeAttr(uiText().headingLinkAria)}">#</a></h${level}>`);
      continue;
    }

    if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      flushBlockquote();
      flushParagraph();
      closeList();
      html.push('<hr>');
      continue;
    }

    const quote = line.match(/^>\s?(.*)$/);
    if (quote) {
      flushParagraph();
      closeList();
      blockquoteLines.push(quote[1]);
      continue;
    }

    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      flushBlockquote();
      flushParagraph();
      const needed = unordered ? 'ul' : 'ol';
      if (listType !== needed) {
        closeList();
        html.push(`<${needed}>`);
        listType = needed;
      }
      html.push(`<li>${renderInline((unordered || ordered)[1])}</li>`);
      continue;
    }

    flushBlockquote();
    paragraph.push(line.trim());
  }

  if (inCode) flushCode();
  flushBlockquote();
  flushParagraph();
  closeList();
  return html.join('\n');
}

function rewriteRenderedLinks(docKey, fetchedPath) {
  const anchors = content.querySelectorAll('a[href]');
  anchors.forEach((anchor) => {
    const href = anchor.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('http')) return;

    if (/zh-CN\/README\.md|README\.zh-CN\.md/i.test(href)) {
      anchor.setAttribute('href', '#/zh-CN');
      return;
    }
    if (/ja\/README\.md|README\.ja\.md/i.test(href)) {
      anchor.setAttribute('href', '#/ja');
      return;
    }
    if (/README\.md/i.test(href)) {
      anchor.setAttribute('href', '#/en');
      return;
    }
    if (/actionagent-manual\.md/i.test(href)) {
      anchor.setAttribute('href', '#/manual');
      return;
    }

    try {
      anchor.setAttribute('href', new URL(href, new URL(fetchedPath, location.href)).toString());
    } catch {
      anchor.setAttribute('href', href);
    }
  });

  const images = content.querySelectorAll('img[src]');
  images.forEach((image) => {
    const src = image.getAttribute('src');
    if (!src || src.startsWith('data:') || src.startsWith('http')) return;
    try {
      image.setAttribute('src', new URL(src, new URL(fetchedPath, location.href)).toString());
    } catch {
      image.setAttribute('src', src);
    }
  });
}

function buildToc() {
  const headings = Array.from(content.querySelectorAll('h2, h3')).slice(0, 72);
  activeHeadingIds = headings.map((heading) => heading.id);

  if (!headings.length) {
    toc.innerHTML = `<span class="muted">${escapeHtml(uiText().noSections)}</span>`;
    return;
  }

  toc.innerHTML = headings.map((heading) => {
    const level = heading.tagName === 'H3' ? 'sub' : 'top';
    const label = heading.textContent.replace(/#$/, '').trim();
    return `<a class="${level}" href="#${escapeAttr(heading.id)}">${escapeHtml(label)}</a>`;
  }).join('');

  updateActiveToc();
}

function updateActiveToc() {
  if (!activeHeadingIds.length) return;

  const offset = 96;
  let current = activeHeadingIds[0];
  for (const id of activeHeadingIds) {
    const heading = document.getElementById(id);
    if (!heading) continue;
    const top = heading.getBoundingClientRect().top;
    if (top <= offset) current = id;
    else break;
  }

  toc.querySelectorAll('a').forEach((link) => {
    link.classList.toggle('active', link.getAttribute('href') === `#${current}`);
  });
}

async function loadDocument(key = getInitialDoc()) {
  const doc = DOCS[key] || DOCS.en;
  activeDoc = DOCS[key] ? key : 'en';
  localStorage.setItem('actionagent-docs-current-doc', activeDoc);

  if (LANGUAGE_DOC_KEYS.includes(activeDoc)) {
    lastLanguage = activeDoc;
    localStorage.setItem('actionagent-docs-last-language', lastLanguage);
  }

  applyShellText();
  updateLanguageSelect(activeDoc);
  docTitle.textContent = doc.title;
  docKind.textContent = doc.kind;
  content.innerHTML = `<div class="loading">${escapeHtml(uiText().readingDoc)}</div>`;
  toc.innerHTML = `<span class="muted">${escapeHtml(uiText().buildingToc)}</span>`;
  activeHeadingIds = [];
  updateThemeLabel();

  try {
    const { text, path } = await fetchFirst(doc.candidates);
    content.innerHTML = renderMarkdown(text);
    rewriteRenderedLinks(activeDoc, path);
    buildToc();

    const hash = decodeURIComponent(location.hash || '');
    if (hash && !parseDocRouteFromHash() && document.getElementById(hash.slice(1))) {
      requestAnimationFrame(() => document.getElementById(hash.slice(1))?.scrollIntoView());
    } else {
      window.scrollTo({ top: 0 });
    }
  } catch (error) {
    content.innerHTML = `
      <div class="error-box">
        <h2>${escapeHtml(uiText().loadFailedTitle)}</h2>
        <p>${escapeHtml(uiText().loadFailedBody)}</p>
        <pre><code>${escapeHtml(error.message || String(error))}</code></pre>
      </div>
    `;
    toc.innerHTML = `<span class="muted">${escapeHtml(uiText().tocFailed)}</span>`;
  }
}

window.addEventListener('hashchange', () => {
  const route = parseDocRouteFromHash();
  if (route && route !== activeDoc) {
    loadDocument(route);
    return;
  }
  updateActiveToc();
});

window.addEventListener('scroll', () => {
  requestAnimationFrame(updateActiveToc);
}, { passive: true });

updateLanguageSelect(activeDoc);
loadDocument(getInitialDoc());
