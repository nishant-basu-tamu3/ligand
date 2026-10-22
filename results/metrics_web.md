# Unseen-web results (generated)

336 runs per config per noise level per seed (144 dev / 192 held-out). Seeds: [1, 2].


## Success, Held-out sites (archetypes, vocabulary and layouts never used in dev)

| config | noise L0 | noise L1 | noise L2 | noise L3 | mean |
|---|---|---|---|---|---|
| Ligand-Web (warm: saw dev sites) | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| Ligand-Web (cold on held-out) | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| - value-shape typing | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| - input gate | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| - verify/backtrack | 75.0% | 50.0% | 50.0% | 50.0% | 56.2% |
| - memory | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| Similarity browser (+backtrack) | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| Similarity browser (no backtrack) | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| Similarity browser, lexicon incl. held-out words (ceiling) | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |


## Success, Dev sites (the vocabulary the baseline's lexicon was built from)

| config | noise L0 | noise L1 | noise L2 | noise L3 | mean |
|---|---|---|---|---|---|
| Ligand-Web (warm: saw dev sites) | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| Ligand-Web (cold on held-out) | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| - value-shape typing | 100.0% | 100.0% | 100.0% | 99.3% | 99.8% |
| - input gate | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| - verify/backtrack | 50.0% | 50.0% | 50.0% | 50.0% | 50.0% |
| - memory | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| Similarity browser (+backtrack) | 80.6% | 80.6% | 75.0% | 77.8% | 78.5% |
| Similarity browser (no backtrack) | 80.6% | 80.6% | 75.0% | 77.8% | 78.5% |
| Similarity browser, lexicon incl. held-out words (ceiling) | 80.6% | 80.6% | 75.0% | 77.8% | 78.5% |


## Silent wrong answers, held-out

| config | L0 | L1 | L2 | L3 |
|---|---|---|---|---|
| Ligand-Web (warm: saw dev sites) | 0.0% | 0.0% | 0.0% | 0.0% |
| Ligand-Web (cold on held-out) | 0.0% | 0.0% | 0.0% | 0.0% |
| - value-shape typing | 0.0% | 0.0% | 0.0% | 0.0% |
| - input gate | 0.0% | 0.0% | 0.0% | 0.0% |
| - verify/backtrack | 0.0% | 0.0% | 0.0% | 0.0% |
| - memory | 0.0% | 0.0% | 0.0% | 0.0% |
| Similarity browser (+backtrack) | 0.0% | 0.0% | 0.0% | 0.0% |
| Similarity browser (no backtrack) | 0.0% | 0.0% | 0.0% | 0.0% |
| Similarity browser, lexicon incl. held-out words (ceiling) | 0.0% | 0.0% | 0.0% | 0.0% |

## Cost per task, held-out (mean over noise levels)

| config | page loads | wall ms | asks/task | model-visible tokens* | raw-DOM tokens a DOM-reading LLM would see |
|---|---|---|---|---|---|
| Ligand-Web (warm: saw dev sites) | 2.5 | 404 | 0.04 | 338 | 1010 |
| Ligand-Web (cold on held-out) | 2.5 | 418 | 0.04 | 338 | 1010 |
| - value-shape typing | 5.1 | 600 | 0.00 | 328 | 2029 |
| - input gate | 2.5 | 396 | 0.04 | 338 | 1010 |
| - verify/backtrack | 2.1 | 320 | 0.01 | 335 | 820 |
| - memory | 3.2 | 452 | 0.44 | 362 | 1266 |
| Similarity browser (+backtrack) | 9.0 | 944 | 0.00 | - | 3781 |
| Similarity browser (no backtrack) | 2.2 | 297 | 0.00 | - | 791 |
| Similarity browser, lexicon incl. held-out words (ceiling) | 2.4 | 366 | 0.00 | - | 959 |

*Ligand variants: tool definition + call + returned rows (+60 per ask turn). The page text never enters the model.


## By archetype, held-out, Ligand-Web cold vs similarity browser (mean over levels)

| archetype | Ligand-Web (cold) | Ligand-Web (warm) | similarity+backtrack |
|---|---|---|---|
| jobs | 100.0% | 100.0% | 0.0% |
| restaurants | 100.0% | 100.0% | 0.0% |
| stocks | 100.0% | 100.0% | 0.0% |
| wiki | 100.0% | 100.0% | 0.0% |

## By layout feature, held-out (all levels), Ligand-Web cold vs similarity+backtrack

| feature | value | Ligand-Web | similarity |
|---|---|---|---|
| label_style | aria | 100.0% | 0.0% |
| label_style | placeholder | 100.0% | 0.0% |
| label_style | span | 100.0% | 0.0% |
| label_style | wrap | 100.0% | 0.0% |
| layout | cards | 100.0% | 0.0% |
| layout | dl | 100.0% | 0.0% |
| layout | list | 100.0% | 0.0% |
| link_style | icon | 100.0% | 0.0% |
| link_style | text | 100.0% | 0.0% |

## Revisit and transfer (held-out sites, Ligand-Web cold vs no_memory)

Task index within a site (0 = first visit, 1-2 = revisits of the same site with a new question):

| config | task 0 success | task 1 success | task 2 success | loads t0 | loads t2 | asks t0 | asks t2 |
|---|---|---|---|---|---|---|---|
| Ligand-Web (cold on held-out) | 100.0% | 100.0% | 100.0% | 2.80 | 2.37 | 0.11 | 0.00 |
| - memory | 100.0% | 100.0% | 100.0% | 3.20 | 3.18 | 0.44 | 0.44 |

Across sites of the same archetype (site order within archetype, asks per task):

| config | 1st site | 2nd | 3rd | 4th |
|---|---|---|---|---|
| Ligand-Web (cold on held-out) | 0.06 asks, 100.0% | 0.06 asks, 100.0% | 0.02 asks, 100.0% | 0.00 asks, 100.0% |
| - memory | 0.38 asks, 100.0% | 0.38 asks, 100.0% | 0.62 asks, 100.0% | 0.38 asks, 100.0% |

Crashed runs (counted as failures): 1 of 12096.