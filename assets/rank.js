/* The §3 ranking arithmetic, mirrored from radar/rank.py.
 *
 * It lives in two languages so the tuning page can re-rank an archived week live in the
 * browser without a server. That is only safe because the ranking is deliberately plain
 * arithmetic rather than a learned model — and because tests/test_rank_parity.py asserts
 * these two implementations agree on a fixture. Change them together.
 */

(function () {
  "use strict";

  var MAX_RATING = 10.0;

  function round4(x) { return Math.round(x * 10000) / 10000; }

  /* Mirrors rank.score(). `paper` carries the raw signals; `weights` comes from the
   * sliders (or profile.yaml). Returns the per-term breakdown, never just a total —
   * seeing which term sank a paper is the entire point. */
  function score(paper, weights) {
    var b = {
      relevance:            round4(weights.relevance * (paper.relevance / MAX_RATING)),
      novelty:              round4(weights.novelty * (paper.novelty / MAX_RATING)),
      category:             round4(weights.category * paper.category_weight),
      watchlist_author:     round4(weights.watchlist_author * (paper.watchlist_author ? 1 : 0)),
      code_released:        round4(weights.code_released * (paper.code_released ? 1 : 0)),
      venue_tier:           round4(weights.venue_tier * paper.venue_tier),
      similar_seen_recently: round4(weights.similar_seen_recently * (paper.similar_seen_recently ? 1 : 0))
    };
    b.total = round4(Object.keys(b).reduce(function (a, k) { return a + b[k]; }, 0));
    return b;
  }

  /* Mirrors rank.select_front_page(): global top-N with a per-category cap, so one hot
   * week in a single category cannot crowd out everything else. */
  function selectFrontPage(scored, topN, maxPerCategory) {
    var ordered = scored.slice().sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.date < b.date ? 1 : -1;
    });
    var front = [], perCat = {};
    for (var i = 0; i < ordered.length && front.length < topN; i++) {
      var s = ordered[i];
      if ((perCat[s.category] || 0) >= maxPerCategory) continue;
      front.push(s);
      perCat[s.category] = (perCat[s.category] || 0) + 1;
    }
    return front;
  }

  window.RadarRank = { score: score, selectFrontPage: selectFrontPage, MAX_RATING: MAX_RATING };
})();
