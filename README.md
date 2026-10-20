# Ligand: intent-bound tool routing for agents

An experiment in a third way for agents to use tools, besides "read a catalog of MCP tools" and "drive a CLI".

**Idea (from cell signalling).** A hormone doesn't look up its receptor. It is released and binds whatever fits its shape;
the cell that binds does the work. Here the agent never sees a tool list. It emits an *intent*, and the tools whose
**shape** fits (can accept what the agent has, can produce what it wants) bind to it.

```
agent ── emit{goal, have, want} ──▶  LIGAND ── (binds 1–3 tools, runs them, filters, shapes) ──▶ ordinary MCP servers
      ◀── rows{only the wanted fields} ──                                         (github, slack, notion, calendar, files, crm)
```

The agent sees **one** tool (`emit`, ~290 tokens). Everything between intent and result happens outside the model's context.
Ligand sits in front of *unmodified* MCP servers: it reads their `list_tools()` schemas (`inputSchema`, `outputSchema`) and builds receptors from them.

| Biology | Here |
|---|---|
| ligand / receptor shape complementarity | `have`/`want` vs tool params/outputs: a chain binds only if it can consume what you have and produce what you want |
| signal cascade | chains of up to 3 tools wired by matching output fields to input params (types inferred from description head-phrases) |
| affinity | semantic match of goal ↔ tool description × shape fit × learned success |
| spinal reflex | repeated successful chains become "reflexes" (centroid of their goals) that raise affinity next time |
| receptor sensitisation / decay | outcome feedback (`prev=[ticket, ok]`) boosts or suppresses chains; failing reflexes are deleted |
| "I can't tell which receptor" | `ask`: close call → return candidate chains, agent picks; `need`: near-miss → return the field names that exist |

## The protocol (one tool)
```
emit(goal="email of whoever wrote PR 117", have={"repo":"acme/infra","number":117}, want=["email"], prev=["t41", true])
 → {"t":"t42","rows":[{"email":"raj@acme.io"}]}
 → {"t":"t42","ask":[{"k":0,"via":"github.get_pull_request>github.get_github_user"},{"k":1,"via":"github.get_issue>github.get_github_user"}]}   # then emit(pick={t,k})
 → {"t":"t42","need":["message"],"fields":["name","text","ts"]}                                                                               # then re-emit with a listed name
```

## v2 (second iteration)
The blood-stream bus got an address system and organs instead of random drift:
- **Type-address gate** (leukocyte homing): fields carry a type; conflicting types cannot bind (`database_name` ≠ `database_id`).
- **Adjacency index + goal-directed search**: candidate tools come from a precomputed output→input graph and only chains that can reach a wanted field are explored.
- **Per-server bidding** (like ARP): each server searches only its own tools; servers with nothing to contribute abstain; bids are calibrated per server.
- **Contrastive memory**: when the agent resolves an `ask`, the rejected candidates are remembered as negatives.
Result (fresh test2 split): 217 tools 77.8% → 89.5%, 500 tools 78.2% → 86.8%, silent wrong answers 7.8% → 2.2%; 500-tool latency and wording shift remain open. See RESULTS.md.

## Run it
```bash
pip install numpy "mcp<2" matplotlib          # mcp 2.x changed its Python API; this prototype targets 1.x
python -m tests.test_mcp_e2e                  # real MCP: client → Ligand server → 6 stdio MCP servers (≈20 s)
python -m bench.probe --v                     # dev-split cold-start probe with failure details
python -m bench.run_bench                     # v1 benchmark → results/results.json  (≈5 min on 2 cores)
python -m bench.report ; python -m bench.figures
python -m bench.run_v2                        # v1 vs v2, 37-500 tools, ablations → results/results_v2.json (≈40 min on 2 cores)
python -m bench.report_v2 ; python -m bench.figures_v2
python -m ligand.mcp_server --memory mem.json # the server itself (stdio); point an MCP client at it
```

## Layout
- `ligand/engine.py` binding, chain search, scoring, memory, reflexes, persistence · `ligand/protocol.py` the `emit` tool definition
- `ligand/mcp_server.py` Ligand as an MCP server · `ligand/mcp_bridge.py` talks to ordinary MCP servers · `ligand/mcp_backends.py` the 6 demo servers
- `ligand/world.py` simulated company + 37 deliberately confusable tools · `ligand/distractors.py` +180 plausible distractor tools
- `bench/` tasks (20 templates × 2 × 4 phrasings), baselines, runner, tuning, report, figures · `tests/test_mcp_e2e.py`

See **RESULTS.md** for numbers and, more importantly, for what these experiments do *not* show.
