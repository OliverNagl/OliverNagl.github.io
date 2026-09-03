/* Archive page behaviour: load the prebuilt index, filter, render.
 *
 * Rows are one line each by default and expand on click. The point of this surface is
 * recall of something you half-remember, not reading — so density beats richness here,
 * which is the opposite of the front page.
 */

(function () {
  "use strict";

  var state = { docs: [], index: null, cats: {}, q: "", flags: {}, week: "", cat: "" };

  var $q = document.getElementById("q");
  var $results = document.getElementById("results");
  var $count = document.getElementById("count");
  var $catFilters = document.getElementById("cat-filters");
  var $weekFilter = document.getElementById("week-filter");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function highlight(text, terms) {
    var out = esc(text);
    if (!terms || !terms.length) return out;
    // Longest first, so "assembly" is not partly consumed by a match on "assemb".
    terms.slice().sort(function (a, b) { return b.length - a.length; }).forEach(function (t) {
      if (t.length < 2) return;
      var re = new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
      out = out.replace(re, "<mark>$1</mark>");
    });
    return out;
  }

  function matchesFilters(d) {
    if (state.cat && d.category !== state.cat) return false;
    if (state.week && d.week !== state.week) return false;
    if (state.flags.front && !d.front) return false;
    if (state.flags.code && !d.code) return false;
    if (state.flags.watchlist && !d.watchlist) return false;
    return true;
  }

  function render() {
    var terms = state.q ? window.RadarSearch.tokenize(state.q) : [];
    var hits = state.q ? state.index.search(state.q) : null;

    var rows, partial = false;
    if (hits === null) {
      rows = state.docs.filter(matchesFilters).sort(function (a, b) {
        return a.week === b.week ? b.score - a.score : (a.week < b.week ? 1 : -1);
      });
    } else {
      partial = !!hits.partial;
      rows = hits.filter(function (h) { return matchesFilters(h.doc); })
                 .map(function (h) { return h.doc; });
    }

    $count.textContent = rows.length
      ? rows.length + (state.q ? " match" + (rows.length === 1 ? "" : "es") : " papers") +
        (partial ? " (partial)" : "")
      : "no matches";

    if (!rows.length) {
      $results.innerHTML = '<div class="empty">Nothing matches. Try fewer words, or reset the filters.</div>';
      return;
    }

    var shown = rows.slice(0, 400);
    var html = partial
      ? '<div class="more">No paper matches every word. Showing the closest.</div>'
      : "";
    html += shown.map(function (d) {
      var body = d.why || d.reason || "";
      return (
        '<article class="row" style="--cat: var(--c-' + esc(d.category) + ', var(--rule-firm));">' +
          '<div class="row-head">' +
            '<a class="row-title" href="' + esc(d.url) + '" rel="noopener">' + highlight(d.title, terms) + "</a>" +
            '<span class="row-meta">' +
              (d.action ? '<span class="pill action-' + esc(d.action) + '">' + esc(d.action) + "</span>" : "") +
              '<span class="cat-chip">' + esc(state.cats[d.category] || d.category) + "</span>" +
              '<span class="row-week">' + esc(d.week) + "</span>" +
            "</span>" +
          "</div>" +
          (body ? '<p class="row-why">' + highlight(body, terms) + "</p>" : "") +
          '<div class="row-foot">' +
            '<span>' + esc(d.authors) + "</span>" +
            '<span class="sep">·</span><span>' + esc(d.venue) + "</span>" +
            '<span class="sep">·</span><span>' + esc(d.date) + "</span>" +
            (d.code ? '<span class="signal has-code">◆ code</span>' : "") +
            (d.watchlist ? '<span class="signal watchlist">★ ' + esc(d.watchlist) + "</span>" : "") +
          "</div>" +
        "</article>"
      );
    }).join("");

    if (rows.length > shown.length) {
      html += '<div class="more">Showing ' + shown.length + " of " + rows.length +
              ". Narrow the query to see the rest.</div>";
    }
    $results.innerHTML = html;
  }

  function buildFilters() {
    var counts = {};
    state.docs.forEach(function (d) { counts[d.category] = (counts[d.category] || 0) + 1; });

    $catFilters.innerHTML = Object.keys(counts)
      .sort(function (a, b) { return counts[b] - counts[a]; })
      .map(function (c) {
        return '<button class="chip cat" data-cat="' + esc(c) + '" ' +
               'style="--cat: var(--c-' + esc(c) + ', var(--muted));">' +
               esc(state.cats[c] || c) + ' <span class="n">' + counts[c] + "</span></button>";
      }).join("");

    var weeks = Array.from(new Set(state.docs.map(function (d) { return d.week; }))).sort().reverse();
    weeks.forEach(function (w) {
      var o = document.createElement("option");
      o.value = w; o.textContent = w;
      $weekFilter.appendChild(o);
    });
  }

  function wire() {
    var t;
    $q.addEventListener("input", function () {
      state.q = $q.value.trim();
      clearTimeout(t);
      t = setTimeout(render, 60);
    });

    $catFilters.addEventListener("click", function (e) {
      var btn = e.target.closest("button.cat");
      if (!btn) return;
      var cat = btn.dataset.cat;
      state.cat = state.cat === cat ? "" : cat;
      Array.from($catFilters.children).forEach(function (b) {
        b.classList.toggle("on", b.dataset.cat === state.cat);
      });
      render();
    });

    document.querySelectorAll("[data-flag]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var f = btn.dataset.flag;
        state.flags[f] = !state.flags[f];
        btn.classList.toggle("on", state.flags[f]);
        render();
      });
    });

    $weekFilter.addEventListener("change", function () {
      state.week = $weekFilter.value;
      render();
    });

    document.getElementById("reset").addEventListener("click", function () {
      state.q = ""; state.cat = ""; state.week = ""; state.flags = {};
      $q.value = ""; $weekFilter.value = "";
      document.querySelectorAll(".chip.on").forEach(function (b) { b.classList.remove("on"); });
      render();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && document.activeElement !== $q) { e.preventDefault(); $q.focus(); }
      if (e.key === "Escape" && document.activeElement === $q) { $q.blur(); }
    });
  }

  fetch("data/search-index.json")
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (payload) {
      state.docs = payload.docs || [];
      state.cats = payload.categories || {};
      state.index = new window.RadarSearch.Index(state.docs);
      buildFilters();
      wire();

      // A "touches" chip on the front page links here with ?q=...
      var pre = new URLSearchParams(location.search).get("q");
      if (pre) { $q.value = pre; state.q = pre; }
      render();
    })
    .catch(function (err) {
      $results.innerHTML = '<div class="empty">Could not load the archive index (' +
        esc(err.message) + "). Run <code>radar render</code> to build it.</div>";
    });
})();
