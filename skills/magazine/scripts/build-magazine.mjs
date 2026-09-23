#!/usr/bin/env node
'use strict';

/*
 * build-magazine.mjs — turn markdown documents into one self-contained, printable HTML edition.
 *
 * Zero dependencies beyond Node's standard library and, for diagrams, `mmdc` on PATH; a global
 * highlight.js (`npm i -g highlight.js`) colours code blocks at build time and is skipped when
 * absent. The stylesheet beside it is inlined into the output, so the result is a single file
 * that can be moved, mailed, archived, or printed offline.
 *
 * Source files are READ-ONLY inputs. Their prose is read from disk and converted, never rewritten,
 * reordered or summarised — the edition is wording-faithful by construction, and the build proves
 * it: after rendering, every non-blank source line (or table cell) is looked for in the edition's
 * text, and a missing one fails the build.
 *
 * Usage:
 *   node build-magazine.mjs --out <edition.html> [options] <doc.md> [doc2.md ...]
 *
 *   --out <path>          Output HTML file (required)
 *   --kind <k>            feature | brief | dashboard. Inferred from the document when omitted:
 *                         a table of 8+ columns → dashboard (landscape); under 2,000 words →
 *                         brief; exhibits outweighing prose → dashboard; otherwise feature.
 *   --title "..."         Masthead title (default: first document's H1)
 *   --subtitle "..."      Masthead subhead
 *   --kicker "..."        Uppercase label above the title (feature default: "Edition")
 *   --thesis "..."        One-line banner under the masthead
 *   --columns / --single  Force two columns or one (the kind decides otherwise)
 *   --serif-body /        Force the body face (feature is serif, brief and dashboard sans)
 *   --sans-body
 *   --landscape           Force landscape (a table of 8+ columns forces it anyway)
 *   --toc / --no-toc      Force the contents block on or off
 *   --accent "#2456a6"    Accent colour
 *   --mermaid <mode>      mmdc (default; a build error when mmdc is missing) | cdn | code
 *   --diagram-direction   auto (default) transposes a wide LR flowchart to TD when that helps;
 *                         keep leaves the author's direction alone
 *   --label-cap <pt>      Largest a plate's labels print (default 10, the body size); a plate
 *                         is never enlarged past it just because the page has room
 *   --css <path>          Override the bundled stylesheet (its :root is the palette, plates included)
 *
 *   node build-magazine.mjs --mermaid-config <out.json> [--accent ...] [--css ...]
 *                         Write the mermaid config the plates render with and build nothing;
 *                         the diagram skill's magazine target measures with it.
 *   node build-magazine.mjs --place <w>x<h> [--kind k] [--label-cap pt]
 *                         Print, as JSON, where a figure of that native SVG size is placed and
 *                         at what scale; build nothing. The diagram skill's magazine target
 *                         measures label size with this scale, so both report what prints.
 *   --no-verify           Skip the fidelity check (never for a shipped edition)
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// mmdc is a .cmd shim on Windows and must be run through the shell; its arguments are the
// builder's own file paths, so the DEP0190 deprecation notice is noise here.
process.noDeprecation = true;
const DEFAULT_CSS = path.resolve(__dirname, '..', 'assets', 'magazine.css');
const MERMAID_THEME = path.resolve(__dirname, '..', 'assets', 'mermaid-theme.json');
const GEOMETRY = JSON.parse(readFileSync(path.resolve(__dirname, '..', 'assets', 'geometry.json'), 'utf8'));

// Graphviz is installed by winget and is not on PATH in every shell, so its default location is
// tried too.
const DOT_FALLBACK = 'C:\\Program Files\\Graphviz\\bin\\dot.exe';

// ---------------------------------------------------------------- fences
//
// What a fence is, and which fences become plates: the diagram skill's fences.json, the one
// definition the diagram gate, the edit gate and this builder all read. fenceAt mirrors that
// skill's fences.py line for line; its tests/fences fixture pins every tool to one answer.
// A Graphviz fence is what the diagram skill escalates a real graph to when mermaid cannot lay
// it out legibly.

const FENCES_JSON = path.resolve(__dirname, '..', '..', 'diagram', 'scripts', 'fences.json');
if (!existsSync(FENCES_JSON)) {
  throw new Error(`build-magazine: ${FENCES_JSON} is missing; the magazine needs the diagram skill installed beside it`);
}
const FENCE_SPEC = JSON.parse(readFileSync(FENCES_JSON, 'utf8'));
// language as written (lower-case) -> the engine that draws it: mermaid | graphviz
const DIAGRAM_LANGS = Object.fromEntries(Object.entries(FENCE_SPEC.diagramLanguages).map(([k, v]) => [k.toLowerCase(), v]));
const ANY_LANGUAGE = Object.fromEntries(FENCE_SPEC.markers.map((m) => [m.char, m.anyLanguage]));
const FENCE_OPENER = new RegExp(
  '^[ \\t]*((?<ch>[' + Object.keys(ANY_LANGUAGE).map((c) => c.replace(/[\\\]^-]/g, '\\$&')).join('') +
  '])\\k<ch>{' + (FENCE_SPEC.minLength - 1) + ',})[ \\t]*(.*?)[ \\t]*$');

// { run, lang } when the line opens a fence, else null.
function fenceOpener(line) {
  const m = line.match(FENCE_OPENER);
  if (!m) return null;
  const run = m[1];
  const info = m[3];
  if (run[0] === '`' && info.includes('`')) return null;   // inline code, not a fence
  const lang = info ? info.split(/\s+/)[0] : '';
  if (!ANY_LANGUAGE[run[0]] && !Object.hasOwn(DIAGRAM_LANGS, lang.toLowerCase())) return null;
  return { run, lang };
}

function isCloser(line, run) {
  const s = line.trim();
  return s.length >= run.length && [...s].every((c) => c === run[0]);
}

// The fence opening on line i, running to its closer (end) or the end of the document.
function fenceAt(lines, i) {
  const o = fenceOpener(lines[i]);
  if (!o) return null;
  let j = i + 1;
  while (j < lines.length && !isCloser(lines[j], o.run)) j++;
  const lower = o.lang.toLowerCase();
  return { start: i, end: j, run: o.run, lang: o.lang, engine: Object.hasOwn(DIAGRAM_LANGS, lower) ? DIAGRAM_LANGS[lower] : null };
}

function scanFences(lines) {
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    const f = fenceAt(lines, i);
    if (f) { out.push(f); i = f.end; }
  }
  return out;
}

const splitLines = (md) => md.replace(/\r\n?/g, '\n').split('\n');

// ---------------------------------------------------------------- document kinds
//
// One decision per build, made from the document's own shape and overridable by flag. Everything
// below the recognisers (type scale, spacing unit, palette, print block) is shared; the kind sets
// the column count, the body face, the masthead scale, and which recognisers are active.

const KINDS = {
  feature: {
    columns: true, serif: true, toc: 'auto', masthead: 'feature', kicker: 'Edition',
    deck: true, pullquote: true, dropcap: true, cards: true, ladder: true, colophon: true,
  },
  brief: {
    columns: false, serif: false, toc: false, masthead: 'brief', kicker: null,
    deck: true, pullquote: false, dropcap: false, cards: true, ladder: true, colophon: true,
  },
  dashboard: {
    columns: false, serif: false, toc: 'auto', masthead: 'brief', kicker: null,
    deck: false, pullquote: false, dropcap: false, cards: true, ladder: true, colophon: true,
    proseColumns: true,   // exhibits take the width; a long run of prose between them flows in two columns
  },
};

// A run of prose this long, between exhibits in a dashboard, is set in two columns; a shorter
// one stays a single column at the reading measure rather than becoming two stubs.
const PROSE_COLUMNS_MIN_WORDS = 120;
// What breaks a prose run in a dashboard: anything that is not running text.
const EXHIBIT_HTML = /^<(table|figure|pre|section|header|hr|div class="(cards|deck|colophon))/;

const WIDE_TABLE_COLS = 8;        // a table this wide forces landscape and the dashboard kind
const BRIEF_MAX_WORDS = 2000;
const DASHBOARD_EXHIBIT_SHARE = 0.4;   // tables and code outweighing prose and lists

function inferKind(stats) {
  if (stats.maxCols >= WIDE_TABLE_COLS) return 'dashboard';
  if (stats.words < BRIEF_MAX_WORDS) return 'brief';
  if (stats.exhibitWords / Math.max(1, stats.words) > DASHBOARD_EXHIBIT_SHARE) return 'dashboard';
  return 'feature';
}

// ---------------------------------------------------------------- arguments

function parseArgs(argv) {
  const o = { inputs: [], mermaid: 'mmdc', accent: null, toc: null, columns: null, serif: null, verify: true };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const val = () => argv[++i];
    switch (a) {
      case '--out': o.out = val(); break;
      case '--kind': o.kind = val(); break;
      case '--title': o.title = val(); break;
      case '--subtitle': o.subtitle = val(); break;
      case '--kicker': o.kicker = val(); break;
      case '--thesis': o.thesis = val(); break;
      case '--columns': o.columns = true; break;
      case '--single': o.columns = false; break;
      case '--serif-body': o.serif = true; break;
      case '--sans-body': o.serif = false; break;
      case '--landscape': o.landscape = true; break;
      case '--toc': o.toc = true; break;
      case '--no-toc': o.toc = false; break;
      case '--accent': o.accent = val(); break;
      case '--mermaid': o.mermaid = val(); break;
      case '--diagram-direction': o.diagramDirection = val(); break;
      case '--label-cap': o.labelCap = Number(val()); break;
      case '--css': o.css = val(); break;
      case '--mermaid-config': o.mermaidConfigOut = val(); break;
      case '--place': o.place = val(); break;
      case '--no-verify': o.verify = false; break;
      default:
        if (a.startsWith('--')) throw new Error(`unknown option: ${a}`);
        o.inputs.push(a);
    }
  }
  if (o.accent && !/^#[0-9a-fA-F]{6}$/.test(o.accent)) throw new Error('--accent takes a #rrggbb color');
  if (o.kind && !KINDS[o.kind]) throw new Error(`--kind must be one of ${Object.keys(KINDS).join(', ')}`);
  if (o.mermaidConfigOut) return o;   // writes the plates' mermaid config and builds nothing
  if (o.place) return o;              // reports one figure's placement and builds nothing
  if (!o.out) throw new Error('--out <file.html> is required');
  if (!o.inputs.length) throw new Error('at least one markdown file is required');
  return o;
}

// ---------------------------------------------------------------- inline markdown

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ESC[c]);

function inline(src) {
  // Code spans are extracted first so their contents are never touched by other rules.
  const spans = [];
  let s = src.replace(/`([^`]+)`/g, (_, code) => {
    spans.push(`<code>${esc(code)}</code>`);
    return `@@CODESPAN${spans.length - 1}@@`;
  });

  s = esc(s);
  s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_, alt, src2) => `<img alt="${alt}" src="${src2}">`);
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, text, href) => `<a href="${href}">${text}</a>`);
  s = s.replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  s = s.replace(/(^|[^_\w])_([^_\n]+)_(?![a-zA-Z0-9])/g, '$1<em>$2</em>');
  s = s.replace(/~~([^~]+)~~/g, '<del>$1</del>');
  s = s.replace(/@@CODESPAN(\d+)@@/g, (_, i) => spans[Number(i)]);
  return s;
}

const slug = (s) =>
  s.toLowerCase().replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '-').slice(0, 60);

const words = (s) => String(s).trim().split(/\s+/).filter(Boolean).length;
const stripMd = (s) => String(s).replace(/[*_`~]/g, '');

// A bold lead: `**Term.** rest`, `**Step 3 - Name.** rest`, `**Risk:** rest`.
// The separator after the closing ** (a colon, or a spaced dash) belongs to the lead: dropped, a
// card body would open with an orphaned ":" and the line would no longer be contiguous.
const BOLD_LEAD = /^\*\*([^*]{2,80})\*\*(:|\s+[-—–](?=\s))?/;
// A plain lead inside a list item: `Precondition: ...`, `Today (verified): ...`.
const PLAIN_LEAD = /^([A-Z][A-Za-z0-9 ,()/'-]{1,44}?):\s+(.*)$/s;
const VERDICT_LEXICON = /^(Recommendation|Verdict|Decision|Answer|In short|Conclusion|Bottom line)\b/i;
// Inside a rung, the leads that carry an answer: the recommendation is set off under an accent
// rule, a decision on the verdict's ground, and a pending one on no ground at all. These are
// the leads a list may split on alone (every other lead needs a partner to count as fielding).
const ANSWER_LEAD = /^(Recommendation|Verdict|Answer|In short|Conclusion|Bottom line)$/i;
const DECISION_LEAD = /^(Decided|Decision)$/i;
const PENDING_LEAD = /^(Pending|Undecided|Open)$/i;
// The leads that make a rung an item put to a reader: a recommendation awaiting a decision, or
// the decision itself. A verdict or a conclusion is a step's own outcome, not an ask.
const ASK_LEAD = /<dt>(Recommendation|Answer|Decided|Decision|Pending|Undecided|Open)\b/i;
// A lead ends in a colon, except these, which the author writes as a sentence: "**Pending.**".
const DOT_LEADS = 'Pending|Decided|Undecided|Open';
const NUMBERED_LEAD = /^(Step|Rung|Phase|Stage|Item|Round|Day|Week)\s+(\d+)/i;

const splitLead = (t) => {
  const m = t.match(BOLD_LEAD);
  return { label: m ? m[1] : '', sep: m && m[2] ? m[2].trim() : '', rest: t.replace(BOLD_LEAD, '') };
};
// The separator, set quietly beside its label. The text is unchanged: "Label" + ":" + " rest".
const sepHtml = (sep) => (sep ? `<span class="sep">${sep === ':' ? ':' : ' ' + sep}</span>` : '');

// ---------------------------------------------------------------- block parser
//
// Markdown to a typed block model. No HTML is produced here; the structure pass below decides what
// each block becomes, because that decision depends on neighbours (a deck needs the paragraph after
// an opener; a ladder needs a run) and on the document kind.

function parseBlocks(md, ctx) {
  const lines = splitLines(md);
  const out = [];
  let i = 0;

  const isListLine = (l) => /^(\s*)([-*+]|\d+[.)])\s+/.test(l);

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (/^\s*<!--.*-->\s*$/.test(line)) { i++; continue; }   // an HTML comment is markup, not prose

    // fenced code / mermaid
    const fence = fenceAt(lines, i);
    if (fence) {
      const body = lines.slice(i + 1, fence.end).join('\n');
      i = fence.end + 1;
      out.push(fence.engine ? { k: 'figure', src: body, engine: fence.engine } : { k: 'code', lang: fence.lang, body });
      continue;
    }

    // heading
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      const level = h[1].length;
      const text = h[2].replace(/\s+#+\s*$/, '');
      if (level === 1) { ctx.h1 = ctx.h1 || text; i++; continue; } // H1 becomes the doc title
      const id = slug(stripMd(text));
      if (level === 2) {
        // The numeral stays in the heading's own text; the badge is a second rendering of the
        // same glyph, never a deletion.
        const m = text.match(/^(\d+(?:\.\d+)*[.)]?)\s+(.*)$/);
        out.push({ k: 'opener', id, num: m ? m[1] : null, text: m ? m[2] : text });
        ctx.seenSection = true;
      } else {
        out.push({ k: 'h', level, id, text });
      }
      i++;
      continue;
    }

    // horizontal rule
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { out.push({ k: 'hr' }); i++; continue; }

    // blockquote
    if (/^\s*>/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ''));
      const inner = parseBlocks(buf.join('\n'), { ...ctx, seenSection: true });
      // A blockquote before the first section is provenance, not an epigraph.
      out.push({ k: 'quote', inner, colophon: !ctx.seenSection });
      continue;
    }

    // pipe table
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])) {
      // Split on unescaped pipes only: a cell may legitimately contain \| (a verdict
      // alternation, a regex).
      const cells = (row) => row
        .trim()
        .replace(/^\||\|$/g, '')
        .split(/(?<!\\)\|/)
        .map((c) => c.trim().replace(/\\\|/g, '|'));
      const head = cells(lines[i]);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(cells(lines[i++]));
      const cols = Math.max(head.length, ...rows.map((r) => r.length));
      out.push({ k: 'table', head, rows, cols });
      continue;
    }

    // lists, any depth. A blank line ends the list; an indented line that is not an item
    // continues the previous item. Nested items are kept as a tree, so nothing is dropped.
    if (isListLine(line)) {
      const root = { sub: [] };
      const stack = [{ indent: -1, node: root }];
      let taskList = false;
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
        if (m) {
          const indent = m[1].length;
          while (stack.length > 1 && stack[stack.length - 1].indent >= indent) stack.pop();
          const parent = stack[stack.length - 1].node;
          let text = m[3];
          let task = null;
          const t = text.match(/^\[([ xX])\]\s+(.*)$/);
          if (t) { task = t[1] !== ' '; text = t[2]; taskList = true; }
          const item = { text, sub: [], ordered: /^\d/.test(m[2]), task };
          parent.sub.push(item);
          stack.push({ indent, node: item });
          i++;
        } else if (stack.length > 1 && /^\s+\S/.test(lines[i]) && !fenceOpener(lines[i])) {
          stack[stack.length - 1].node.text += ' ' + lines[i].trim();
          i++;
        } else break;
      }
      const items = root.sub;
      out.push({
        k: 'list', items, taskList,
        ordered: items.length ? items[0].ordered : false,
        hasNested: items.some((it) => it.sub.length),
      });
      continue;
    }

    // paragraph
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^\s*(#{1,6}\s|>|\|)/.test(lines[i]) && !fenceOpener(lines[i]) && !isListLine(lines[i])) {
      buf.push(lines[i++]);
    }
    if (buf.length) out.push({ k: 'p', raw: buf.join(' ') });
    else i++;
  }
  return out;
}

// ---------------------------------------------------------------- shape statistics

function docStats(blocks) {
  const s = { words: 0, proseWords: 0, exhibitWords: 0, quoteWords: 0, maxCols: 0, h2: 0, quotes: 0, figures: 0 };
  const listWords = (items) => items.reduce((a, it) => a + words(it.text) + listWords(it.sub), 0);
  const walk = (bs) => {
    for (const b of bs) {
      switch (b.k) {
        case 'p': s.words += words(b.raw); s.proseWords += words(b.raw); break;
        case 'opener': s.h2++; s.words += words(b.text); break;
        case 'h': s.words += words(b.text); break;
        case 'list': { const w = listWords(b.items); s.words += w; s.proseWords += w; break; }
        case 'table': { const w = words([b.head, ...b.rows].flat().join(' ')); s.maxCols = Math.max(s.maxCols, b.cols); s.words += w; s.exhibitWords += w; break; }
        case 'code': { const w = words(b.body); s.words += w; s.exhibitWords += w; break; }
        case 'figure': s.figures++; break;
        case 'quote': { s.quotes++; const before = s.words; walk(b.inner); s.quoteWords += s.words - before; break; }
        default: break;
      }
    }
  };
  walk(blocks);
  return s;
}

// ---------------------------------------------------------------- renderers

// A list item's nested sub-list, rendered inline wherever an item may carry one.
const renderSub = (it) => (it.sub.length ? renderList(it.sub, it.sub[0].ordered) : '');

function renderItems(items) {
  return items.map((it) => {
    const cls = it.task === null ? '' : it.task ? ' class="done"' : ' class="todo"';
    return `<li${cls}>${inline(it.text)}${renderSub(it)}</li>`;
  }).join('');
}

function renderList(items, ordered, cls = '') {
  const tag = ordered ? 'ol' : 'ul';
  return `<${tag}${cls ? ` class="${cls}"` : ''}>${renderItems(items)}</${tag}>`;
}

// A table whose cells are paragraphs is a set of records: at 8pt, with the widest cell setting
// every column, it was the worst thing in the old edition. Records become cards; a two-column
// term/meaning table becomes a definition list at body size. A short lookup table stays a table.
function classifyTable(b) {
  const cells = b.rows.flat();
  if (!cells.length) return 'table';
  const lens = cells.map(words);
  const mean = lens.reduce((a, c) => a + c, 0) / lens.length;
  if (b.head.length === 2 && b.rows.every((r) => r.length <= 2) && cells.some((c) => String(c).length > 12)) return 'deflist';
  if (b.rows.length <= 16 && (mean >= 18 || Math.max(...lens) > 40)) return 'cards';
  return 'table';
}

// Cards two to a row. A row is one block: it moves to the next page whole, so a card is never
// stranded from its partner, and the reading order across then down is the source order.
const cardRows = (cards) => {
  const rows = [];
  for (let i = 0; i < cards.length; i += 2) {
    const pair = cards.slice(i, i + 2);
    // A row holding a long card may break across the page rather than leave a band of white.
    const long = pair.some((c) => c.includes('class="card long"')) ? ' long' : '';
    rows.push(`<div class="card-row${long}">${pair.join('')}</div>`);
  }
  return rows.join('');
};

function renderRecordCards(b, span) {
  const cards = b.rows.map((r) => {
    const fields = r.slice(1).map((cell, k) => cell
      ? `<dt>${inline(b.head[k + 1] || ' ')}</dt><dd>${inline(cell)}</dd>`
      : '').join('');
    const long = words(r.join(' ')) > 120 ? ' long' : '';
    return `<article class="card${long}"><h5 class="card-title">${inline(r[0] || '')}</h5><dl>${fields}</dl></article>`;
  });
  // The table's own header row, once, above the grid: the first header word names what each card
  // is, and it appears nowhere else.
  const head = `<div class="cards-head${span}">${b.head.map((h) => `<span>${inline(h)}</span>`).join('')}</div>`;
  // A grid row cannot break across a page, so records that run to paragraphs are stacked as
  // full-width entries that can, each with its fields side by side.
  const stacked = b.rows.some((r) => words(r.join(' ')) > STACKED_RECORD_WORDS);
  return head + (stacked ? `<section class="records${span}">${cards.join('')}</section>` : `<section class="cards${span}">${cardRows(cards)}</section>`);
}

const renderDefList = (b) =>
  `<div class="deflist-head"><span>${inline(b.head[0] || '')}</span><span>${inline(b.head[1] || '')}</span></div>` +
  `<dl class="deflist">${b.rows.map((r) =>
    `<dt>${inline(r[0] || '')}</dt><dd>${inline(r[1] || '')}</dd>`).join('')}</dl>`;

// A column with a handful of short repeated values is a status column: each value becomes a
// pill, hue from a fixed lexicon, text unchanged. An unlisted value is a neutral pill.
const PILL_HUES = [
  [/^(green|exists|passed|pass|yes|done|ok|clear|live|ready|complete|shipped)$/i, 'green'],
  [/^(amber|later|deferred|pending|partial|wip|in progress|waiver|caution|soon)$/i, 'amber'],
  [/^(red|blocked|failed|fail|no|missing|broken|rejected|conflict|taken)$/i, 'red'],
  [/^(new|blue|planned|proposed)$/i, 'blue'],
];
function pillColumns(b) {
  if (b.rows.length < 4) return new Set();
  const cols = new Set();
  for (let c = 1; c < b.cols; c++) {
    const vals = b.rows.map((r) => String(r[c] || '').trim()).filter(Boolean);
    if (vals.length < b.rows.length * 0.8) continue;
    const distinct = new Set(vals.map((v) => v.toLowerCase()));
    const known = [...distinct].filter((v) => PILL_HUES.some(([re]) => re.test(v))).length;
    if (distinct.size <= 6 && distinct.size < vals.length && known >= distinct.size * 0.6 && vals.every((v) => words(v) <= 2 && v.length <= 14)) cols.add(c);
  }
  return cols;
}
const pill = (text) => {
  const hue = (PILL_HUES.find(([re]) => re.test(text.trim())) || [null, 'neutral'])[1];
  return `<span class="pill ${hue}">${inline(text)}</span>`;
};

function renderTable(b, span) {
  // A column whose every cell is short is a key column — an id, a count, a verdict. Held on
  // one line so it cannot fragment at its own hyphen.
  const keyCol = [];
  for (let c = 0; c < b.cols; c++) {
    const column = [b.head, ...b.rows].map((r) => String(r[c] || '').trim());
    keyCol[c] = column.every((v) => v.length <= 12);
  }
  const pills = pillColumns(b);
  const cell = (tag, c, idx) => `<${tag}${keyCol[idx] ? ' class="nw"' : ''}>${tag === 'td' && pills.has(idx) && String(c).trim() ? pill(c) : inline(c)}</${tag}>`;
  return `<table class="tbl${span}${b.cols >= WIDE_TABLE_COLS ? ' wide' : ''}"><thead><tr>` +
    b.head.map((c, idx) => cell('th', c, idx)).join('') + '</tr></thead><tbody>' +
    b.rows.map((r) => '<tr>' + r.map((c, idx) => cell('td', c, idx)).join('') + '</tr>').join('') +
    '</tbody></table>';
}

// The sub-leads every item of a list shares ("Was:" and "Is:", "Today:" and "Under continuous
// operation:", "Implemented now:" and "Stubbed now:"). A list whose items all carry the same two or
// more of them is a ladder with fields, not a card grid, and a pair of them is a comparison.
function sharedLeads(bodies) {
  const LEAD_IN_BODY = new RegExp(`(?:^\\s*|[.!?:]\\s+|\\*\\*)([A-Z][A-Za-z0-9 ,()/'-]{1,40}?)(?:\\*\\*)?(?::|(?<=${DOT_LEADS})\\.)(?:\\*\\*)?\\s`, 'g');
  const sets = bodies.map((t) => new Set([...t.matchAll(LEAD_IN_BODY)].map((m) => m[1])));
  if (!sets.length) return [];
  const count = new Map();
  for (const st of sets) for (const lead of st) count.set(lead, (count.get(lead) || 0) + 1);
  // One shared lead is enough when it is an answer: a list of questions that each carry a
  // "Recommendation:" is a fielded ladder with one field per rung — and a decision counts
  // wherever it appears, even on one item, once the list is fielded at all.
  const isAnswer = (l) => ANSWER_LEAD.test(l) || DECISION_LEAD.test(l) || PENDING_LEAD.test(l);
  const common = [...count.entries()].filter(([l, c]) => c >= Math.ceil(sets.length * 0.6) || isAnswer(l)).map(([l]) => l);
  return common.length >= 2 || common.some(isAnswer) ? common : [];
}

// Split a body at its shared leads, in order of appearance. Every character is kept: what comes
// before the first lead is the rung's intro; each lead heads the text up to the next one, and
// keeps the mark the author closed it with (a colon, or the full stop of "Pending.").
function splitFields(body, leads) {
  const alt = leads.map((l) => l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  // A lead may follow a sentence end across the item's own line break and indentation.
  const re = new RegExp(`(?:^\\s*|(?<=[.!?:]\\s{1,8})|(?<=\\*\\*))(${alt})(?:\\*\\*)?(:|(?<=${DOT_LEADS})\\.)(?:\\*\\*)?\\s`, 'g');
  const fields = [];
  let intro = body;
  let last = null;
  for (const m of body.matchAll(re)) {
    const start = m.index;
    if (last === null) intro = body.slice(0, start).replace(/\*\*\s*$/, '');
    else fields[fields.length - 1].text = body.slice(last, start).replace(/\*\*\s*$/, '');
    fields.push({ lead: m[1] + m[2], text: '' });
    last = m.index + m[0].length;
  }
  if (last !== null) fields[fields.length - 1].text = body.slice(last).replace(/\*\*\s*$/, '');
  return { intro, fields };
}

// The wrapper a field gets from its lead: the answer under an accent rule, the decision on the
// verdict's ground, a pending decision on none. Text inside is untouched.
function fieldClass(lead) {
  const word = lead.replace(/[:.]$/, '');
  if (ANSWER_LEAD.test(word)) return ' class="answer"';
  if (DECISION_LEAD.test(word)) return ' class="decision"';
  if (PENDING_LEAD.test(word)) return ' class="decision pending"';
  return '';
}

const renderFields = (fields) => {
  // Two fields are a comparison and may sit side by side — unless one is an answer, which
  // reads top to bottom: question, recommendation, decision.
  const pair = fields.length === 2 && !fields.some((f) => fieldClass(f.lead));
  const cls = pair ? 'fields pair' : 'fields';
  return `<dl class="${cls}">${fields.map((f) =>
    `<div${fieldClass(f.lead)}><dt>${inline(f.lead)}</dt><dd>${inline(f.text)}</dd></div>`).join('')}</dl>`;
};

// One rung of a ladder: a label, its text, and optionally its fields (from a list that follows a
// bold-lead paragraph, or from shared leads inside the item's own body). A numbered rung's badge
// shows the lead's own number — "Step 0" is 0, never a count.
// A rung from an ordered list carries the list's own ordinal instead, so a numbered set of
// questions keeps its numbers on the page.
function renderRung(label, sep, rest, fieldsHtml, numbered, ordinal = null) {
  const n = numbered ? label.match(NUMBERED_LEAD) : null;
  const num = n ? n[2] : ordinal;
  const badge = num !== null && num !== undefined ? `<span class="rung-badge">${esc(String(num))}</span>` : '';
  // A rung over about twelve lines may break rather than leave a third of a column empty; a
  // fielded rung has natural seams between its parts and may break at half that, each field
  // staying whole.
  const total = words(rest) + words(fieldsHtml.replace(/<[^>]+>/g, ' '));
  const long = total > LONG_ITEM_WORDS || (fieldsHtml && total > LONG_ITEM_WORDS / 2) ? ' long' : '';
  // A rung put to a reader (see ASK_LEAD) is framed as a card, its number set large, so one item
  // never runs into the next.
  const ask = ASK_LEAD.test(fieldsHtml) ? ' ask' : '';
  return `<div class="rung${long}${ask}"><p>${badge ? badge + ' ' : ''}<span class="rung-label">${inline(label)}</span>${sepHtml(sep)}${inline(rest)}</p>${fieldsHtml}</div>`;
}

// The list that follows a rung paragraph: fields when every item has a lead and none is nested,
// a plain list inside the rung otherwise.
function rungListHtml(list) {
  if (!list) return '';
  const leads = list.items.map((it) => {
    if (it.sub.length) return null;
    const b = it.text.match(BOLD_LEAD);
    if (b) return { lead: b[1] + (b[2] ? b[2].trim() : ''), text: it.text.replace(BOLD_LEAD, '') };
    const p = it.text.match(PLAIN_LEAD);
    return p ? { lead: p[1] + ':', text: p[2] } : null;
  });
  if (leads.every(Boolean)) return renderFields(leads);
  return renderList(list.items, list.ordered);
}

function classifyList(b, kind) {
  if (b.taskList || !b.items.length) return 'list';
  const leads = b.items.filter((it) => BOLD_LEAD.test(it.text)).length;
  if (leads / b.items.length < 0.8) return 'list';
  const bodies = b.items.map((it) => it.text.replace(BOLD_LEAD, ''));
  if (!b.hasNested && kind.ladder && sharedLeads(bodies).length) return 'fielded';
  // A nested list has no home inside a card; it stays a run-in item with its sub-list intact.
  if (!b.hasNested && kind.cards && b.items.length <= 8 && Math.max(...bodies.map(words)) <= 60) return 'cardgrid';
  return 'runin';
}

const renderCardGrid = (b, span) =>
  `<section class="cards${span}">${cardRows(b.items.map((it) => {
    const { label, sep, rest } = splitLead(it.text);
    return `<article class="card"><h5 class="card-title">${inline(label)}${sepHtml(sep)}</h5><p>${inline(rest)}</p></article>`;
  }))}</section>`;

const renderRunInItem = (it) => {
  const { label, sep, rest } = splitLead(it.text);
  const long = words(it.text) > LONG_ITEM_WORDS ? ' class="long"' : '';
  return `<li${long}><span class="runin-label">${inline(label)}</span>${sepHtml(sep)}${inline(rest)}${renderSub(it)}</li>`;
};

const renderRunIn = (b) => {
  const tag = b.ordered ? 'ol' : 'ul';
  const start = b.start || 1;
  return `<${tag} class="runin">${b.items.map((it, k) => {
    const { label, sep, rest } = splitLead(it.text);
    const sub = renderSub(it);
    const long = words(it.text) > LONG_ITEM_WORDS ? ' class="long"' : '';
    // An ordered run-in keeps its numbers: the prose refers to "kind 1" and the list must show it.
    const badge = b.ordered ? `<span class="rung-badge">${start + k}</span> ` : '';
    return `<li${long}>${badge}<span class="runin-label">${inline(label)}</span>${sepHtml(sep)}${inline(rest)}${sub}</li>`;
  }).join('')}</${tag}>`;
};

const renderFielded = (b) => {
  const bodies = b.items.map((it) => it.text.replace(BOLD_LEAD, ''));
  const leads = sharedLeads(bodies);
  const numbered = b.items.every((it) => NUMBERED_LEAD.test(splitLead(it.text).label));
  const start = b.start || 1;
  return `<div class="ladder${b.ordered ? ' numbered' : ''}">${b.items.map((it, k) => {
    const { label, sep, rest } = splitLead(it.text);
    const { intro, fields } = splitFields(rest, leads);
    return renderRung(label, sep, intro, renderFields(fields), numbered, b.ordered && !numbered ? start + k : null);
  }).join('')}</div>`;
};

// ---------------------------------------------------------------- structure pass
//
// Runs over the whole block list once it is known, because the deck needs the paragraph after an
// opener, a ladder needs a run, and the pull-quote needs to know how long it has been since the
// reader last had something other than body text to land on. Every transform re-containers text:
// nothing is rewritten, reordered, trimmed or summarised. A pull-quote is a duplicate and the
// sentence stays in the prose; card labels are the table's own header words.

const DECK_MIN_WORDS = 15;
const DECK_MAX_WORDS = 70;
const PULLQUOTE_GAP_WORDS = 320;   // about 60% of a page of body text with no other entry point
const PULLQUOTE_SECTION_MIN = 300;
const PULLQUOTE_MIN_WORDS = 6;      // the shortest emphasis worth lifting: a slogan
const DROPCAP_MIN_WORDS = 40;
const LONG_ITEM_WORDS = 120;        // a run-in item longer than this is a paragraph with a label
const LADDER_PAIR_LEAD_WORDS = 5;   // two bold-lead paragraphs make a ladder when both leads are this short
const RUNIN_HEAD_MAX_WORDS = 80;    // an h4 runs into its paragraph when the paragraph is this short
const STACKED_RECORD_WORDS = 160;   // a record this long is stacked full-width, not gridded
const LANDSCAPE_EDITION_MAX_WORDS = 1500;   // a brief this short turns landscape with its plate
const COLUMN_WORDS = 420;           // about one column of body text beside a tall plate

// A deck is a sentence that carries the section's point, not a lead-in to a list: it ends in a
// full stop, never a colon, and it does not open with a bold lead.
function isDeck(p) {
  const w = words(p.raw);
  return w >= DECK_MIN_WORDS && w <= DECK_MAX_WORDS && !BOLD_LEAD.test(p.raw) &&
    !/:\s*$/.test(p.raw) && /[.!?]/.test(p.raw);
}

// A paragraph that introduces a figure, when it is short and says so, is set in caption style in
// its own place above the plate.
const FIGURE_LEAD = /\b(flow|figure|diagram|arrows?|edges?|sequence|state machine|ladder|below|as a (?:flow|sequence|graph))\b/i;
const isFigureLead = (p) => words(p.raw) <= 60 && (/:\s*$/.test(p.raw) || FIGURE_LEAD.test(p.raw));

// The emitter carries the state that used to be closed over directly by `structure()`
// (`sectionWords`, `sinceEntry`, `sectionHasQuote`, `pendingQuote`, `dropcapArmed`), plus the
// small set of functions every block-kind handler below needs: `emit`/`push` to place HTML,
// `considerQuote` to offer a pull-quote candidate, `paragraph` for a plain paragraph. Bundling
// them here, instead of each handler closing over its own copies, is what keeps the handlers
// callable and testable on their own.
function createEmitter(kind) {
  const out = [];
  const state = {
    sectionWords: 0,
    sinceEntry: 0,        // words since the reader last had a non-text entry point
    sectionHasQuote: false,
    pendingQuote: null,    // a pull-quote waiting to be placed one block after its source
    dropcapArmed: false,
  };

  const textWords = (html) => words(html.replace(/<[^>]+>/g, ' '));
  const emit = (html) => {
    const w = textWords(html);
    state.sectionWords += w;
    out.push({ html, full: / class="[^"]*full/.test(html.slice(0, 120)), plate: /<figure class="[^"]*plate/.test(html.slice(0, 80)), landscape: /<figure class="[^"]*plate-landscape/.test(html.slice(0, 80)), tall: /<figure class="diagram tall/.test(html.slice(0, 40)), words: w });
  };
  const push = (html, entry) => {
    emit(html);
    if (entry) state.sinceEntry = 0;
    if (state.pendingQuote) { emit(state.pendingQuote); state.pendingQuote = null; state.sinceEntry = 0; }
  };

  // The focal rule's pick: the next sentence the author chose to emphasise, verbatim, when a
  // page-turn of body text has passed with no other entry point.
  const considerQuote = (raw) => {
    if (!(kind.pullquote && !state.pendingQuote && state.sinceEntry > PULLQUOTE_GAP_WORDS && state.sectionWords > PULLQUOTE_SECTION_MIN)) return;
    const pick = [...raw.matchAll(/\*\*([^*]{20,220})\*\*/g)]
      .map((m) => m[1])
      .find((q) => words(q) >= PULLQUOTE_MIN_WORDS && words(q) <= 30 && !raw.trim().startsWith('**' + q));
    if (pick) {
      const long = words(pick) >= 24;
      state.pendingQuote = `<p class="pullquote${long && kind.columns ? ' full' : ''}">${inline(pick)}</p>`;
    }
  };

  const paragraph = (p) => {
    const w = words(p.raw);
    state.sinceEntry += w;
    const cls = [];
    if (state.dropcapArmed && kind.dropcap && w >= DROPCAP_MIN_WORDS && /^[A-Za-z]/.test(p.raw)) cls.push('dropcap');
    state.dropcapArmed = false;
    push(`<p${cls.length ? ` class="${cls.join(' ')}"` : ''}>${inline(p.raw)}</p>`);
    considerQuote(p.raw);
  };

  return { out, state, emit, push, considerQuote, paragraph };
}

// An opener starts a new section: word counters reset, its own heading is emitted, and the
// paragraph right after it becomes the deck when it reads like one. Returns the block index to
// resume from (the loop's own increment still applies on top of this, as everywhere below).
function handleOpener(b, i, blocks, kind, ctx, em, span) {
  em.state.sectionWords = 0; em.state.sinceEntry = 0; em.state.sectionHasQuote = false; em.state.pendingQuote = null;
  ctx.toc.push({ id: b.id, text: b.text, num: b.num ? b.num.replace(/[.)]$/, '') : null });
  em.emit(`<header class="opener${span}" id="${b.id}">` +
    `<span class="numeral">${b.num ? esc(b.num) : ''}</span> <h2>${inline(b.text)}</h2></header>`);
  const nxt = blocks[i + 1];
  let next = i;
  if (kind.deck && nxt && nxt.k === 'p' && isDeck(nxt)) {
    em.emit(`<p class="deck${span}">${inline(nxt.raw)}</p>`);
    next++;
  }
  em.state.dropcapArmed = true;
  return next;
}

// A heading, with two recognisers of its own: a `### Q1.` question badge, and an h4 that runs
// into a short paragraph below it as a magazine sub-head.
function handleHeading(b, i, blocks, em) {
  const q = b.level === 3 ? b.text.match(/^(Q\d+\.)\s+(.*)$/s) : null;
  const text = q ? `<span class="q-badge">${esc(q[1])}</span> ${inline(q[2])}` : inline(b.text);
  const nxt = blocks[i + 1];
  const runin = b.level === 4 && nxt && nxt.k === 'p' && words(nxt.raw) <= RUNIN_HEAD_MAX_WORDS &&
    !BOLD_LEAD.test(nxt.raw) && !(blocks[i + 2] && blocks[i + 2].k === 'figure' && isFigureLead(nxt));
  const cls = runin ? ' class="runin-head"' : q ? ' class="question"' : '';
  em.push(`<h${b.level} id="${b.id}"${cls}>${text}</h${b.level}>`, true);
}

// A paragraph: a verdict panel, a run of bold-lead paragraphs that makes a ladder, a caption
// before a figure, a lone bold lead, or plain prose — in that order of preference. Returns the
// block index to resume from, same convention as `handleOpener`.
function handleParagraph(b, i, blocks, kind, ctx, em, span) {
  // A paragraph that opens by announcing a verdict is the answer to the section: give it a
  // panel so the eye finds it without reading the section first.
  const lead = b.raw.match(BOLD_LEAD);
  if (lead && VERDICT_LEXICON.test(lead[1])) {
    const { label, sep, rest } = splitLead(b.raw);
    em.push(`<aside class="verdict${span}"><span class="verdict-label">${inline(label)}${sepHtml(sep)}</span> <p>${inline(rest)}</p></aside>`, true);
    return i;
  }

  // A run of three or more bold-lead paragraphs, each optionally followed by its own list, is
  // a ladder, not prose. The list becomes the rung's fields when every item has a lead.
  if (kind.ladder && lead) {
    const units = [];
    let j = i;
    while (blocks[j] && blocks[j].k === 'p' && BOLD_LEAD.test(blocks[j].raw) && !VERDICT_LEXICON.test(blocks[j].raw.match(BOLD_LEAD)[1])) {
      const list = blocks[j + 1] && blocks[j + 1].k === 'list' && !blocks[j + 1].taskList ? blocks[j + 1] : null;
      units.push({ p: blocks[j], list });
      j += list ? 2 : 1;
    }
    // Three make a ladder; a pair does too when both leads are short ("Performance: no.",
    // "Reliability: …") — the same shape, and the caution against false positives was the
    // three, not the pair.
    const shortPair = units.length === 2 && units.every((u) => words(splitLead(u.p.raw).label) <= LADDER_PAIR_LEAD_WORDS);
    if (units.length >= 3 || shortPair) {
      const numbered = units.every((u) => NUMBERED_LEAD.test(splitLead(u.p.raw).label));
      const html = units.map((u) => {
        const { label, sep, rest } = splitLead(u.p.raw);
        return renderRung(label, sep, rest, rungListHtml(u.list), numbered);
      }).join('');
      em.push(`<div class="ladder">${html}</div>`, true);
      return j - 1;
    }
  }

  // A short paragraph that introduces the plate is set as its caption, in its own place,
  // inside the plate's frame so the two are one unbreakable unit.
  const nxt = blocks[i + 1];
  if (nxt && nxt.k === 'figure' && isFigureLead(b)) {
    const leadHtml = `<p class="figure-lead">${inline(b.raw)}</p>`;
    const leadIn = ((Math.ceil(stripMd(b.raw).length / 100) + 0.5) * 11.5 + 8) / 72;
    em.push(renderFigure(nxt.src, ctx, kind, leadHtml, leadIn, nxt.engine), true);
    return i + 1;
  }

  // A lone bold-lead paragraph outside a ladder: the lead set in sans, so the eye catches
  // it. One paragraph, not a rung — no rule, no ground.
  if (kind.ladder && lead) {
    const { label, sep, rest } = splitLead(b.raw);
    em.state.sinceEntry += words(b.raw);
    em.state.dropcapArmed = false;
    em.push(`<p class="lead"><span class="runin-label">${inline(label)}</span>${sepHtml(sep)}${inline(rest)}</p>`);
    em.considerQuote(b.raw);
    return i;
  }

  em.paragraph(b);
  return i;
}

// A list, classified once (`classifyList`) into the shape it prints as.
function handleList(b, kind, span, em) {
  const kindOf = classifyList(b, kind);
  const itemWords = b.items.map((it) => words(it.text) + words(it.sub.map((x) => x.text).join(' ')));
  const total = itemWords.reduce((a, c) => a + c, 0);
  const longItems = (kindOf === 'runin' || kindOf === 'list') && total / itemWords.length > LONG_ITEM_WORDS;
  if (kindOf === 'cardgrid') em.push(renderCardGrid(b, span), true);
  else if (kindOf === 'fielded') em.push(renderFielded(b), true);
  else if (longItems) {
    // A list whose items run to paragraphs is prose with bullets, not a set of things the
    // eye can take in: it counts as text for the focal rule, and may lend it a sentence. It
    // is emitted in pieces so a quote can sit one item after its source, the numbering intact.
    const tag = b.ordered ? 'ol' : 'ul';
    const cls = kindOf === 'runin' ? ' class="runin"' : b.taskList ? ' class="task"' : '';
    let piece = [];
    let start = 1;
    const flushPiece = () => {
      if (!piece.length) return;
      em.push(`<${tag}${cls}${b.ordered && start > 1 ? ` start="${start}"` : ''}>${piece.join('')}</${tag}>`, false);
      start += piece.length; piece = [];
    };
    b.items.forEach((it, k) => {
      em.state.sinceEntry += itemWords[k];
      piece.push(kindOf === 'runin' ? renderRunInItem(it) : renderItems([it]));
      if (em.state.pendingQuote) flushPiece();
      em.considerQuote(it.text);
    });
    flushPiece();
  }
  else if (kindOf === 'runin') em.push(renderRunIn(b), true);
  else { em.state.sinceEntry += total; em.push(renderList(b.items, b.ordered, b.taskList ? 'task' : ''), false); }
}

// A table, classified once (`classifyTable`) into cards, a definition list, or a plain table.
function handleTable(b, kind, span, em) {
  const t = kind.cards ? classifyTable(b) : 'table';
  if (t === 'cards') em.push(renderRecordCards(b, span), true);
  else if (t === 'deflist') em.push(renderDefList(b), true);
  else {
    // A table wider than about two columns cannot shrink to a column's measure — long
    // identifiers set a min-content width it refuses to go below — so it becomes a
    // full-measure exhibit instead of overflowing into the neighbouring column.
    const widest = Math.max(0, ...[b.head, ...b.rows].flat().map((c) => String(c).length));
    const full = kind.columns && (b.cols >= 3 || widest > 90);
    em.push(renderTable(b, full ? ' full' : ''), true);
  }
}

function handleCode(b, kind, em) {
  // A code block whose lines are long wraps on every line inside a column, which is
  // unreadable. Give it the full measure.
  const longest = Math.max(0, ...b.body.split('\n').map((l) => l.length));
  const full = kind.columns && longest > 58;
  em.push(`<pre${full ? ' class="full"' : ''}><code>${highlight(b.body, b.lang)}</code></pre>`, true);
}

function handleQuote(b, kind, ctx, span, em) {
  const inner = structure(b.inner, { ...kind, deck: false, pullquote: false, dropcap: false, ladder: false, cards: false, columns: false }, { ...ctx, toc: [] }).map((x) => x.html).join('\n');
  if (b.colophon && kind.colophon) em.push(`<div class="colophon${span}">${inner}</div>`);
  else { em.state.sectionHasQuote = true; em.push(`<blockquote${words(inner.replace(/<[^>]+>/g, ' ')) > 80 ? ' class="long"' : ''}>${inner}</blockquote>`); }
}

// Runs over the whole block list once it is known, because the deck needs the paragraph after an
// opener, a ladder needs a run, and the pull-quote needs to know how long it has been since the
// reader last had something other than body text to land on. Every transform re-containers text:
// nothing is rewritten, reordered, trimmed or summarised. A pull-quote is a duplicate and the
// sentence stays in the prose; card labels are the table's own header words. The loop below is a
// dispatch table; each block kind's own decision lives in its handler above.
function structure(blocks, kind, ctx) {
  const span = kind.columns ? ' full' : '';
  const em = createEmitter(kind);

  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    switch (b.k) {
      case 'opener': i = handleOpener(b, i, blocks, kind, ctx, em, span); continue;
      case 'h': handleHeading(b, i, blocks, em); continue;
      case 'p': i = handleParagraph(b, i, blocks, kind, ctx, em, span); continue;
      case 'list': handleList(b, kind, span, em); continue;
      case 'table': handleTable(b, kind, span, em); continue;
      case 'code': handleCode(b, kind, em); continue;
      case 'figure': em.push(renderFigure(b.src, ctx, kind, '', 0, b.engine), true); continue;
      case 'quote': handleQuote(b, kind, ctx, span, em); continue;
      case 'hr': em.push('<hr>'); continue;
      default: continue;
    }
  }
  if (em.state.pendingQuote) em.emit(em.state.pendingQuote);
  return em.out;
}

// Lay the blocks out. In a columned edition every run of column-flow blocks becomes its own
// multicol segment and every full-measure block sits between segments. Segments balance their
// columns, except the one that runs into a full-page plate: given enough text to fill more than
// a column, it fills the left column to the foot of the page and lets the right column end
// short, which is how a magazine page ends before a plate — rather than two truncated columns
// over a band of white.

// Words of body text a landscape page has room for beneath a plate of the given height: about
// 65 words to the inch at 10/13.5 across a 44em measure, less the plate's own chrome.
const landscapeBudget = (plateIn) => Math.max(0, Math.floor((LANDSCAPE.boxIn - plateIn - 0.7) * 65));

function layout(blocks, kind) {
  const parts = [];
  let seg = [];
  let segWords = 0;
  const flush = (next) => {
    if (!seg.length) return;
    const cols = kind.columns || (kind.proseColumns && segWords >= PROSE_COLUMNS_MIN_WORDS);
    parts.push(cols ? `<section class="columns">\n${seg.join('\n')}\n</section>` : seg.join('\n'));
    seg = []; segWords = 0;
  };
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    if (kind.proseColumns && !b.full && EXHIBIT_HTML.test(b.html)) {
      // In a dashboard an exhibit ends the prose run and takes the whole measure itself.
      flush(b); parts.push(b.html); continue;
    }
    if (b.landscape) {
      // The plate takes a landscape page; the blocks after it fill the rest of that page in a
      // single column, in their own order, so the sheet the reader turns is not mostly white.
      flush(b);
      const h = Number((b.html.match(/data-h="([\d.]+)"/) || [])[1] || LANDSCAPE.boxIn);
      let budget = landscapeBudget(h);
      const page = [b.html];
      while (budget > 60 && blocks[i + 1] && !blocks[i + 1].plate && !/^<header class="opener/.test(blocks[i + 1].html) && blocks[i + 1].words <= budget) {
        i++;
        page.push(blocks[i].html);
        budget -= blocks[i].words;
      }
      parts.push(`<section class="plate-page flow">\n${page.join('\n')}\n</section>`);
      continue;
    }
    if (!kind.columns && b.tall) {
      // A tall column plate in a single-column edition: it takes the left column of a local
      // two-column section and the text that follows flows beside it, in its own order.
      flush(b);
      let budget = COLUMN_WORDS;
      const page = [b.html];
      while (budget > 40 && blocks[i + 1] && !blocks[i + 1].full && !blocks[i + 1].tall && !/^<header class="opener/.test(blocks[i + 1].html) && blocks[i + 1].words <= budget) {
        i++;
        page.push(blocks[i].html);
        budget -= blocks[i].words;
      }
      parts.push(`<section class="columns local">\n${page.join('\n')}\n</section>`);
      continue;
    }
    if (b.full) { flush(b); parts.push(b.html); }
    else { seg.push(b.html); segWords += b.words; }
  }
  flush(null);
  return parts.join('\n');
}

// ---------------------------------------------------------------- mermaid

// Syntax colour for a code block, the way an editor shows a file it opens: highlight.js from the
// global npm tree, classes only (the print palette lives in the stylesheet). A fence with no
// language, or an unknown one, is left plain; no highlight.js on the machine means plain too.
let hljs;
function highlight(body, lang) {
  if (hljs === undefined) {
    try {
      const root = execFileSync('npm', ['root', '-g'], { encoding: 'utf8', shell: true }).trim();
      hljs = require(path.join(root, 'highlight.js'));
    } catch { hljs = null; }
  }
  const name = (lang || '').toLowerCase();
  if (!hljs || !name || !hljs.getLanguage(name)) return esc(body);
  return hljs.highlight(body, { language: name, ignoreIllegals: true }).value;
}

let mmdcChecked = false;
let mmdcPath = null;

function findMmdc() {
  if (mmdcChecked) return mmdcPath;
  mmdcChecked = true;
  for (const cmd of ['mmdc', 'mmdc.cmd']) {
    try {
      // shell: true is required on Windows, where mmdc is a .cmd shim that Node refuses to
      // execFile directly; harmless elsewhere.
      execFileSync(cmd, ['--version'], { stdio: 'ignore', shell: process.platform === 'win32' });
      mmdcPath = cmd;
      return mmdcPath;
    } catch { /* not present */ }
  }
  return null;
}

function normaliseMermaid(src, ctx) {
  let s = src;

  // A %%{init: ...}%% directive must sit on ONE line; wrapped, mermaid answers "Syntax error".
  s = s.replace(/%%\{[\s\S]*?\}%%/g, (m) => m.replace(/\s*\n\s*/g, ' '));

  // A semicolon closes a statement in mermaid's grammar, so one inside a sequence-diagram
  // message is read as a second statement and the diagram fails. `#59;` is mermaid's own entity
  // for a literal semicolon: the rendered label carries exactly the character the source has.
  if (/^\s*sequenceDiagram\b/m.test(s)) {
    s = s.split('\n').map((line) => {
      if (/^\s*%%/.test(line)) return line;
      const colon = line.indexOf(':');
      if (colon < 0) return line;
      return line.slice(0, colon + 1) + line.slice(colon + 1).replace(/;/g, '#59;');
    }).join('\n');
  }

  return s;
}

// The page geometry the plate rules are computed against, per orientation, derived from
// assets/geometry.json — the one home of the page's numbers, which magazine.css is pinned to by
// tests/geometry.test.mjs. The diagram skill never reads it: it asks placementFor (--place).
function pageGeometry(orientation) {
  const g = GEOMETRY[orientation];
  const m = g.marginIn;
  const measureIn = g.pageIn.width - 2 * m.side;
  return {
    measureIn,                                                       // the page less its side margins
    boxIn: g.pageIn.height - m.top - m.bottom - GEOMETRY.safetyIn,   // the content box, less a hair so a plate sized to it never tips over
    columnIn: (measureIn - GEOMETRY.columnGapPx / GEOMETRY.pxPerIn) / 2 - GEOMETRY.figureInsetIn,  // a column less the figure's inset
    sideIn: g.sideIn,                                                // the widest a turned plate may float beside a single column
    marginIn: m,
  };
}
const PORTRAIT = pageGeometry('portrait');
const LANDSCAPE = pageGeometry('landscape');
const PAGE = {
  inflowCapIn: 0.6,        // an in-flow plate never takes more than 60% of a page
  labelFloorPt: 7,         // no label prints smaller than this without a warning
  labelTargetPt: 8,        // the size a placement is chosen for when one can reach it
  labelCapPt: 10,          // no label prints larger than this: body size (--label-cap overrides)
};
const CSS_PX_TO_PT = 0.75; // 96 CSS px/in / 72 pt/in — mermaid's theme font size is in CSS px

function svgSize(svg) {
  const vb = svg.match(/viewBox="\s*[-\d.eE+]+\s+[-\d.eE+]+\s+([\d.eE+]+)\s+([\d.eE+]+)\s*"/);
  if (!vb) return null;
  const w = Number(vb[1]); const h = Number(vb[2]);
  return w > 0 && h > 0 ? { w, h } : null;
}

// The label size mermaid used, in CSS px: the theme's fontSize, which is what every node and
// message label is set at. (Sniffing the SVG is unreliable: sequence diagrams size their text
// from a stylesheet block and carry only the small sequence numbers inline.)
let themeLabelPx = null;
function labelPx() {
  if (themeLabelPx) return themeLabelPx;
  themeLabelPx = 16;
  try {
    const t = JSON.parse(readFileSync(MERMAID_THEME, 'utf8'));
    const fs = String((t.themeVariables || {}).fontSize || '16px');
    const n = Number(fs.replace(/px$/, ''));
    if (n > 0) themeLabelPx = n;
  } catch { /* the default */ }
  return themeLabelPx;
}

// Strip mmdc's sizing (width="100%" plus an inline max-width) so the builder can set the printed
// size explicitly, in inches, and know at build time how tall every plate is.
function fitSvg(svg, wIn, hIn) {
  return svg.replace(/<svg\b[^>]*>/, (tag) => {
    const stripped = tag
      .replace(/\s(?:width|height)="[^"]*"/g, '')
      .replace(/\sstyle="[^"]*"/, '');
    return stripped.replace(/<svg\b/, `<svg style="width:${wIn.toFixed(2)}in;height:${hIn.toFixed(2)}in"`);
  });
}

// Where a plate goes, and at what size. Tried in order, first fit wins:
//   column      — narrower than a column at the in-flow cap: stays in the column flow
//   inflow      — full measure, at most 60% of a page tall, shares the page with text
//   tall        — a column plate at the full page height, prose flowing in the other column
//   side        — a strip-shaped plate (three times wider than tall) turned on its side and
//                 floated at the left of a single column, prose flowing beside it
//   plate       — full measure at the full page height
//   plate-landscape — a landscape page of its own, only for a plate tall enough to earn a sheet
// A placement is chosen when its labels reach the 8pt target; failing that, the 7pt floor;
// failing that, the largest labels available (a column plate wins a near tie: it costs no
// crater). Below the floor the build warns: a plate the reader cannot read is never hidden.
const FIGURE_CHROME_IN = 0.5;       // label, padding, rules and the svg's margin, measured; a plate has no margin of its own
const LANDSCAPE_MIN_SHARE = 0.4;    // a landscape sheet is earned by a plate this tall, or taller
const STRIP_ASPECT = 3;             // wider than this, relative to height, is a strip

function placePlate(size, labelPx, kind, extraIn = 0) {
  const pxPerIn = GEOMETRY.pxPerIn;
  const G = kind.landscape ? LANDSCAPE : PORTRAIT;
  const chrome = FIGURE_CHROME_IN + extraIn;
  const labelPt = (scale) => labelPx * CSS_PX_TO_PT * scale;
  const fit = (wIn, hIn) => Math.min(1, wIn * pxPerIn / size.w, (hIn - chrome) * pxPerIn / size.h);
  // A turned plate: its width runs down the page, its height across.
  const fitTurned = (wIn, hIn) => Math.min(1, (hIn - chrome) * pxPerIn / size.w, wIn * pxPerIn / size.h);
  const strip = size.w / size.h >= STRIP_ASPECT;
  const cap = G.boxIn * PAGE.inflowCapIn;
  const options = [];
  if (kind.columns) options.push({ cls: 'diagram', scale: fit(G.columnIn, cap) });
  options.push({ cls: 'diagram full', scale: fit(G.measureIn, cap) });
  if (kind.columns) options.push({ cls: 'diagram tall', scale: fit(G.columnIn, G.boxIn) });
  if (strip && kind.columns) options.push({ cls: 'diagram tall turned', scale: fitTurned(G.columnIn, G.boxIn), turned: true });
  if (strip && !kind.columns) options.push({ cls: 'diagram tall turned', scale: fitTurned(G.columnIn, G.boxIn), turned: true });
  options.push({ cls: 'diagram full plate', scale: fit(G.measureIn, G.boxIn) });
  // A landscape sheet inside a portrait edition, only for a plate tall enough to earn one.
  const landscape = kind.landscape ? null
    : { cls: 'diagram full plate plate-landscape', scale: fit(LANDSCAPE.measureIn, LANDSCAPE.boxIn), landscape: true };
  if (landscape && size.h * landscape.scale / pxPerIn >= LANDSCAPE_MIN_SHARE * LANDSCAPE.boxIn) options.push(landscape);
  const at = (min) => options.find((o) => labelPt(o.scale) >= min);
  let pick = at(PAGE.labelTargetPt) || at(PAGE.labelFloorPt);
  if (!pick) {
    const all = landscape && !options.includes(landscape) ? options.concat(landscape) : options;
    const best = all.reduce((a, b) => (b.scale > a.scale ? b : a));
    const tall = all.find((o) => o.cls === 'diagram tall');
    pick = tall && tall.scale >= best.scale * 0.95 ? tall : best;
  }
  // A plate is sized for its labels, not for the room on the page: past the cap (body size by
  // default) a bigger picture says nothing more and costs the page the text that would have
  // sat under it. Two 12pt sequence plates with a sentence between once took a page each.
  const capScale = PAGE.labelCapPt / (labelPx * CSS_PX_TO_PT);
  if (pick.scale > capScale) pick = { ...pick, scale: capScale };
  const wIn = size.w * pick.scale / pxPerIn;
  const hIn = size.h * pick.scale / pxPerIn;
  return { ...pick, labelPt: labelPt(pick.scale), wIn, hIn, boxW: pick.turned ? hIn : wIn, boxH: pick.turned ? wIn : hIn };
}

// ---------------------------------------------------------------- palette
//
// The edition's named colors have one home: the stylesheet's :root. The plates take theirs from
// it too — mermaid-theme.json names every color as var(--name), resolved here — so --accent,
// which overrides :root, recolors the plates as well as the page.

const ACCENT_BG_ALPHA = '1f';   // a custom accent's ground: the accent at this alpha over paper

function paletteOf(css, accent = null) {
  const root = ((css.match(/:root\s*\{([^}]*)\}/) || [])[1] || '').replace(/\/\*[\s\S]*?\*\//g, '');
  const vars = {};
  for (const m of root.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) vars[m[1]] = m[2].trim();
  if (accent) {
    vars.accent = accent;
    vars['accent-bg'] = overPaper(accent, parseInt(ACCENT_BG_ALPHA, 16) / 255);
  }
  return vars;
}

// A translucent color laid on white paper, as the opaque hex a renderer can derive shades from.
function overPaper(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  const mix = (c) => Math.round(c * alpha + 255 * (1 - alpha)).toString(16).padStart(2, '0');
  return `#${mix(n >> 16)}${mix((n >> 8) & 255)}${mix(n & 255)}`;
}

function named(palette, name) {
  if (!Object.hasOwn(palette, name)) throw new Error(`the stylesheet's :root does not define --${name}, which the plates use`);
  return palette[name];
}

// The mermaid config the plates render with: mermaid-theme.json with its var(--name) colors
// resolved against the palette.
function mermaidConfig(palette) {
  const resolve = (v) => {
    if (typeof v === 'string') return v.replace(/var\(--([\w-]+)\)/g, (_, name) => named(palette, name));
    if (Array.isArray(v)) return v.map(resolve);
    if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, resolve(x)]));
    return v;
  };
  return resolve(JSON.parse(readFileSync(MERMAID_THEME, 'utf8')));
}

// Written once per build (per palette), where mmdc can read it.
function mermaidConfigFile(shared) {
  if (!shared.mermaidConfigFile) {
    const text = JSON.stringify(mermaidConfig(shared.palette), null, 2);
    const file = path.join(mkdtempWorkdir(), `mermaid-config-${createHash('sha1').update(text).digest('hex').slice(0, 12)}.json`);
    writeFileSync(file, text, 'utf8');
    shared.mermaidConfigFile = file;
  }
  return shared.mermaidConfigFile;
}

const svgCache = new Map();
function renderMermaidSvg(src, n, suffix, configFile) {
  const key = `${configFile}\n${src}`;
  if (svgCache.has(key)) return svgCache.get(key);
  const dir = mkdtempWorkdir();
  const inFile = path.join(dir, `d${n}${suffix}.mmd`);
  const outFile = path.join(dir, `d${n}${suffix}.svg`);
  writeFileSync(inFile, src, 'utf8');
  try {
    execFileSync(findMmdc(), ['-i', inFile, '-o', outFile, '-b', 'transparent', '-c', configFile], {
      stdio: ['ignore', 'ignore', 'pipe'],
      encoding: 'utf8',
      shell: process.platform === 'win32',
    });
  } catch (e) {
    const why = String(e.stderr || e.message).split('\n').map((l) => l.trim()).filter(Boolean).slice(0, 3).join(' / ');
    throw new Error(`figure ${n}: mmdc could not render it — ${why}`);
  }
  const svg = readFileSync(outFile, 'utf8').replace(/<\?xml[^>]*\?>/, '');
  svgCache.set(key, svg);
  return svg;
}

let dotChecked = false;
let dotPath = null;

function findDot() {
  if (dotChecked) return dotPath;
  dotChecked = true;
  for (const cmd of ['dot', DOT_FALLBACK]) {
    try {
      execFileSync(cmd, ['-V'], { stdio: 'ignore' });
      dotPath = cmd;
      return dotPath;
    } catch { /* not present */ }
  }
  return null;
}

// Graphviz writes its SVG in points, with the font size on every text run; the smallest run is
// the label size, in the same unit as the viewBox, which is all the plate rules need.
function dotLabelSize(svg) {
  const sizes = [...svg.matchAll(/font-size="([\d.]+)"/g)].map((m) => Number(m[1])).filter((n) => n > 0);
  return sizes.length ? Math.min(...sizes) : 14;
}

function renderDotSvg(src, n, suffix) {
  if (svgCache.has(src)) return svgCache.get(src);
  const dir = mkdtempWorkdir();
  const inFile = path.join(dir, `d${n}${suffix}.dot`);
  const outFile = path.join(dir, `d${n}${suffix}.svg`);
  writeFileSync(inFile, src, 'utf8');
  try {
    execFileSync(findDot(), ['-Tsvg', '-o', outFile, inFile], { stdio: ['ignore', 'ignore', 'pipe'], encoding: 'utf8' });
  } catch (e) {
    const why = String(e.stderr || e.message).split('\n').map((l) => l.trim()).filter(Boolean).slice(0, 3).join(' / ');
    throw new Error(`figure ${n}: dot could not render it — ${why}`);
  }
  const svg = readFileSync(outFile, 'utf8').replace(/<\?xml[^>]*\?>/, '').replace(/<!DOCTYPE[^>]*>/, '');
  svgCache.set(src, svg);
  return svg;
}

// Colour is a participant's identity, held across the edition: the same name gets the same hue
// on every sequence plate. Hues in order of first sight; amber comes fifth so a note (amber) is
// never the colour of the actor it annotates on a four-actor plate. A new name takes a hue no
// other actor on its own plate has, the least-used across the edition first, so a late plate of
// new names is coloured like the first one; ink-soft only when a plate has more actors than hues.
// Lifelines, arrows and message text stay ink. Keyed by the printed label, not the alias, so
// "ExecutionBroker" is one colour whatever a figure calls it.
const ACTOR_HUE_NAMES = ['blue', 'green', 'violet', 'teal', 'amber', 'orange'];

// The hues, built once per build from the palette: identity matters, since an actor keeps the
// hue object it was first given across every plate.
function actorHues(shared) {
  if (!shared.hues) {
    const p = shared.palette;
    shared.hues = {
      hues: ACTOR_HUE_NAMES.map((h) => ({ fill: named(p, `${h}-bg`), stroke: named(p, h) })),
      rest: { fill: named(p, 'shell'), stroke: named(p, 'ink-soft') },
    };
  }
  return shared.hues;
}

function colourActors(svg, n, ctx) {
  const { hues: ACTOR_HUES, rest: ACTOR_HUE_REST } = actorHues(ctx.shared);
  const id = `fig${n}-svg`;
  let out = svg.replace(/my-svg/g, id);
  const rules = [];
  const actors = new Map();   // alias -> printed label, in order of appearance on this plate
  const re = /<rect\b[^>]*\bname="([^"]+)"[^>]*class="actor[^"]*"[^>]*\/>\s*<text\b[^>]*>([\s\S]*?)<\/text>/g;
  for (const m of out.matchAll(re)) {
    if (actors.has(m[1])) continue;
    actors.set(m[1], m[2].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim() || m[1]);
  }
  const onPlate = new Set([...actors.values()].map((l) => ctx.actorHues.get(l)).filter(Boolean));
  for (const label of actors.values()) {
    if (ctx.actorHues.has(label)) continue;
    const uses = new Map(ACTOR_HUES.map((h) => [h, 0]));
    for (const h of ctx.actorHues.values()) if (uses.has(h)) uses.set(h, uses.get(h) + 1);
    const free = ACTOR_HUES.filter((h) => !onPlate.has(h)).sort((a, b) => uses.get(a) - uses.get(b));
    const hue = free[0] || ACTOR_HUE_REST;
    ctx.actorHues.set(label, hue);
    onPlate.add(hue);
  }
  for (const [alias, label] of actors) {
    const hue = ctx.actorHues.get(label);
    rules.push(`#${id} rect.actor[name="${alias.replace(/"/g, '&quot;')}"]{fill:${hue.fill};stroke:${hue.stroke};}`);
  }
  if (!rules.length) return out;
  return out.replace(/<\/svg>\s*$/, `<style>${rules.join('')}</style></svg>`);
}

// The other direction of a Graphviz graph: rankdir, declared or defaulted to TB.
function flipDotDirection(src) {
  const m = src.match(/rankdir\s*=\s*"?(TB|LR|BT|RL)"?/);
  if (m) return src.replace(m[0], `rankdir=${/^(TB|BT)$/.test(m[1]) ? 'LR' : 'TB'}`);
  return src.replace(/^(\s*(?:strict\s+)?di?graph\b[^{]*\{)/m, '$1 rankdir=LR;');
}

// The other direction of a flowchart: a wide TB graph with subgraphs side by side is often a
// tall LR one, and the reverse. Diagrams are the one thing the edition may re-lay-out.
function flipDirection(src) {
  const m = src.match(/^(\s*(?:flowchart|graph)\s+)(TB|TD|LR|RL|BT)\b/m);
  if (!m) return null;
  const to = /^(TB|TD|BT)$/.test(m[2]) ? 'LR' : 'TD';
  return src.replace(m[0], `${m[1]}${to}`);
}

function renderFigure(rawSrc, ctx, kind, leadHtml = '', leadIn = 0, engine = 'mermaid') {
  const dot = engine === 'graphviz';
  const src = dot ? rawSrc : normaliseMermaid(rawSrc, ctx);
  const n = ctx.figure++;
  const label = `${leadHtml}<span class="figure-label">Figure ${n}</span>`;

  if (ctx.mermaid === 'code') {
    return `<figure class="full">${label}<pre><code>${esc(src)}</code></pre></figure>`;
  }
  if (ctx.mermaid === 'cdn') {
    ctx.needsMermaidCdn = true;
    return `<figure class="diagram full">${label}<pre class="mermaid">${esc(src)}</pre></figure>`;
  }

  if (dot && !findDot()) {
    throw new Error('dot is not on PATH and the document has a Graphviz diagram. Install it once: winget install Graphviz.Graphviz');
  }
  if (!dot && !findMmdc()) {
    throw new Error('mmdc is not on PATH and the document has a mermaid diagram. Install it once: npm i -g @mermaid-js/mermaid-cli (or pass --mermaid cdn for a screen-only preview).');
  }
  const attempt = (source, suffix) => {
    const svg = dot ? renderDotSvg(source, n, suffix) : renderMermaidSvg(source, n, suffix, mermaidConfigFile(ctx.shared));
    const size = svgSize(svg);
    const label = dot ? dotLabelSize(svg) : labelPx();
    return size ? { svg, size, place: placePlate(size, label, kind, leadIn) } : { svg, size: null };
  };
  let best = attempt(src, '');
  if (!best.size) {
    ctx.warnings.push(`figure ${n}: the SVG has no viewBox; printed at the full measure`);
    return `<figure class="diagram full">${label}${best.svg}</figure>`;
  }
  if (best.place.labelPt < PAGE.labelTargetPt && ctx.diagramDirection !== 'keep') {
    const flipped = dot ? flipDotDirection(src) : flipDirection(src);
    if (flipped) {
      const other = attempt(flipped, '-flip');
      if (other.size && other.place.labelPt >= best.place.labelPt * 1.15) { best = other; best.flipped = true; }
    }
  }
  const { place, size } = best;
  let svg = fitSvg(best.svg, place.wIn, place.hIn);
  if (!dot && /^\s*sequenceDiagram\b/m.test(src)) svg = colourActors(svg, n, ctx);
  if (place.turned) svg = `<div class="turn" style="width:${place.boxW.toFixed(2)}in;height:${place.boxH.toFixed(2)}in">${svg}</div>`;
  ctx.figures.push({ n, ...place, native: size, flipped: Boolean(best.flipped) });
  if (place.labelPt < PAGE.labelFloorPt) {
    ctx.warnings.push(`figure ${n}: labels print at ${place.labelPt.toFixed(1)}pt even as a ${place.cls.includes('landscape') ? 'landscape' : 'portrait'} plate in either direction (native ${Math.round(size.w)}x${Math.round(size.h)}); the diagram needs fewer nodes per rank or shorter labels to reach ${PAGE.labelFloorPt}pt`);
  }
  return `<figure class="${place.cls}" data-h="${place.boxH.toFixed(2)}">${label}${svg}</figure>`;
}

function mkdtempWorkdir() {
  const dir = path.join(os.tmpdir(), 'magazine-build');
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

// ---------------------------------------------------------------- fidelity
//
// The edition is verbatim by construction; this proves it. Every non-blank source line, with its
// markdown syntax removed, must appear in the edition's text with its tags removed. Table rows are
// checked cell by cell (a record card interleaves header words between cells). Mermaid fences are
// skipped: they become pictures. Anything missing is a build failure.

const ENT = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&nbsp;': ' ' };
const decode = (s) => s.replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (m) => ENT[m]);

function normalise(s) {
  return String(s)
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[*_`~\\]/g, '')
    .replace(/[\s ]+/g, ' ')
    .trim()
    .toLowerCase();
}

function editionText(html) {
  return normalise(decode(html
    .replace(/<style[\s\S]*?<\/style>/g, ' ')
    .replace(/<script[\s\S]*?<\/script>/g, ' ')
    .replace(/<svg[\s\S]*?<\/svg>/g, ' ')
    .replace(/<\/(?:p|li|dd|dt|td|th|h[1-6]|div|pre|section|article|aside|header|figure|blockquote|tr|ul|ol|dl|nav|main)>|<br\s*\/?>/g, '\n')
    .replace(/<[^>]+>/g, '')));
}

// Every cell of every table in the edition, as its own normalised text — never the whole document
// blended into one string. A table cell is checked against these, not against prose: a short
// value like "Yes" or "EU" is otherwise a coin flip to find by accident somewhere else in the
// edition (a real edition once dropped a whole row and still passed, because its cells' letters
// happened to occur inside unrelated words). A plain table keeps its cells as `<td>`/`<th>`; a
// definition list and a record card re-container the same cells as `<dt>`/`<dd>` pairs, a record
// card's own first column as its `<h5 class="card-title">`, and both renderers repeat the header
// row once as `<span>`s inside their own head block — all of it is still the source table's cells.
function extractCells(html) {
  const cells = [];
  const push = (re, group) => {
    let m;
    while ((m = re.exec(html))) cells.push(normalise(decode(m[group].replace(/<[^>]+>/g, ''))));
  };
  push(/<(td|th|dt|dd)\b[^>]*>([\s\S]*?)<\/\1>/g, 2);
  push(/<h5 class="card-title">([\s\S]*?)<\/h5>/g, 1);
  const headBlock = /<div class="(?:deflist-head|cards-head[^"]*)">([\s\S]*?)<\/div>/g;
  let hm;
  while ((hm = headBlock.exec(html))) {
    const spanRe = /<span>([\s\S]*?)<\/span>/g;
    let sm;
    while ((sm = spanRe.exec(hm[1]))) cells.push(normalise(decode(sm[1].replace(/<[^>]+>/g, ''))));
  }
  return cells;
}

function verifyEdition(sources, html) {
  const text = editionText(html);
  const cells = extractCells(html);
  const missing = [];
  for (const { file, md } of sources) {
    const lines = splitLines(md);
    // Fence markers, and every line of a diagram (it became a picture), are not looked for; a
    // code sample's lines are, verbatim.
    const skip = new Set();
    const code = new Set();
    for (const f of scanFences(lines)) {
      skip.add(f.start).add(f.end);
      for (let k = f.start + 1; k < f.end; k++) (f.engine ? skip : code).add(k);
    }
    lines.forEach((raw, idx) => {
      if (skip.has(idx)) return;
      const inCode = code.has(idx);
      if (!inCode && /^\s*<!--.*-->\s*$/.test(raw)) return;
      let line = raw;
      if (!inCode) {
        line = line.replace(/^\s*#{1,6}\s+/, '').replace(/\s+#+\s*$/, '')
          .replace(/^\s*>\s?/, '')
          .replace(/^\s*([-*+]|\d+[.)])\s+(\[[ xX]\]\s+)?/, '');
        if (/^\s*([-*_])\1{2,}\s*$/.test(line)) return;
        if (/^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(line)) return;          // table rule row
        if (/^\s*\|/.test(line)) {
          line.trim().replace(/^\||\|$/g, '').split(/(?<!\\)\|/).forEach((cell) => {
            const c = normalise(cell.replace(/\\\|/g, '|'));
            if (c && !cells.some((ct) => ct.includes(c))) missing.push({ file, line: idx + 1, text: cell.trim() });
          });
          return;
        }
      }
      const n = normalise(line);
      if (n && !text.includes(n)) missing.push({ file, line: idx + 1, text: raw.trim() });
    });
  }
  return missing;
}

// The masthead date: the reader's own local calendar day, not UTC — an edition built in the
// evening must not print tomorrow's date. `timeZone` is a seam for tests; a real build always
// takes the system's own zone (the default when it is omitted).
function printedDate(now = new Date(), timeZone = undefined) {
  return now.toLocaleDateString('en-CA', timeZone ? { timeZone } : undefined);
}

// ---------------------------------------------------------------- assembly

function build(opts) {
  // Scoped to this call: a custom label cap applies for one build, not every build after it in
  // the same process.
  if (opts.labelCap) PAGE.labelCapPt = opts.labelCap;
  const sources = opts.inputs.map((file) => {
    if (!existsSync(file)) throw new Error(`no such file: ${file}`);
    return { file, md: readFileSync(file, 'utf8') };
  });

  // Parse everything first: the kind is decided from the whole edition's shape.
  const docs = sources.map((s) => {
    const pctx = { h1: null, seenSection: false };
    const blocks = parseBlocks(s.md, pctx);
    return { ...s, blocks, h1: pctx.h1, stats: docStats(blocks) };
  });
  const stats = docs.reduce((a, d) => ({
    words: a.words + d.stats.words, proseWords: a.proseWords + d.stats.proseWords, exhibitWords: a.exhibitWords + d.stats.exhibitWords,
    maxCols: Math.max(a.maxCols, d.stats.maxCols), h2: a.h2 + d.stats.h2,
    quotes: a.quotes + d.stats.quotes, quoteWords: a.quoteWords + d.stats.quoteWords, figures: a.figures + d.stats.figures,
  }), { words: 0, proseWords: 0, exhibitWords: 0, quoteWords: 0, maxCols: 0, h2: 0, quotes: 0, figures: 0 });

  const kindName = opts.kind || inferKind(stats);
  const kind = {
    ...KINDS[kindName],
    columns: opts.columns === null ? KINDS[kindName].columns : opts.columns,
    serif: opts.serif === null ? KINDS[kindName].serif : opts.serif,
  };
  let landscape = Boolean(opts.landscape) || stats.maxCols >= WIDE_TABLE_COLS;
  if (landscape) kind.columns = false;
  kind.landscape = landscape;
  // A document dense with the author's own quotations should not shout each one from a tinted
  // panel, and has no room for pull-quotes competing with them.
  const quietQuotes = stats.quotes > 0 && (stats.words / stats.quotes < 400 || stats.quoteWords / Math.max(1, stats.words) > 0.2);
  if (quietQuotes) kind.pullquote = false;

  const css = readFileSync(opts.css ? opts.css : DEFAULT_CSS, 'utf8');
  const ctx = {
    toc: [], figure: 1, figures: [], mermaid: opts.mermaid, warnings: [],
    needsMermaidCdn: false, diagramDirection: opts.diagramDirection || 'auto', actorHues: new Map(),
    // One per build, shared by every document's copy of ctx: the palette and what is derived from it.
    shared: { palette: paletteOf(css, opts.accent), hues: null, mermaidConfigFile: null },
  };

  const render = (d) => {
    const docCtx = { ...ctx, toc: [], warnings: [], figures: [] };
    const blocks = structure(d.blocks, kind, docCtx);
    return { docCtx, blocks };
  };
  // A short single-column document whose plate needs a landscape sheet is better as a landscape
  // edition altogether: rendered again with the landscape geometry, the plate sits in the flow.
  if (!landscape && !kind.columns && stats.words < LANDSCAPE_EDITION_MAX_WORDS && stats.figures) {
    const probe = docs.map(render);
    if (probe.some((r) => r.docCtx.figures.some((f) => f.landscape))) {
      landscape = true; kind.landscape = true;
      ctx.figure = 1;
    }
  }

  const sections = docs.map((d, idx) => {
    const title = d.h1 || path.basename(d.file, path.extname(d.file));
    const id = slug(title);
    const { docCtx, blocks } = render(d);
    const html = layout(blocks, kind);
    ctx.figure = docCtx.figure;
    ctx.figures = ctx.figures.concat(docCtx.figures);
    ctx.needsMermaidCdn = ctx.needsMermaidCdn || docCtx.needsMermaidCdn;
    ctx.warnings.push(...docCtx.warnings);
    if (docs.length > 1) ctx.toc.push({ id, text: title, doc: true, sections: docCtx.toc });
    else ctx.toc.push(...docCtx.toc);
    return { file: d.file, title, id, html, first: idx === 0 };
  });

  const title = opts.title || sections[0].title;
  const showToc = opts.toc !== null ? opts.toc
    : kind.toc === 'auto' ? (sections.length > 1 || stats.h2 >= 6) : Boolean(kind.toc);
  const accentRule = opts.accent ? `\n:root { --accent: ${opts.accent}; --accent-bg: ${opts.accent}${ACCENT_BG_ALPHA}; }\n` : '';

  // The folio. A @page margin box cannot read the document, and the builder is the only place
  // that knows this edition's title, so it is written out literally here.
  const cssString = (s) => `"${String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
  const shortTitle = (s, max = 58) => {
    const t = String(s).trim();
    if (t.length <= max) return t;
    const cut = t.slice(0, max);
    return cut.slice(0, Math.max(cut.lastIndexOf(' '), max - 12)).replace(/[\s,;:.–—-]+$/, '') + '…';
  };
  const folio = `\n@media print { @page { @bottom-right { content: ${cssString(shortTitle(title) + '  ·  ')} counter(page); } } }\n`;
  // A landscape edition's page box is what LANDSCAPE in the plate geometry assumes: 0.4in sides
  // and top, 0.45in below for the folio.
  const pageSize = landscape ? '\n@media print { @page { size: letter landscape; margin: 0.4in 0.4in 0.45in; } }\n' : '';

  const date = printedDate();
  const bodyClass = [
    `kind-${kindName}`,
    kind.serif ? 'serif-body' : 'sans-body',
    kind.columns ? 'columned' : 'single',
    landscape ? 'landscape' : '',
    quietQuotes ? 'quiet-quotes' : '',
  ].filter(Boolean).join(' ');

  const tocEntry = (t) => `<li><span class="toc-num">${t.num ? esc(t.num) : ''}</span><a href="#${t.id}">${inline(t.text)}</a></li>`;
  const tocHtml = showToc
    ? `<nav class="toc"><p class="toc-label">Contents</p>` +
      (sections.length > 1
        ? ctx.toc.map((d) => `<div class="toc-doc"><a href="#${d.id}">${esc(d.text)}</a><ol>${d.sections.map(tocEntry).join('')}</ol></div>`).join('')
        : `<ol>${ctx.toc.map(tocEntry).join('')}</ol>`) +
      `</nav>`
    : '';

  const bodyHtml = sections.map((s) => {
    const heading = sections.length > 1
      ? `<header class="opener doc-start full${s.first ? ' first' : ''}" id="${s.id}"><span class="numeral"></span> <h2>${esc(s.title)}</h2></header>`
      : '';
    return heading + s.html;
  }).join('\n');

  const kicker = opts.kicker || kind.kicker;
  const byline = [`Printed ${date}`, sections.length > 1 ? `${sections.length} documents` : null].filter(Boolean);
  const masthead = `<header class="masthead ${kind.masthead}">` +
    (kicker ? `<p class="kicker">${esc(kicker)}</p>` : '') +
    `<h1>${esc(title)}</h1>` +
    (opts.subtitle ? `<p class="subhead">${esc(opts.subtitle)}</p>` : '') +
    `<div class="byline">${byline.map((b) => `<span>${esc(b)}</span>`).join('')}</div>` +
    `</header>`;

  const mermaidScript = ctx.needsMermaidCdn
    ? `<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
mermaid.initialize({ startOnLoad: true, theme: "neutral" });
</script>`
    : '';

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<style>
${css}${accentRule}${folio}${pageSize}
</style>
</head>
<body class="${bodyClass}">
<div class="page">
  ${masthead}
  ${opts.thesis ? `<div class="spine"><div class="label">In short</div><p>${inline(opts.thesis)}</p></div>` : ''}
  ${tocHtml}
  <main class="${kind.columns ? 'columned' : 'flow'}">
${bodyHtml}
  </main>
</div>
${mermaidScript}
</body>
</html>
`;

  return { html, kindName, kind, landscape, stats, ctx, sources };
}

// ---------------------------------------------------------------- main
//
// Guarded so the module can be imported — by a test, or anything else that wants its functions —
// without shelling out a build as a side effect of the import.

const isMain = (() => {
  const entry = process.argv[1];
  return Boolean(entry) && import.meta.url === pathToFileURL(entry).href;
})();

/**
 * Where a figure of a given native SVG size prints, and at what scale — the same placePlate a
 * build runs, so a measurement taken with this scale is the label size the reader gets.
 * @param {string} spec   native size as "<w>x<h>" in SVG px
 * @param {string} [kindName]  an edition kind; feature when omitted
 * @param {number} [labelCap]  overrides the label cap, as --label-cap does for a build
 * @returns {{cls: string, scale: number, labelPt: number, wIn: number, hIn: number}}
 * @throws {Error} on a malformed size or an unknown kind
 */
export function placementFor(spec, kindName = 'feature', labelCap = null) {
  const m = /^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)$/.exec(String(spec));
  if (!m || Number(m[1]) <= 0 || Number(m[2]) <= 0) throw new Error(`--place takes <w>x<h> in px, got ${spec}`);
  if (!KINDS[kindName]) throw new Error(`--kind must be one of ${Object.keys(KINDS).join(', ')}`);
  const savedCap = PAGE.labelCapPt;
  if (labelCap) PAGE.labelCapPt = labelCap;
  try {
    const p = placePlate({ w: Number(m[1]), h: Number(m[2]) }, labelPx(), KINDS[kindName]);
    return { cls: p.cls, scale: p.scale, labelPt: p.labelPt, wIn: p.wIn, hIn: p.hIn };
  } finally {
    PAGE.labelCapPt = savedCap;
  }
}

function main() {
  try {
    const opts = parseArgs(process.argv.slice(2));
    if (opts.place) {
      console.log(JSON.stringify(placementFor(opts.place, opts.kind || 'feature', opts.labelCap)));
      return;
    }
    if (opts.mermaidConfigOut) {
      const css = readFileSync(opts.css ? opts.css : DEFAULT_CSS, 'utf8');
      writeFileSync(opts.mermaidConfigOut, JSON.stringify(mermaidConfig(paletteOf(css, opts.accent)), null, 2), 'utf8');
      return;
    }
    const { html, kindName, kind, landscape, stats, ctx, sources } = build(opts);
    const outDir = path.dirname(path.resolve(opts.out));
    if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
    writeFileSync(opts.out, html, 'utf8');
    const kb = (Buffer.byteLength(html, 'utf8') / 1024).toFixed(0);
    console.log(`wrote ${opts.out} (${kb} KB, ${opts.inputs.length} document(s))`);
    console.log(`kind: ${kindName}${opts.kind ? ' (forced)' : ''} — ${stats.words} words, ${stats.h2} sections, ${stats.figures} figures, widest table ${stats.maxCols} cols; ` +
      `${kind.columns ? 'two columns' : 'single column'}, ${kind.serif ? 'serif' : 'sans'} body${landscape ? ', landscape' : ''}`);
    for (const f of ctx.figures) {
      console.log(`figure ${f.n}: ${f.cls.replace('diagram', '').trim() || 'column'} ${f.wIn.toFixed(1)}x${f.hIn.toFixed(1)}in (native ${Math.round(f.native.w)}x${Math.round(f.native.h)}${f.flipped ? ', direction flipped' : ''}), labels ${f.labelPt.toFixed(1)}pt`);
    }
    if (opts.verify) {
      const missing = verifyEdition(sources, html);
      if (missing.length) {
        for (const m of missing.slice(0, 25)) console.error(`build-magazine: MISSING ${path.basename(m.file)}:${m.line}: ${m.text.slice(0, 100)}`);
        console.error(`build-magazine: fidelity check failed — ${missing.length} source line(s) or cell(s) not found in the edition`);
        process.exit(2);
      }
      console.log('fidelity: every source line and table cell is present in the edition');
    }
    for (const w of ctx.warnings) console.error(`build-magazine: WARNING ${w}`);
    if (ctx.warnings.length) console.error(`build-magazine: ${ctx.warnings.length} warning(s) — review the edition before shipping it`);
  } catch (e) {
    console.error(`build-magazine: ${e.message}`);
    process.exit(1);
  }
}

if (isMain) main();

export {
  parseArgs, build, verifyEdition, editionText, extractCells, normalise, renderSub, renderList, printedDate,
  parseBlocks, scanFences, splitLines, paletteOf, mermaidConfig, actorHues, PORTRAIT, LANDSCAPE, GEOMETRY,
  DEFAULT_CSS, MERMAID_THEME,
};
