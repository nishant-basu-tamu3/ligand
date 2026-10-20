### Cold start, v1 vs v2
| tools | engine | success dev | success test* | success **test2** | wrong-bind | ask rate | router ms (seq) | router ms (servers in parallel**) |
|---|---|---|---|---|---|---|---|---|
| 37 | v1 | 95.0% | 95.0% | **92.3%** ± 0.5 | 1.7% | 40.7% | 10 | 10 |
| 37 | v2 | 97.5% | 95.0% | **92.5%** ± 0.0 | 1.7% | 26.5% | 2 | 1 |
| 100 | v1 | 86.8% | 89.8% | **81.5%** ± 0.5 | 3.2% | 36.6% | 10 | 10 |
| 100 | v2 | 97.5% | 94.8% | **92.2%** ± 0.5 | 1.7% | 27.6% | 7 | 3 |
| 217 | v1 | 86.0% | 76.7% | **77.8%** ± 2.2 | 7.8% | 33.0% | 20 | 20 |
| 217 | v2 | 97.5% | 93.8% | **89.5%** ± 1.0 | 2.2% | 27.7% | 16 | 3 |
| 500 | v1 | 83.8% | 74.0% | **78.2%** ± 1.7 | 6.2% | 33.8% | 34 | 34 |
| 500 | v2 | 97.5% | 92.8% | **86.8%** ± 1.3 | 1.7% | 29.0% | 291 | 46 |

### Ablation at 217 tools
| engine (217 tools) | success dev | success test* | success test2 | wrong-bind | ask rate | router ms (seq) |
|---|---|---|---|---|---|---|
| v1 (baseline) | 86.0% | 76.7% | 77.8% | 7.8% | 33.0% | 20 |
| + type gate, index, goal-directed search | 95.0% | 88.0% | 86.8% | 0.8% | 51.0% | 2902 |
| + per-server bidding only (no type gate) | 95.0% | 83.0% | 89.2% | 5.8% | 37.9% | 39 |
| v2 without contrastive memory | 97.5% | 93.0% | 89.2% | 2.4% | 37.1% | 16 |
| v2 (all) | 97.5% | 93.8% | 89.5% | 2.2% | 27.7% | 16 |

### Learning (16 passes, online)
| engine | feedback | ask rate (passes 3-16) | success (passes 3-16) | wrong-bind (passes 3-16) |
|---|---|---|---|---|
| v1 | clean | 5.2% | 94.8% | 1.8% |
| v2_nocontrast | clean | 4.4% | 95.4% | 1.5% |
| v2 | clean | 4.0% | 94.8% | 2.2% |
| v1 | 30% wrong | 15.5% | 91.2% | 5.2% |
| v2 | 30% wrong | 7.9% | 92.9% | 3.9% |

### Held-out wording (train: new parameters absent, wording A/B; test: new parameters, wording C/D)
| engine | cold success | trained success | cold wrong-bind | trained wrong-bind | cold ask | trained ask |
|---|---|---|---|---|---|---|
| v1 | 88.3% | 84.7% | 3.3% | 8.3% | 45.0% | 27.0% |
| v2_nocontrast | 90.0% | 85.7% | 3.3% | 7.3% | 40.0% | 27.3% |
| v2 | 90.0% | 85.0% | 3.3% | 8.0% | 37.3% | 26.7% |

### Tokens per task, 37 tools, test2 split (cold)
raw_mcp        input    7182  cost    4078
tool_search    input    2297  cost    1584
code_mode      input    1869  cost    1823
cli_unfamiliar input    3655  cost    1806
cli_familiar   input     927  cost     771
ligand         input    1454  cost    1189
ligand_v1      input    1560  cost    1222

### Per-template success at 217 tools (v1 -> v2)
t01: 100.0% -> 100.0%
t02: 100.0% -> 100.0%
t03: 50.0% -> 100.0%
t04: 100.0% -> 100.0%
t05: 100.0% -> 100.0%
t06: 75.0% -> 75.0%
t07: 60.0% -> 100.0%
t08: 75.0% -> 100.0%
t09: 100.0% -> 100.0%
t10: 100.0% -> 100.0%
t11: 0.0% -> 100.0%
t12: 55.0% -> 62.5%
t13: 100.0% -> 100.0%
t14: 100.0% -> 100.0%
t15: 92.5% -> 100.0%
t16: 70.0% -> 100.0%
t17: 75.0% -> 100.0%
t18: 75.0% -> 75.0%
t19: 100.0% -> 100.0%
t20: 100.0% -> 100.0%
t21: 42.5% -> 45.0%
t22: 75.0% -> 75.0%
t23: 75.0% -> 75.0%
t24: 85.0% -> 100.0%
t25: 100.0% -> 100.0%
t26: 25.0% -> 100.0%
t27: 100.0% -> 100.0%
t28: 75.0% -> 100.0%
t29: 100.0% -> 100.0%
t30: 100.0% -> 100.0%

(seeds [0, 1, 2, 3, 4], passes 16, 2537s)
