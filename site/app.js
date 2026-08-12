'use strict';

/* Marine Microbial Observatories -- catalogue browser.
 *
 * Reads dist/data.json (built from the YAML records) and renders three
 * filterable tables, a map of the time-series sites, and a record detail
 * dialog with links back to the YAML file on GitHub.
 */

const REPO = 'https://github.com/merenlab/marine-microbial-observatories';
const BRANCH = 'main';

const TABLE_VIEWS = ['time-series', 'expeditions', 'coordination-networks'];

/* Prose views, rendered by scripts/build.py from the markdown files in the
 * repository root. The markdown is the only copy of this text. */
const PAGE_VIEWS = ['about', 'contribute'];

/* What a visitor with no hash lands on. About comes first so people meet the
 * catalogue, and the map, before the tables. */
const DEFAULT_VIEW = 'about';

const LABELS = {
  'time-series': 'Time series',
  'expeditions': 'Expeditions',
  'coordination-networks': 'Coordination networks',
};

/* Human-readable forms of the controlled vocabularies. */
const VOCAB = {
  'active': 'Active',
  'active-omics-discontinued': 'Active, omics discontinued',
  'discontinued': 'Discontinued',
  'unknown': 'Unknown',
  'surface': 'Surface',
  'surface-and-deep': 'Surface + deep',
  'weekly-or-more': 'Weekly or more',
  'monthly': 'Monthly',
  'bimonthly': 'Bimonthly',
  'quarterly': 'Quarterly',
  'annually': 'Annually',
  'amplicon-sequencing': 'Amplicon',
  'metagenomics': 'Metagenomics',
  'metatranscriptomics': 'Metatranscriptomics',
  'other-omics': 'Other omics',
};

const term = (v) => VOCAB[v] || v;

/* Column definitions per view. `get` returns a sortable primitive;
 * `cell` returns display HTML. */
const COLUMNS = {
  'time-series': [
    { key: 'name', label: 'Program', cls: 'name', cell: nameCell },
    { key: 'countries', label: 'Country', get: (r) => (r.countries || []).join(', ') },
    { key: 'ocean-basins', label: 'Ocean basin', get: (r) => (r['ocean-basins'] || []).join(', ') },
    { key: 'sub-region', label: 'Sub-region', cls: 'wrap-cell' },
    { key: 'sampling-start-year', label: 'Since', cls: 'num' },
    { key: 'sampling-cadence', label: 'Cadence', get: (r) => term(r['sampling-cadence']) },
    { key: 'sampling-depth', label: 'Depth', get: (r) => term(r['sampling-depth']) },
    {
      key: 'omics-types', label: 'Omics',
      get: (r) => (r['omics-types'] || []).length,
      cell: (r) => pills((r['omics-types'] || []).map(term)),
    },
    { key: 'status', label: 'Status', cell: (r) => statusPill(r.status) },
    {
      key: 'data-accessions', label: 'Accessions', cls: 'num',
      get: (r) => (r['data-accessions'] || []).length,
      cell: (r) => String((r['data-accessions'] || []).length || '—'),
    },
  ],
  'expeditions': [
    { key: 'name', label: 'Expedition', cls: 'name', cell: nameCell },
    { key: 'affiliated-institutions', label: 'Affiliation', cls: 'wrap-cell' },
    {
      key: 'data-accessions', label: 'Accessions', cls: 'num',
      get: (r) => (r['data-accessions'] || []).length,
      cell: (r) => String((r['data-accessions'] || []).length || '—'),
    },
    {
      key: 'publications', label: 'Publications', cls: 'num',
      get: (r) => (r.publications || []).length,
      cell: (r) => String((r.publications || []).length || '—'),
    },
    { key: 'contacts', label: 'Contact', get: (r) => contactNames(r), cls: 'wrap-cell' },
  ],
  'coordination-networks': [
    { key: 'name', label: 'Network', cls: 'name', cell: nameCell },
    { key: 'umbrella-organisation', label: 'Umbrella' },
    { key: 'geographic-scope', label: 'Scope', cls: 'wrap-cell' },
    { key: 'established-year', label: 'Since', cls: 'num' },
    { key: 'status', label: 'Status', cell: (r) => statusPill(r.status) },
    { key: 'contacts', label: 'Contact', get: (r) => contactNames(r), cls: 'wrap-cell' },
  ],
};

/* Filters offered per view: a select built from the values present. */
const FILTERS = {
  'time-series': [
    { key: 'ocean-basins', label: 'Ocean basin', multi: true },
    { key: 'countries', label: 'Country', multi: true },
    { key: 'status', label: 'Status', display: term },
    { key: 'sampling-cadence', label: 'Cadence', display: term },
    { key: 'sampling-depth', label: 'Depth', display: term },
    { key: 'omics-types', label: 'Omics type', multi: true, display: term },
  ],
  'expeditions': [],
  'coordination-networks': [
    { key: 'umbrella-organisation', label: 'Umbrella' },
    { key: 'status', label: 'Status', display: term },
  ],
};

/* ------------------------------------------------------------------ state */

const state = {
  view: DEFAULT_VIEW,
  query: '',
  filters: {},
  sort: { key: 'name', dir: 1 },
};

let DATA = null;
let map = null;

/* --------------------------------------------------------------- helpers */

const $ = (sel) => document.querySelector(sel);

function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function contactNames(record) {
  return (record.contacts || []).map((c) => c.name).filter(Boolean).join(', ');
}

function nameCell(record) {
  const acronym = record.acronym
    ? `<span class="acronym">${esc(record.acronym)}</span>` : '';
  return `${esc(record.name)}${acronym}`;
}

function statusPill(status) {
  if (!status) return '—';
  const kind = status.startsWith('active') ? 'active' : status;
  return `<span class="pill ${esc(kind)}">${esc(term(status))}</span>`;
}

function pills(values) {
  if (!values || !values.length) return '—';
  return `<span class="pill-row">${values
    .map((v) => `<span class="pill">${esc(v)}</span>`).join('')}</span>`;
}

function publicationLink(item) {
  const href = /^10\./.test(item) ? `https://doi.org/${item}` : item;
  return `<a href="${esc(href)}" rel="noopener noreferrer" target="_blank">${esc(item)}</a>`;
}

/* Archive links, chosen by accession prefix. */
function accessionLink(accession) {
  let href;
  if (/^PRJNA/.test(accession)) {
    href = `https://www.ncbi.nlm.nih.gov/bioproject/${accession}`;
  } else if (/^PRJE|^ER/.test(accession)) {
    href = `https://www.ebi.ac.uk/ena/browser/view/${accession}`;
  } else if (/^PRJDB|^DR/.test(accession)) {
    href = `https://ddbj.nig.ac.jp/search/entry/bioproject/${accession}`;
  } else if (/^PXD/.test(accession)) {
    href = `https://www.ebi.ac.uk/pride/archive/projects/${accession}`;
  } else if (/^SR/.test(accession)) {
    href = `https://www.ncbi.nlm.nih.gov/sra/?term=${accession}`;
  } else {
    href = `https://www.ncbi.nlm.nih.gov/search/all/?term=${accession}`;
  }
  return `<a href="${esc(href)}" rel="noopener noreferrer" target="_blank"><code>${esc(accession)}</code></a>`;
}

/* Everything a record contains, flattened, for the search box. */
function searchBlob(record) {
  if (record.__blob) return record.__blob;
  const parts = [];
  const walk = (node) => {
    if (node == null) return;
    if (typeof node === 'string' || typeof node === 'number') { parts.push(String(node)); return; }
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (typeof node === 'object') {
      // `samples` holds thousands of accessions and coordinates per expedition.
      // Folding those in would make a search for "50" match every expedition
      // and would grow the blob far beyond anything a person types.
      Object.entries(node).forEach(([key, value]) => { if (key !== 'samples') walk(value); });
    }
  };
  walk(record);
  record.__blob = parts.join('  ').toLowerCase();
  return record.__blob;
}

/* --------------------------------------------------------------- filtering */

function currentRecords() {
  const records = (DATA.records[state.view] || []).slice();
  const query = state.query.trim().toLowerCase();
  const terms = query ? query.split(/\s+/) : [];

  const filtered = records.filter((record) => {
    for (const [key, value] of Object.entries(state.filters)) {
      if (!value) continue;
      const field = record[key];
      const ok = Array.isArray(field) ? field.includes(value) : field === value;
      if (!ok) return false;
    }
    if (!terms.length) return true;
    const blob = searchBlob(record);
    return terms.every((t) => blob.includes(t));
  });

  const column = (COLUMNS[state.view] || []).find((c) => c.key === state.sort.key);
  const value = (record) => {
    if (column && column.get) return column.get(record);
    const raw = record[state.sort.key];
    return Array.isArray(raw) ? raw.join(', ') : raw;
  };

  filtered.sort((a, b) => {
    const va = value(a);
    const vb = value(b);
    const ea = va === undefined || va === null || va === '';
    const eb = vb === undefined || vb === null || vb === '';
    if (ea && eb) return 0;
    if (ea) return 1;   // missing values always sort last
    if (eb) return -1;
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * state.sort.dir;
    return String(va).localeCompare(String(vb), 'en', { sensitivity: 'base' }) * state.sort.dir;
  });

  return filtered;
}

/* --------------------------------------------------------------- rendering */

function renderFilters() {
  const host = $('#filters');
  const defs = FILTERS[state.view] || [];
  host.innerHTML = '';

  defs.forEach((def) => {
    const values = new Set();
    (DATA.records[state.view] || []).forEach((record) => {
      const field = record[def.key];
      if (Array.isArray(field)) field.forEach((v) => values.add(v));
      else if (field) values.add(field);
    });
    if (values.size < 2) return;

    const sorted = [...values].sort((a, b) =>
      String(def.display ? def.display(a) : a)
        .localeCompare(String(def.display ? def.display(b) : b), 'en'));

    const label = document.createElement('label');
    label.innerHTML = `<span>${esc(def.label)}</span>`;
    const select = document.createElement('select');
    select.innerHTML = `<option value="">All</option>` + sorted
      .map((v) => `<option value="${esc(v)}"${state.filters[def.key] === v ? ' selected' : ''}>${
        esc(def.display ? def.display(v) : v)}</option>`).join('');
    select.addEventListener('change', () => {
      state.filters[def.key] = select.value;
      renderTable();
    });
    label.appendChild(select);
    host.appendChild(label);
  });
}

function renderTable() {
  const columns = COLUMNS[state.view] || [];
  const records = currentRecords();
  const total = (DATA.records[state.view] || []).length;

  $('#table-head').innerHTML = columns.map((c) => {
    const active = state.sort.key === c.key;
    const arrow = active ? `<span class="arrow">${state.sort.dir > 0 ? '▲' : '▼'}</span>` : '';
    const sortAttr = active
      ? ` aria-sort="${state.sort.dir > 0 ? 'ascending' : 'descending'}"` : '';
    return `<th data-key="${esc(c.key)}"${sortAttr} scope="col" tabindex="0"
      role="columnheader">${esc(c.label)} ${arrow}</th>`;
  }).join('');

  $('#table-body').innerHTML = records.map((record) => {
    const cells = columns.map((c) => {
      const cls = c.cls ? ` class="${c.cls}"` : '';
      let html;
      if (c.cell) html = c.cell(record);
      else {
        const raw = c.get ? c.get(record) : record[c.key];
        const value = Array.isArray(raw) ? raw.join(', ') : raw;
        html = (value === undefined || value === null || value === '') ? '—' : esc(value);
      }
      return `<td${cls}>${html}</td>`;
    }).join('');
    return `<tr data-id="${esc(record.id)}" tabindex="0">${cells}</tr>`;
  }).join('');

  const shown = records.length;
  $('#result-count').textContent = shown === total
    ? `${total} ${total === 1 ? 'record' : 'records'}`
    : `${shown} of ${total} records`;
  $('#empty').hidden = shown !== 0;
}

/* ------------------------------------------------------------------ detail */

function field(label, html) {
  if (html === undefined || html === null || html === '' || html === '—') return '';
  return `<dt>${esc(label)}</dt><dd>${html}</dd>`;
}

function list(items, render) {
  if (!items || !items.length) return '';
  if (items.length === 1) return render(items[0]);
  return `<ul>${items.map((i) => `<li>${render(i)}</li>`).join('')}</ul>`;
}

function link(url) {
  return `<a href="${esc(url)}" rel="noopener noreferrer" target="_blank">${esc(url)}</a>`;
}

function renderDetail(view, record) {
  const rows = [];
  const add = (label, html) => rows.push(field(label, html));

  const websiteKey = view === 'coordination-networks' ? 'network-website' : 'program-website';
  const websites = [record[websiteKey], ...(record['additional-websites'] || [])].filter(Boolean);
  add('website', list(websites, link));

  add('affiliated institutions', record['affiliated-institutions']
    ? esc(record['affiliated-institutions']) : '');
  add('institution websites', list(record['affiliated-institution-websites'], link));

  if (view === 'time-series') {
    add('status', statusPill(record.status));
    add('countries', esc((record.countries || []).join(', ')));
    add('ocean basins', esc((record['ocean-basins'] || []).join(', ')));
    add('sub-region', esc(record['sub-region'] || ''));
    if (record.latitude != null) {
      add('coordinates',
        `${record.latitude}, ${record.longitude}
         <a href="https://www.openstreetmap.org/?mlat=${record.latitude}&mlon=${
           record.longitude}#map=6/${record.latitude}/${record.longitude}"
            rel="noopener noreferrer" target="_blank">map</a>`);
    }
    const span = record['sampling-end-year'] === 'present'
      ? `${record['sampling-start-year']} – present`
      : `${record['sampling-start-year']} – ${record['sampling-end-year']}`;
    add('sampling years', esc(span));
    add('DNA collection since', record['dna-collection-start-year']
      ? esc(record['dna-collection-start-year']) : '');
    add('DNA collection detail', record['dna-collection-note']
      ? esc(record['dna-collection-note']) : '');
    add('sampling depth', esc(term(record['sampling-depth'])));
    add('sampling cadence', esc(term(record['sampling-cadence'])));
    add('omics types', pills((record['omics-types'] || []).map(term)));
    add('multiple sites', record['multiple-sampling-sites'] === undefined
      ? '' : (record['multiple-sampling-sites'] ? 'Yes' : 'No'));
    add('sites detail', record['sampling-sites-note'] ? esc(record['sampling-sites-note']) : '');
  }

  if (view === 'coordination-networks') {
    add('status', statusPill(record.status));
    add('umbrella organisation', esc(record['umbrella-organisation'] || ''));
    add('geographic scope', esc(record['geographic-scope'] || ''));
    add('established', record['established-year']
      ? esc(record['established-year'] + (record['established-note']
        ? ` (${record['established-note']})` : '')) : '');
    add('mission', record['mission-statement'] ? esc(record['mission-statement']) : '');
  }

  if (view === 'expeditions') {
    add('sample metadata', record['sample-metadata-source']
      ? esc(record['sample-metadata-source']) : '');
    const samples = record.samples || [];
    const placed = samples.filter((s) => s.latitude != null && s.longitude != null).length;
    add('samples', samples.length
      ? `${samples.length.toLocaleString()} samples` + (placed
        ? `, ${placed === samples.length ? 'all' : placed.toLocaleString()} with coordinates
           and shown as black dots on the <a href="#about" data-map="1">map</a>` : '') +
        (placed < samples.length
          ? ` <span class="unverified">${(samples.length - placed).toLocaleString()} without
             coordinates</span>` : '')
      : '');
  }

  add('data accessions', list(record['data-accessions'], accessionLink));
  add('accession notes', record['data-accessions-note']
    ? esc(record['data-accessions-note']) : '');

  add('contacts', list(record.contacts || [], (c) => {
    const name = c.name ? esc(c.name) : '';
    const mail = c.email
      ? `<a href="mailto:${esc(c.email)}?subject=${encodeURIComponent(record.name)}">${
        esc(c.email)}</a>` : '';
    const role = c.role ? ` <span class="role">${esc(c.role)}</span>` : '';
    const note = c.note ? ` <span class="cnote">(${esc(c.note)})</span>` : '';
    return `<div class="contact">${name}${role}${name && mail ? '<br>' : ''}${mail}${note}</div>`;
  }));

  add('publications', list(record.publications, publicationLink));
  add('notes', record.notes ? esc(record.notes) : '');

  const verification = record.verification || {};
  if (verification['checked-on']) {
    add('last checked', `${esc(verification['checked-on'])} by ${
      esc((verification['checked-by'] || []).join(', '))}`);
  } else if (verification['checked-by']) {
    add('last checked', `<span class="unverified">date unknown</span> — ${
      esc((verification['checked-by'] || []).join(', '))}`);
  } else {
    add('last checked', '<span class="unverified">never confirmed by a named person</span>');
  }
  if (verification['checked-note']) add('verification note', esc(verification['checked-note']));

  const path = `data/${view}/${record.id}.yml`;
  const editUrl = `${REPO}/edit/${BRANCH}/${path}`;
  const viewUrl = `${REPO}/blob/${BRANCH}/${path}`;
  const issueUrl = `${REPO}/issues/new?template=correct-record.yml&title=${
    encodeURIComponent(`Correction: ${record.name}`)}&record=${encodeURIComponent(`${view}/${record.id}`)}`;

  $('#detail-body').innerHTML = `
    <h2 id="detail-title">${esc(record.name)}</h2>
    <p class="rec-acronym">${esc(record.acronym || '')}${record.acronym ? ' · ' : ''}${
      esc(view)}/${esc(record.id)}</p>
    <dl class="fields">${rows.join('')}</dl>
    <div class="rec-actions">
      <a class="btn primary" href="${esc(editUrl)}" rel="noopener noreferrer" target="_blank">Edit this record</a>
      <a class="btn" href="${esc(issueUrl)}" rel="noopener noreferrer" target="_blank">Report a problem</a>
      <a class="btn" href="${esc(viewUrl)}" rel="noopener noreferrer" target="_blank">View YAML</a>
    </div>`;

  const dialog = $('#detail');

  // The map lives on the About page, so the sample-count link has to leave the
  // dialog rather than just move the hash under it. Closing first lets the
  // dialog's own close handler write its hash before setView writes the real one.
  const toMap = $('#detail-body').querySelector('[data-map]');
  if (toMap) {
    toMap.addEventListener('click', (event) => {
      event.preventDefault();
      dialog.close();
      setView('about', true);
    });
  }

  if (!dialog.open) dialog.showModal();
}

function openRecord(view, id, pushHash) {
  const record = (DATA.records[view] || []).find((r) => r.id === id);
  if (!record) return false;
  renderDetail(view, record);
  if (pushHash) history.replaceState(null, '', `#${view}/${id}`);
  return true;
}

/* --------------------------------------------------------------------- map */

/* The map lives inside the About page, in a <div id="map-embed"> that ABOUT.md
 * positions in its own prose. Called after that page is injected. */
function renderMap() {
  const host = $('#map-embed');
  if (!host || map) {
    if (map) map.invalidateSize();
    return;
  }

  const records = (DATA.records['time-series'] || [])
    .filter((r) => r.latitude != null && r.longitude != null);
  const missing = (DATA.records['time-series'] || []).length - records.length;

  host.innerHTML = '<div class="map-canvas"></div><p class="map-caption"></p>';
  const canvas = host.querySelector('.map-canvas');

  // Leaflet comes from a CDN; some networks block it, and the rest of the
  // catalogue should still work when they do.
  if (typeof L === 'undefined') {
    host.innerHTML =
      '<p class="empty">The map library could not be loaded, so the map is unavailable. ' +
      'Coordinates are still listed on each time-series record.</p>';
    return;
  }

  map = L.map(canvas, { worldCopyJump: true }).setView([20, 0], 2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 12,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  /* Expeditions are ships in motion, so they have no single home coordinate the
   * way an observatory does -- each one contributes hundreds of individual
   * sample positions instead. Drawn as ordinary markers they would bury the
   * observatories under thousands of circles, so they go down as 1px black dots
   * that read as a track rather than as records you can click. Their own pane,
   * below the overlay pane the station markers live in, keeps them underneath;
   * a canvas renderer keeps panning smooth, which a few thousand SVG nodes
   * would not. */
  map.createPane('expedition-samples');
  map.getPane('expedition-samples').style.zIndex = 350;
  const dots = L.canvas({ pane: 'expedition-samples', padding: 0.5 });

  let sampleCount = 0;
  let expeditionCount = 0;
  let unplacedCount = 0;
  (DATA.records.expeditions || []).forEach((record) => {
    const listed = record.samples || [];
    const samples = listed.filter((s) => s.latitude != null && s.longitude != null);
    unplacedCount += listed.length - samples.length;
    if (samples.length) expeditionCount += 1;
    samples.forEach((sample) => {
      L.circleMarker([sample.latitude, sample.longitude], {
        renderer: dots,
        pane: 'expedition-samples',
        radius: 1,
        weight: 0,
        fillColor: '#111',
        fillOpacity: 0.6,
        interactive: false,
      }).addTo(map);
      sampleCount += 1;
    });
  });

  /* Group by exact coordinate so co-located programs are all reachable. */
  const groups = new Map();
  records.forEach((record) => {
    const key = `${record.latitude},${record.longitude}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(record);
  });

  const bounds = [];

  groups.forEach((group, key) => {
    const [lat, lon] = key.split(',').map(Number);
    const marker = L.circleMarker([lat, lon], {
      radius: group.length > 1 ? 7 : 5,
      weight: 1.5,
      color: '#0e5670',
      fillColor: '#3aa8cc',
      fillOpacity: 0.85,
    }).addTo(map);

    bounds.push([lat, lon]);

    const html = group.map((record) => `
      <strong><a href="#time-series/${esc(record.id)}" data-open="${esc(record.id)}">${
        esc(record.name)}</a></strong>
      <span class="sub">${esc(record.acronym || '')}${record.acronym ? ' · ' : ''}${
        esc((record['ocean-basins'] || []).join(', '))} · since ${
        esc(record['sampling-start-year'])}</span>`).join('<hr>');

    marker.bindPopup(html);
    marker.on('popupopen', (event) => {
      event.popup.getElement().querySelectorAll('[data-open]').forEach((anchor) => {
        anchor.addEventListener('click', (clickEvent) => {
          clickEvent.preventDefault();
          openRecord('time-series', anchor.dataset.open, true);
        });
      });
    });
  });

  /* Only the observatories frame the view. Expedition samples are near-global,
   * so fitting to them too would always zoom straight back out to the world. */
  if (bounds.length) map.fitBounds(bounds, { padding: [20, 20], maxZoom: 6 });

  host.querySelector('.map-caption').textContent =
    `${records.length} time-series programs with coordinates.` +
    (missing ? ` ${missing} record${missing === 1 ? '' : 's'} ` +
      `${missing === 1 ? 'has' : 'have'} no coordinates and cannot be shown.` : '') +
    ' Programs at identical coordinates share a marker.' +
    (sampleCount ? ` The small black dots are ${sampleCount.toLocaleString()} individual ` +
      `samples from ${expeditionCount} large-scale expedition` +
      `${expeditionCount === 1 ? '' : 's'}; they mark where an expedition sampled ` +
      'rather than a program you can open.' : '') +
    (unplacedCount ? ` ${unplacedCount.toLocaleString()} listed sample` +
      `${unplacedCount === 1 ? ' has' : 's have'} no coordinates and cannot be shown.` : '');
}

/* ------------------------------------------------------------------- pages */

const pageCache = {};

/* Fetch a rendered markdown fragment once and drop it into its panel. */
async function loadPage(slug) {
  const panel = $(`#panel-${slug}`);
  if (!panel || pageCache[slug]) return;
  pageCache[slug] = true;

  try {
    const response = await fetch(`pages/${slug}.html`, { cache: 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    panel.innerHTML = await response.text();
    // The page may carry a <div id="map-embed"> placeholder for the site map.
    if (panel.querySelector('#map-embed')) renderMap();
  } catch (error) {
    pageCache[slug] = false;
    const source = slug === 'about' ? 'ABOUT.md' : 'CONTRIBUTING.md';
    panel.innerHTML = `<p class="empty">This page could not be loaded ` +
      `(${esc(error.message)}). Read it on GitHub instead: ` +
      `<a href="${esc(REPO)}/blob/${BRANCH}/${esc(source)}">${esc(source)}</a>.</p>`;
  } finally {
    panel.removeAttribute('aria-busy');
  }
}

/* ------------------------------------------------------------------- views */

function setView(view, pushHash) {
  state.view = view;
  document.querySelectorAll('.tab').forEach((tab) => {
    if (tab.dataset.view === view) tab.setAttribute('aria-current', 'page');
    else tab.removeAttribute('aria-current');
  });

  const isTable = TABLE_VIEWS.includes(view);
  $('#panel-table').hidden = !isTable;
  PAGE_VIEWS.forEach((slug) => { $(`#panel-${slug}`).hidden = view !== slug; });

  if (PAGE_VIEWS.includes(view)) loadPage(view);

  if (isTable) {
    state.filters = {};
    state.sort = { key: 'name', dir: 1 };
    renderFilters();
    renderTable();
  }
  // Leaflet mis-measures a map that was laid out while hidden, so re-check on
  // every return to the page that holds it.
  if (view === 'about' && map) map.invalidateSize();
  if (pushHash) history.replaceState(null, '', `#${view}`);
}

function applyHash() {
  const hash = decodeURIComponent(location.hash.replace(/^#/, ''));
  if (!hash) { setView(DEFAULT_VIEW, false); return; }
  const [first, second] = hash.split('/');
  if (second && TABLE_VIEWS.includes(first)) {
    setView(first, false);
    if (!openRecord(first, second, false)) setView(first, true);
    return;
  }
  if (TABLE_VIEWS.includes(first) || PAGE_VIEWS.includes(first)) {
    setView(first, false);
    return;
  }
  // `#map` used to be its own tab; the map now lives on the About page.
  if (first === 'map') { setView('about', true); return; }
  setView(DEFAULT_VIEW, true);
}

/* -------------------------------------------------------------------- init */

function wire() {
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => setView(tab.dataset.view, true));
  });

  const search = $('#search');
  search.addEventListener('input', () => { state.query = search.value; renderTable(); });

  $('#reset').addEventListener('click', () => {
    search.value = '';
    state.query = '';
    state.filters = {};
    renderFilters();
    renderTable();
  });

  $('#table-head').addEventListener('click', (event) => {
    const th = event.target.closest('th');
    if (!th) return;
    sortBy(th.dataset.key);
  });
  $('#table-head').addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const th = event.target.closest('th');
    if (!th) return;
    event.preventDefault();
    sortBy(th.dataset.key);
  });

  const openFromRow = (event) => {
    const row = event.target.closest('tr[data-id]');
    if (!row) return;
    openRecord(state.view, row.dataset.id, true);
  };
  $('#table-body').addEventListener('click', openFromRow);
  $('#table-body').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') openFromRow(event);
  });

  const dialog = $('#detail');
  $('#detail-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();   // click on the backdrop
  });
  dialog.addEventListener('close', () => {
    history.replaceState(null, '', `#${state.view}`);
  });

  window.addEventListener('hashchange', applyHash);
}

function sortBy(key) {
  if (!key) return;
  if (state.sort.key === key) state.sort.dir *= -1;
  else state.sort = { key, dir: 1 };
  renderTable();
}

function renderChrome() {
  const counts = DATA.counts || {};
  document.querySelectorAll('.tab').forEach((tab) => {
    const view = tab.dataset.view;
    if (counts[view] != null) {
      tab.innerHTML = `${esc(LABELS[view])} <span class="n">${counts[view]}</span>`;
    }
  });

  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const built = DATA['built-on'] ? `, built ${DATA['built-on']}` : '';
  $('#corpus-meta').textContent =
    `${total} records — ${counts['time-series'] || 0} time series, ` +
    `${counts['expeditions'] || 0} expeditions, ` +
    `${counts['coordination-networks'] || 0} coordination networks${built}.`;

  // Tab labels for the prose pages come from the build, so renaming a page in
  // scripts/build.py renames its tab too.
  Object.entries(DATA.pages || {}).forEach(([slug, title]) => {
    const tab = document.querySelector(`.tab[data-view="${slug}"]`);
    if (tab && title) tab.textContent = title;
  });

  $('#rev').innerHTML = DATA.revision
    ? `<a href="${esc(REPO)}/commit/${esc(DATA.revision)}"><code>${esc(DATA.revision)}</code></a>`
    : 'the repository';
}

async function init() {
  try {
    const response = await fetch('data.json', { cache: 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    DATA = await response.json();
  } catch (error) {
    $('#corpus-meta').textContent = `Could not load the catalogue: ${error.message}`;
    return;
  }
  renderChrome();
  wire();
  applyHash();
}

init();
