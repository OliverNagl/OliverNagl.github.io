/* Full-archive search.
 *
 * This is the one thing the markdown digests genuinely cannot do (spec §7.3): in six
 * months, "did anything come past about pseudosymmetric two-component assembly" should be
 * a two-second query.
 *
 * A prefix-capable inverted index with per-field boosts, built once on load. For the few
 * thousand documents an archive of this kind accumulates it stays well under the 50 ms
 * query-to-render budget, and it removes a dependency from a repo with no build step.
 */

(function () {
  "use strict";

  var FIELD_BOOST = { title: 6, touches: 5, why: 3, reason: 3, authors: 2, abstract: 1, category: 2, venue: 1 };
  var MIN_TERM = 2;

  // Words that are in nearly every abstract in this corpus carry no signal.
  var STOP = new Set(("a an the and or of to in for on with by is are was were be been we our " +
    "this that these those as at from it its can may using used use show shows shown here " +
    "we present study results based which than then but not have has had").split(" "));

  function tokenize(text) {
    return String(text || "")
      .toLowerCase()
      .split(/[^a-z0-9+#.\-]+/)
      .map(function (t) { return t.replace(/^[.\-]+|[.\-]+$/g, ""); })
      .filter(function (t) { return t.length >= MIN_TERM && !STOP.has(t); });
  }

  function Index(docs) {
    this.docs = docs;
    this.postings = new Map();   // term -> Map(docIndex -> weight)
    this.terms = [];             // sorted, for prefix expansion

    docs.forEach(function (doc, i) {
      var seen = new Map();
      Object.keys(FIELD_BOOST).forEach(function (field) {
        var value = doc[field];
        if (Array.isArray(value)) value = value.join(" ");
        var boost = FIELD_BOOST[field];
        tokenize(value).forEach(function (t) {
          seen.set(t, (seen.get(t) || 0) + boost);
        });
      });
      seen.forEach(function (w, t) {
        var p = this.postings.get(t);
        if (!p) { p = new Map(); this.postings.set(t, p); }
        // Sub-linear in term frequency: ten mentions of "protein" is not ten times the
        // evidence of one.
        p.set(i, 1 + Math.log(w));
      }, this);
    }, this);

    this.terms = Array.from(this.postings.keys()).sort();

    // Inverse document frequency, so a rare term like "quasi-equivalence" outweighs
    // "protein" — which appears in nearly every document here.
    var n = docs.length || 1;
    this.idf = new Map();
    this.postings.forEach(function (p, t) {
      this.idf.set(t, Math.log(1 + n / (1 + p.size)));
    }, this);
  }

  Index.prototype._expand = function (prefix) {
    // Binary search for the first term >= prefix, then walk while it still matches.
    var lo = 0, hi = this.terms.length;
    while (lo < hi) {
      var mid = (lo + hi) >> 1;
      if (this.terms[mid] < prefix) lo = mid + 1; else hi = mid;
    }
    var out = [];
    for (var i = lo; i < this.terms.length && this.terms[i].indexOf(prefix) === 0; i++) {
      out.push(this.terms[i]);
      if (out.length >= 64) break;      // a one-letter prefix must not explode the query
    }
    return out;
  };

  Index.prototype.search = function (query) {
    var terms = tokenize(query);
    if (!terms.length) return null;     // null means "no query", not "no results"

    var scores = new Map();
    var self = this;

    terms.forEach(function (term, ti) {
      // The last token is treated as a prefix so results update as you type.
      var isLast = ti === terms.length - 1;
      var matches = self.postings.has(term)
        ? [term]
        : (isLast ? self._expand(term) : []);
      if (isLast && self.postings.has(term)) {
        matches = matches.concat(self._expand(term).filter(function (t) { return t !== term; }));
      }
      if (!matches.length) return;

      var hit = new Map();
      matches.forEach(function (m) {
        var idf = self.idf.get(m) || 1;
        // An expanded prefix is weaker evidence than an exact term.
        var penalty = m === term ? 1 : 0.55;
        self.postings.get(m).forEach(function (w, docIdx) {
          hit.set(docIdx, Math.max(hit.get(docIdx) || 0, w * idf * penalty));
        });
      });
      hit.forEach(function (w, docIdx) {
        var cur = scores.get(docIdx) || { score: 0, matched: 0 };
        cur.score += w;
        cur.matched += 1;
        scores.set(docIdx, cur);
      });
    });

    // An AND query is what a researcher means by "pseudosymmetric two-component
    // assembly" — so full matches come first. But returning nothing when one term is
    // absent is a dead end on a small archive, and the half-remembered query is exactly
    // the case this page exists for. So fall back to partial matches, ranked by how many
    // terms they hit, and tell the caller that is what happened.
    var full = [], partial = [];
    scores.forEach(function (v, docIdx) {
      var hit = { doc: self.docs[docIdx], score: v.score, matched: v.matched };
      (v.matched >= terms.length ? full : partial).push(hit);
    });

    var byScore = function (a, b) {
      if (b.matched !== a.matched) return b.matched - a.matched;
      return b.score - a.score;
    };

    if (full.length) {
      full.sort(byScore);
      full.partial = false;
      return full;
    }
    partial.sort(byScore);
    partial.partial = true;
    return partial;
  };

  window.RadarSearch = { Index: Index, tokenize: tokenize };
})();
