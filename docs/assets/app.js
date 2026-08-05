/* Renders docs/data/dashboard.json. No build step, no dependencies.
   All joining happens in Python; this file only presents. */

(function () {
  'use strict';

  var REPO = 'https://github.com/rron-patron/uk-resi-intel';
  var BANDS = ['Critical', 'High', 'Medium', 'Low'];

  var state = { data: null, band: 'all', source: 'all', query: '' };

  var $ = function (id) { return document.getElementById(id); };

  function text(el, value) { if (el) { el.textContent = value == null ? '' : String(value); } }

  function make(tag, cls, content) {
    var el = document.createElement(tag);
    if (cls) { el.className = cls; }
    if (content != null) { el.textContent = String(content); }
    return el;
  }

  function show(id, on) {
    var el = $(id);
    if (el) { el.hidden = !on; }
  }

  function fmtDate(iso) {
    if (!iso) { return 'Date not stated'; }
    var d = new Date(iso);
    if (isNaN(d.getTime())) { return 'Date not stated'; }
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function paragraphs(container, blob) {
    container.textContent = '';
    var parts = String(blob || '').split(/\n\s*\n/).filter(function (p) { return p.trim(); });
    if (!parts.length) {
      container.appendChild(make('p', null, 'No summary in this edition.'));
      return;
    }
    parts.forEach(function (p) { container.appendChild(make('p', null, p.trim())); });
  }

  /* ------------------------------------------------------------- header */

  function renderHeader(d) {
    text($('edition-date'), d.date_label || '—');
    text($('edition-time'), d.time_label || '—');
    text($('edition-count'), d.stats ? d.stats.stories : '—');
    text($('edition-sources'), d.stats ? d.stats.sources_live + '/' + d.stats.sources_total : '—');
    var link = $('repo-link');
    if (link) { link.href = REPO; }

    var ticker = $('ticker');
    ticker.textContent = '';
    var themes = (d.themes || []).slice(0, 10);
    if (!themes.length) {
      ticker.appendChild(make('span', null, 'No themes identified in this edition'));
      return;
    }
    themes.forEach(function (t) {
      var span = make('span');
      span.appendChild(make('b', null, t.name.toUpperCase()));
      span.appendChild(document.createTextNode(' ' + t.count + ' '));
      var arrow = t.direction === 'rising' ? '\u25B2' : t.direction === 'cooling' ? '\u25BC' : '\u2013';
      var mark = make('span', t.direction === 'rising' ? 'up' : t.direction === 'cooling' ? 'down' : '', arrow);
      span.appendChild(mark);
      ticker.appendChild(span);
    });
  }

  function renderNotice(d) {
    var meta = d.meta || {};
    var el = $('notice');
    if (meta.sample) {
      el.textContent = 'Placeholder edition. Nothing here is real market information — '
        + 'the first live briefing replaces this page once the daily workflow runs.';
      show('notice', true);
      return;
    }
    if (meta.degraded) {
      el.textContent = 'Degraded edition — the AI analysis step did not complete, so stories '
        + 'below are unrated and unsummarised. Reason: ' + (meta.degraded_reason || 'unknown') + '.';
      show('notice', true);
      return;
    }
    show('notice', false);
  }

  /* ---------------------------------------------------- note and reading */

  function renderBrief(d) {
    paragraphs($('summary'), d.executive_summary);
    var meta = d.meta || {};
    if (meta.sample) {
      text($('note-sign'), 'Placeholder \u00B7 no collection has run yet');
    } else {
      text($('note-sign'), 'Compiled ' + (d.date_label || '') + ' at ' + (d.time_label || '')
        + ' \u00B7 ' + (meta.model || 'analysis unavailable')
        + ' \u00B7 ' + ((d.stats && d.stats.stories) || 0) + ' items reviewed');
    }

    var s = d.sentiment || {};
    var score = typeof s.score === 'number' ? s.score : 0;
    text($('sentiment-verdict'), (s.overall || 'neutral') + ' ' + (score > 0 ? '+' : '') + score);
    $('gauge-pin').style.left = ((score + 100) / 2) + '%';
    var fig = $('gauge-figure');
    if (fig) { fig.setAttribute('aria-label', 'Sentiment score ' + score + ' out of a range of minus 100 to 100'); }
    text($('sentiment-rationale'), s.rationale || '');

    var wrap = $('signals');
    wrap.textContent = '';
    [['positive_signals', 'signal-pos', '+'], ['neutral_signals', 'signal-neu', '='],
     ['negative_signals', 'signal-neg', '\u2212']].forEach(function (group) {
      (s[group[0]] || []).forEach(function (line) {
        var row = make('p', 'signal ' + group[1]);
        row.appendChild(make('i', null, group[2]));
        row.appendChild(make('span', null, line));
        wrap.appendChild(row);
      });
    });

    var tally = $('tally');
    tally.textContent = '';
    var stats = d.stats || {};
    BANDS.forEach(function (band) {
      var li = document.createElement('li');
      li.appendChild(make('b', null, stats[band.toLowerCase()] || 0));
      li.appendChild(make('span', null, band));
      tally.appendChild(li);
    });
  }

  /* ------------------------------------------------------------ stories */

  function storyNode(story) {
    var li = make('li', 'story');
    li.appendChild(make('div', 'story-rail rail-' + story.importance));

    var main = make('div');
    var meta = make('div', 'story-meta');
    meta.appendChild(make('span', 'tag tag-' + story.importance, story.importance));
    meta.appendChild(make('span', 'story-source', story.source));
    meta.appendChild(make('span', null, fmtDate(story.published)));
    if (story.kind === 'data') { meta.appendChild(make('span', 'story-data', 'Official data')); }
    main.appendChild(meta);

    var h3 = make('h3');
    var a = make('a', null, story.title);
    a.href = story.url;
    a.rel = 'noopener nofollow';
    a.target = '_blank';
    h3.appendChild(a);
    main.appendChild(h3);

    var body = story.summary || story.excerpt;
    if (body) { main.appendChild(make('p', 'story-summary', body)); }

    if (story.why_it_matters) {
      var why = make('p', 'story-why');
      why.appendChild(make('b', null, 'Why it matters'));
      why.appendChild(document.createTextNode(story.why_it_matters));
      main.appendChild(why);
    }

    var tags = (story.themes || []).concat(story.companies || []).concat(story.locations || []);
    if (tags.length) {
      var ul = make('ul', 'story-tags');
      tags.slice(0, 8).forEach(function (t) { ul.appendChild(make('li', null, t)); });
      main.appendChild(ul);
    }

    li.appendChild(main);
    return li;
  }

  function filtered() {
    var q = state.query.trim().toLowerCase();
    return (state.data.stories || []).filter(function (s) {
      if (state.band !== 'all' && s.importance !== state.band) { return false; }
      if (state.source !== 'all' && s.source_key !== state.source) { return false; }
      if (!q) { return true; }
      var haystack = [s.title, s.summary, s.why_it_matters, s.source]
        .concat(s.themes || [], s.companies || [], s.locations || [])
        .join(' ').toLowerCase();
      return haystack.indexOf(q) !== -1;
    });
  }

  function renderStories() {
    var list = $('storylist');
    list.textContent = '';
    var rows = filtered();
    rows.forEach(function (s) { list.appendChild(storyNode(s)); });
    show('stories-empty', rows.length === 0);
    var total = (state.data.stories || []).length;
    text($('result-count'), rows.length === total
      ? rows.length + ' stories'
      : 'Showing ' + rows.length + ' of ' + total + ' stories');
  }

  function renderSourceFilter(d) {
    var select = $('source-filter');
    var counts = {};
    (d.stories || []).forEach(function (s) { counts[s.source_key] = (counts[s.source_key] || 0) + 1; });
    (d.sources || []).forEach(function (src) {
      if (!counts[src.key]) { return; }
      var opt = document.createElement('option');
      opt.value = src.key;
      opt.textContent = src.name + ' (' + counts[src.key] + ')';
      select.appendChild(opt);
    });
  }

  /* -------------------------------------------- themes, companies, etc. */

  function renderThemes(d) {
    var list = $('themes');
    list.textContent = '';
    var themes = d.themes || [];
    var max = themes.reduce(function (m, t) { return Math.max(m, t.count || 0); }, 1);
    if (!themes.length) {
      list.appendChild(make('li', 'empty', 'No themes identified in this edition.'));
      return;
    }
    themes.forEach(function (t) {
      var li = make('li', 'theme');
      var top = make('div', 'theme-top');
      top.appendChild(make('span', 'theme-name', t.name));
      var num = make('span', 'theme-num');
      num.appendChild(document.createTextNode(t.count + ' '));
      num.appendChild(make('span', t.direction, t.direction));
      top.appendChild(num);
      li.appendChild(top);
      var bar = make('div', 'theme-bar');
      var fill = make('span');
      fill.style.width = Math.round(((t.count || 0) / max) * 100) + '%';
      bar.appendChild(fill);
      li.appendChild(bar);
      if (t.summary) { li.appendChild(make('p', 'theme-note', t.summary)); }
      list.appendChild(li);
    });
  }

  function renderCompanies(d) {
    var body = $('companies');
    body.textContent = '';
    var rows = d.companies || [];
    show('companies-empty', rows.length === 0);
    rows.forEach(function (c) {
      var tr = document.createElement('tr');
      var td = document.createElement('td');
      td.appendChild(make('span', 'co-name', c.name));
      if (c.context) { td.appendChild(make('span', 'co-context', c.context)); }
      tr.appendChild(td);
      var type = document.createElement('td');
      type.appendChild(make('span', 'co-type', c.type || 'Other'));
      tr.appendChild(type);
      var num = make('td', 'num', c.mentions);
      tr.appendChild(num);
      body.appendChild(tr);
    });
  }

  function renderRegions(d) {
    var list = $('regions');
    list.textContent = '';
    var rows = d.regions || [];
    show('regions-empty', rows.length === 0);
    var max = rows.reduce(function (m, r) { return Math.max(m, r.mentions || 0); }, 1);
    rows.forEach(function (r) {
      var li = make('li', 'region');
      var left = make('div');
      left.appendChild(make('div', 'region-name', r.name));
      if (r.note) { left.appendChild(make('p', 'region-note', r.note)); }
      var bar = make('div', 'theme-bar');
      var fill = make('span');
      fill.style.width = Math.round(((r.mentions || 0) / max) * 100) + '%';
      bar.appendChild(fill);
      left.appendChild(bar);
      li.appendChild(left);
      li.appendChild(make('div', 'region-count', r.mentions));
      list.appendChild(li);
    });
  }

  function renderProjects(d) {
    var list = $('projects');
    list.textContent = '';
    var rows = d.projects || [];
    show('projects-empty', rows.length === 0);
    rows.forEach(function (p) {
      var li = make('li', 'project');
      li.appendChild(make('div', 'project-name', p.name));
      var meta = make('div', 'project-meta');
      function bit(label, value) {
        if (!value) { return; }
        var span = make('span');
        span.appendChild(document.createTextNode(label + ' '));
        span.appendChild(make('b', null, value));
        meta.appendChild(span);
      }
      bit('Location', p.location);
      bit('Homes', p.homes);
      bit('Value', p.value);
      bit('Developer', (p.developers || []).join(', '));
      li.appendChild(meta);
      if (p.summary) { li.appendChild(make('p', 'project-note', p.summary)); }
      list.appendChild(li);
    });
  }

  function linkFor(id) {
    return (state.data.stories || []).filter(function (s) { return s.id === id; })[0];
  }

  function renderPolicy(d) {
    var list = $('policy');
    list.textContent = '';
    var rows = d.policy || [];
    show('policy-empty', rows.length === 0);
    rows.forEach(function (p) {
      var li = document.createElement('li');
      li.appendChild(make('div', 'policy-kind', p.kind || 'government'));
      li.appendChild(make('h3', 'policy-head', p.headline));
      li.appendChild(make('p', 'policy-body', p.body));
      var ids = (p.article_ids || []).map(linkFor).filter(Boolean);
      if (ids.length) {
        var links = make('p', 'policy-links');
        links.appendChild(document.createTextNode('Source: '));
        ids.slice(0, 3).forEach(function (s, i) {
          if (i) { links.appendChild(document.createTextNode(' · ')); }
          var a = make('a', null, s.source);
          a.href = s.url;
          a.rel = 'noopener nofollow';
          a.target = '_blank';
          links.appendChild(a);
        });
        li.appendChild(links);
      }
      list.appendChild(li);
    });
  }

  function renderInvestor(d) {
    var wrap = $('investor');
    wrap.textContent = '';
    var view = d.investor_view || {};
    var panes = [
      ['Opportunities', view.opportunities || [], 'pane-opp'],
      ['Risks', view.risks || [], 'pane-risk'],
      ['Capital flows', (view.capital_flows || []).map(function (s) { return { point: s }; }), ''],
      ['Watch next', (view.watch_next || []).map(function (s) { return { point: s }; }), '']
    ];
    var any = false;
    panes.forEach(function (p) {
      if (!p[1].length) { return; }
      any = true;
      var pane = make('div', 'pane ' + p[2]);
      pane.appendChild(make('h3', null, p[0]));
      var ul = document.createElement('ul');
      p[1].forEach(function (item) {
        var li = document.createElement('li');
        li.appendChild(make('b', null, item.point));
        if (item.reasoning) { li.appendChild(make('span', null, item.reasoning)); }
        ul.appendChild(li);
      });
      pane.appendChild(ul);
      wrap.appendChild(pane);
    });
    if (!any) { wrap.appendChild(make('p', 'empty', 'No investor commentary in this edition.')); }
  }

  function renderFooter(d) {
    var list = $('sourcelist');
    list.textContent = '';
    (d.sources || []).forEach(function (s) {
      var li = document.createElement('li');
      var a = make('a', null, s.name);
      a.href = s.homepage;
      a.rel = 'noopener';
      a.target = '_blank';
      li.appendChild(a);
      list.appendChild(li);
    });

    var health = $('health');
    health.textContent = '';
    (d.source_health || []).forEach(function (h) {
      var li = document.createElement('li');
      li.appendChild(make('span', h.found > 0 ? 'health-ok' : 'health-bad', h.found > 0 ? '\u25CF ' : '\u25CB '));
      li.appendChild(document.createTextNode(h.name + ' '));
      li.appendChild(make('span', 'health-route', h.found + ' via ' + h.route));
      health.appendChild(li);
    });
  }

  /* ------------------------------------------------------------ archive */

  function renderArchive(entries, current) {
    var list = $('archive');
    list.textContent = '';
    var rows = (entries || []).filter(function (e) { return e.date !== current; });
    show('archive-empty', rows.length === 0);
    rows.slice(0, 30).forEach(function (e) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = '?edition=' + e.date;
      a.appendChild(make('span', 'dot dot-' + (e.sentiment || 'neutral')));
      a.appendChild(document.createTextNode(e.date + '  ' + e.stories + ' items'));
      li.appendChild(a);
      list.appendChild(li);
    });
  }

  /* -------------------------------------------------------------- wiring */

  function bindControls() {
    Array.prototype.forEach.call(document.querySelectorAll('.chip'), function (chip) {
      chip.addEventListener('click', function () {
        state.band = chip.getAttribute('data-band');
        Array.prototype.forEach.call(document.querySelectorAll('.chip'), function (c) {
          c.classList.toggle('is-on', c === chip);
        });
        renderStories();
      });
    });
    $('source-filter').addEventListener('change', function (e) {
      state.source = e.target.value;
      renderStories();
    });
    var timer;
    $('search').addEventListener('input', function (e) {
      clearTimeout(timer);
      var value = e.target.value;
      timer = setTimeout(function () { state.query = value; renderStories(); }, 140);
    });
  }

  function renderAll(d) {
    state.data = d;
    renderHeader(d);
    renderNotice(d);
    renderBrief(d);
    renderSourceFilter(d);
    renderStories();
    renderThemes(d);
    renderCompanies(d);
    renderRegions(d);
    renderProjects(d);
    renderPolicy(d);
    renderInvestor(d);
    renderFooter(d);
  }

  function failed(message) {
    var el = $('notice');
    el.textContent = message;
    show('notice', true);
    var summary = $('summary');
    summary.textContent = '';
    summary.appendChild(make('p', null,
      'No edition to display yet. The first briefing appears once the daily '
      + 'workflow has run successfully.'));
  }

  function boot() {
    bindControls();
    var params = new URLSearchParams(window.location.search);
    var wanted = params.get('edition');
    var path = wanted && /^\d{4}-\d{2}-\d{2}$/.test(wanted)
      ? 'data/archive/' + wanted + '.json'
      : 'data/dashboard.json';

    fetch(path, { cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) { throw new Error('HTTP ' + r.status); }
        return r.json();
      })
      .then(function (d) {
        renderAll(d);
        return fetch('data/archive/index.json', { cache: 'no-cache' });
      })
      .then(function (r) { return r && r.ok ? r.json() : []; })
      .then(function (entries) {
        renderArchive(entries, state.data.generated_at_london.slice(0, 10));
      })
      .catch(function (err) {
        if (!state.data) {
          failed('Could not load ' + path + ' (' + err.message + '). If you are '
            + 'viewing this file directly from disk, serve it over HTTP instead: '
            + 'python -m http.server --directory docs 8000');
        }
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
