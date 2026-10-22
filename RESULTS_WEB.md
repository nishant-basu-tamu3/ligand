# Ligand-Web: unseen-web test (scripted agents, no LLM)

Question: does binding by *shape* (receptor idea) work better in unknown territory than binding by label similarity?
Setup: 28 generated sites (8 archetypes), served to headless Chromium through request interception. Dev = flights, weather, library, shop.
Held-out = jobs, restaurants, stocks, wiki: new archetypes, label words never used in dev, new layouts (definition lists, placeholder/aria-only labels,
icon-only links). Noise levels are cumulative: L1 cookie wall + delayed promo popup + decoy forms/ads, L2 + flaky 503s, shuffled rows, sponsored rows,
L3 + JS-rendered results, 3-row pagination. 2 seeds x 4 levels x 84 tasks x 2 phrasings per config (12,096 runs; 1 crashed, counted as failure).
Full tables: `results/metrics_web.md`, figures `results/fig_web_noise.png`, `results/fig_web_cost.png`. Reproduce: `python -m webbench.run_web --seeds 2 && python -m webbench.report_web && python -m webbench.figures_web` (~50 min).

## Result (held-out sites, success, same at all 4 noise levels)
| agent | success | wrong answers | page loads/task | asks/task |
|---|---|---|---|---|
| Ligand-Web, cold | 100% | 0% | 2.5 | 0.04 |
| Ligand-Web, no memory | 100% | 0% | 3.2 | 0.44 |
| Ligand-Web without verify/backtrack | 56% | 0% | 2.1 | 0.01 |
| Ligand-Web without value-shape typing | 0% | 0% | 5.1 | 0 |
| Label-similarity browser (dev words) | 0% | 0% | 9.0 | 0 |
| Label-similarity browser that knows the held-out words | 100% | 0% | 2.4 | 0 |
Dev sites: Ligand 100%; label-similarity browser 78.5% (even with all words: no echo filtering / twin-column ties).

## What this shows, bluntly
- Your hypothesis holds in one specific sense: when the words are new, a label-matching agent collapses (0%) and a shape-matching agent doesn't (100%), through noise, popups, flaky pages, JS rendering and pagination.
- It does NOT beat an agent that already knows the words: that ties at 100% on held-out. A real LLM knows the words, so the practical win is cost, not accuracy: 338 tokens reach the model vs ~1,010 page tokens for a DOM-reading agent, and the baseline-with-backtracking needs 9 loads.
- Load-bearing parts: value-shape typing (money/time/percent/temp/phone columns bind by what the values look like) and verify/backtrack (the decoy search box is first in the DOM). The input gate did nothing measurable here.
- Memory: asks fell 0.44 -> 0.06/task and revisit page loads 2.8 -> 2.4 (vocabulary learned from answered asks transfers across sites).
- Ties between same-shape columns (salary vs bonus, price vs day-high, capital vs largest city) are not solved by shape; Ligand asks (oracle answers). 100% includes those ask turns.

## Why you shouldn't over-trust it
- Sites, noise and tasks are mine; the perception layer (forms/tables/cards/lists/dl) was written knowing those structure families. Unseen = vocabulary, archetype, label placement, flow; not unseen DOM structure.
- The shape ontology (money, time, percent, ...) and the want-word lexicon are hand-written. The "0%" baseline is by construction: it is lexical-only with words it never saw.
- Asks are answered by an oracle. No LLM, no real sites, no auth, no CAPTCHAs, no images. Tokens are estimates (3.5 chars/token).
- Next test that matters: a real LLM agent on real sites, with Ligand-Web as its only browsing tool.
