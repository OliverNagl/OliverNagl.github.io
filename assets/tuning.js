/* Tuning page: gold-set verdicts, suggested config changes, and live re-ranking.
 *
 * The re-ranking is honest only because radar/rank.py keeps every term of the score in the
 * issue JSON. We recover the raw signals from the stored breakdown by dividing out the
 * weights that produced it, then re-apply the slider weights.
 */

(function () {
  "use strict";

  var WEIGHT_META = [
    ["relevance", 0, 2, "How relevant triage judged the paper (0-10, normalised)."],
    ["novelty", 0, 2, "How new the idea is, as judged at triage."],
    ["category", 0, 2, "Category weight from categories.yaml — how much this area matters to you."],
    ["watchlist_author", 0, 2, "A tracked author is on the paper."],
    ["code_released", 0, 2, "The abstract links released code."],
    ["venue_tier", 0, 2, "Journal tier; preprints score low here by design."],
    ["similar_seen_recently", -2, 0, "Penalty for something close to a recent pick."]
  ];

  var baseWeights = null, weights = {}, issues = {}, weeksList = [], current = null;

  var $sliders = document.getElementById("sliders");
  var $list = document.getElementById("rank-list");
  var $yaml = document.getElementById("yaml-out");
  var $week = document.getElementById("tune-week");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* Recover the raw signal from a stored term: term = weight * signal. Where the baseline
   * weight is zero the signal is unrecoverable, so fall back to the neutral value rather
   * than inventing one. */
  function signal(term, baseWeight, fallback) {
    if (!baseWeight) return fallback;
    return term / baseWeight;
  }

  function toPapers(issue) {
    var all = issue.front_page.slice();
    Object.keys(issue.backlog || {}).forEach(function (c) {
      all = all.concat(issue.backlog[c]);
    });
    return all.map(function (s) {
      var b = s.breakdown || {};
      return {
        id: s.id,
        title: s.title,
        category: s.category,
        date: s.date,
        relevance: s.relevance,
        novelty: s.novelty,
        category_weight: signal(b.category || 0, baseWeights.category, 1),
        watchlist_author: !!s.watchlist_hit,
        code_released: !!(s.links && s.links.code),
        venue_tier: signal(b.venue_tier || 0, baseWeights.venue_tier, 0),
        similar_seen_recently: (b.similar_seen_recently || 0) !== 0,
        origScore: s.score
      };
    });
  }

  function renderRanking() {
    var issue = issues[current];
    if (!issue) return;

    var papers = toPapers(issue);
    papers.forEach(function (p) { p.score = window.RadarRank.score(p, weights).total; });

    var topN = issue.front_page.length || 5;
    var maxPer = 2;
    var front = window.RadarRank.selectFrontPage(papers, topN, maxPer);
    var originalIds = issue.front_page.map(function (s) { return s.id; });

    $list.innerHTML = front.map(function (p, i) {
      var was = originalIds.indexOf(p.id);
      var cls = was === -1 ? "entered" : (was > i ? "moved-up" : (was < i ? "moved-down" : ""));
      var marker = was === -1 ? "new" : (was > i ? "▲" : (was < i ? "▼" : "="));
      return '<li class="rank-item ' + cls + '">' +
        '<span class="pos">' + (i + 1) + " " + marker + "</span>" +
        '<span class="t">' + esc(p.title) + "</span>" +
        '<span class="s">' + p.score.toFixed(2) + "</span></li>";
    }).join("");

    var frontIds = front.map(function (p) { return p.id; });
    var dropped = issue.front_page.filter(function (s) { return frontIds.indexOf(s.id) === -1; });
    if (dropped.length) {
      $list.innerHTML += dropped.map(function (s) {
        return '<li class="rank-item dropped"><span class="pos">out</span>' +
          '<span class="t">' + esc(s.title) + "</span>" +
          '<span class="s">' + s.score.toFixed(2) + "</span></li>";
      }).join("");
    }

    $yaml.textContent = "weights:\n" + WEIGHT_META.map(function (m) {
      return "  " + m[0] + ": " + weights[m[0]].toFixed(2);
    }).join("\n");
  }

  function buildSliders() {
    $sliders.innerHTML = WEIGHT_META.map(function (m) {
      var k = m[0];
      return '<div class="weight">' +
        '<label for="w-' + k + '"><span>' + k.replace(/_/g, " ") + "</span>" +
        '<span class="v" id="v-' + k + '">' + weights[k].toFixed(2) + "</span></label>" +
        '<input type="range" id="w-' + k + '" data-k="' + k + '" min="' + m[1] +
        '" max="' + m[2] + '" step="0.05" value="' + weights[k] + '">' +
        '<div class="hint">' + esc(m[3]) + "</div></div>";
    }).join("");

    $sliders.addEventListener("input", function (e) {
      var k = e.target.dataset.k;
      if (!k) return;
      weights[k] = parseFloat(e.target.value);
      document.getElementById("v-" + k).textContent = weights[k].toFixed(2);
      renderRanking();
    });
  }

  function renderGold(report) {
    var $gold = document.getElementById("gold");
    var $count = document.getElementById("gold-count");
    if (!report || !report.papers || !report.papers.length) return;

    var recovered = report.papers.filter(function (p) { return p.status === "pass"; }).length;
    $count.textContent = recovered + " of " + report.papers.length + " would surface";

    $gold.innerHTML = report.papers.map(function (p) {
      var cls = p.status === "pass" ? "pass" : (p.status === "weak" ? "weak" : "fail");
      return '<div class="verdict ' + cls + '">' +
        "<h4>" + esc(p.title || p.doi) + "</h4>" +
        (p.note ? '<div class="note">' + esc(p.note) + "</div>" : "") +
        '<div class="chain">' + esc((p.chain || []).join("  →  ")) + "</div>" +
        "</div>";
    }).join("");
  }

  function renderSuggestions(report) {
    var $s = document.getElementById("suggestions");
    if (!report || !report.suggestions || !report.suggestions.length) return;

    $s.innerHTML =
      '<p class="lede" style="margin-bottom:16px">Each term is priced against the archived ' +
      "weeks: a term that recovers one paper but admits several hundred is a bad trade, and " +
      "the number says so.</p>" +
      '<pre class="yaml">' + report.suggestions.map(function (s) {
        return esc(s.term) + ": " + esc(String(s.weight)) +
          "   # " + esc(s.category) + " · recovers " + s.recovers +
          ", admits +" + s.admits + " records" +
          (s.verdict ? "  (" + esc(s.verdict) + ")" : "");
      }).join("\n") + "</pre>";
  }

  // --- boot ------------------------------------------------------------------

  fetch("data/index.json")
    .then(function (r) { return r.json(); })
    .then(function (idx) {
      weeksList = (idx.weeks || []).map(function (w) { return w.week; });
      if (!weeksList.length) throw new Error("no archived weeks");
      $week.innerHTML = weeksList.map(function (w) {
        return '<option value="' + esc(w) + '">' + esc(w) + "</option>";
      }).join("");
      current = weeksList[0];
      return fetch("data/issues/" + current + ".json");
    })
    .then(function (r) { return r.json(); })
    .then(function (issue) {
      issues[current] = issue;
      // Recover the baseline weights from profile.yaml via the first scored paper is not
      // possible, so they are emitted into the issue by the renderer instead.
      baseWeights = issue.weights || {
        relevance: 1.0, novelty: 0.35, category: 0.5, watchlist_author: 0.4,
        code_released: 0.25, venue_tier: 0.2, similar_seen_recently: -0.3
      };
      WEIGHT_META.forEach(function (m) { weights[m[0]] = baseWeights[m[0]]; });
      buildSliders();
      renderRanking();
    })
    .catch(function () {
      $list.innerHTML = '<div class="empty">No archived week to re-rank yet.</div>';
    });

  fetch("data/eval/latest.json")
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (report) {
      if (!report) return;
      renderGold(report);
      renderSuggestions(report);
    })
    .catch(function () { /* no eval report yet — the placeholders already say so */ });

  document.getElementById("copy-yaml").addEventListener("click", function () {
    navigator.clipboard.writeText($yaml.textContent).then(function () {
      var b = document.getElementById("copy-yaml");
      var t = b.textContent;
      b.textContent = "Copied";
      setTimeout(function () { b.textContent = t; }, 1200);
    });
  });

  document.getElementById("reset-weights").addEventListener("click", function () {
    WEIGHT_META.forEach(function (m) {
      weights[m[0]] = baseWeights[m[0]];
      var el = document.getElementById("w-" + m[0]);
      if (el) el.value = weights[m[0]];
      var v = document.getElementById("v-" + m[0]);
      if (v) v.textContent = weights[m[0]].toFixed(2);
    });
    renderRanking();
  });

  $week.addEventListener("change", function () {
    current = $week.value;
    if (issues[current]) return renderRanking();
    fetch("data/issues/" + current + ".json")
      .then(function (r) { return r.json(); })
      .then(function (issue) { issues[current] = issue; renderRanking(); });
  });
})();
