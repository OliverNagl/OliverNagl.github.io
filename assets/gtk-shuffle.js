/* Front-page "good to know" shuffle.
 *
 * The section is rendered server-side with one deterministic pick for the week — the
 * point of that determinism is the weekly ledger, not the reader's browser. This adds a
 * client-side button that draws a fresh random pick from two sources merged together:
 * the archive of every past weekly pick (data/search-index.json, category
 * "good-to-know", real data already shipped for the archive page's search) and a seeded
 * pool of alternates (data/good_to_know_pool.json, fetched ahead of time by
 * `radar gtk-seed` since xkcd/Wikipedia don't allow browser-side CORS fetches). Never
 * runs automatically on load or refresh — the reader asks for it.
 */

(function () {
  "use strict";

  var section = document.getElementById("gtk-section");
  var btn = document.getElementById("gtk-shuffle");
  if (!section || !btn) return;

  var article = document.getElementById("gtk-article");
  var note = document.getElementById("gtk-note");
  var shown = [section.getAttribute("data-url") || ""];
  var pool = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function render(pick) {
    article.className = "gtk gtk-" + esc(pick.kind || "");
    var html = '<h3><a href="' + esc(pick.url) + '" rel="noopener">' + esc(pick.title) + "</a></h3>";
    if (pick.image) {
      html += '<a href="' + esc(pick.url) + '" rel="noopener" class="gtk-figure">' +
        '<img src="' + esc(pick.image) + '" alt="' + esc(pick.image_alt) + '" loading="lazy" decoding="async"></a>';
    }
    if (pick.why) html += '<p class="gtk-blurb">' + esc(pick.why) + "</p>";
    if (pick.detail) html += '<p class="gtk-detail">' + esc(pick.detail) + "</p>";
    if (pick.venue) html += '<p class="gtk-credit">' + esc(pick.venue) + "</p>";
    article.innerHTML = html;
    note.textContent = pick.reason || "";
    shown.push(pick.url);
  }

  function pickOne() {
    var fresh = pool.filter(function (d) { return shown.indexOf(d.url) === -1; });
    var from = fresh.length ? fresh : pool;
    return from[Math.floor(Math.random() * from.length)];
  }

  // Pool items (radar gtk-seed) carry different field names than search-index docs;
  // normalise to the shape `render` expects.
  function fromPoolItem(g) {
    return {
      kind: g.kind, title: g.title, url: g.url, image: g.image, image_alt: g.image_alt,
      why: g.blurb, detail: g.detail, venue: g.credit, reason: g.note,
    };
  }

  function loadPool() {
    return Promise.all([
      fetch("data/search-index.json").then(function (r) { return r.json(); }).catch(function () { return { docs: [] }; }),
      fetch("data/good_to_know_pool.json").then(function (r) { return r.json(); }).catch(function () { return { items: [] }; }),
    ]).then(function (results) {
      var fromWeeks = results[0].docs.filter(function (d) { return d.category === "good-to-know"; });
      var fromSeed = (results[1].items || []).map(fromPoolItem);
      return fromWeeks.concat(fromSeed);
    });
  }

  btn.addEventListener("click", function () {
    if (pool && !pool.length) return;
    btn.disabled = true;
    var original = btn.textContent;
    btn.textContent = "Shuffling…";

    Promise.resolve(pool || loadPool())
      .then(function (data) {
        if (!pool) pool = data;
        if (!pool.length) return;
        render(pickOne());
      })
      .catch(function () { /* leave the current pick showing */ })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = original;
      });
  });
})();
