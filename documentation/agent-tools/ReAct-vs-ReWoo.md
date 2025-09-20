# ReAct — General Pattern

**Definition.** ReAct interleaves step-by-step reasoning with external actions: *think → act → observe → repeat*. It improves interpretability and performance on multi-hop tasks such as HotpotQA, FEVER, ALFWorld, and WebShop by generating explicit “thoughts” and tool calls in a single trajectory. ([arXiv][1])

**When to use.**

* Each new observation strongly informs the *very next* move (retrieval hops, web/shop navigation, diagnosis). ([arXiv][1])
* You want auditable traces (human-readable “why” along with “what”). ([arXiv][1])

**Observed benefits (studies).**

* Outperforms CoT-only or act-only baselines on QA and interactive tasks; reduces hallucinations by verifying with tools. ([arXiv][1])

**Minimal loop (language-agnostic pseudocode in Python)**

```python
def react_loop(goal, *, max_iters=32, tool, reason, update, done):
    """
    reason(ctx) -> thought (text)
    tool(thought, ctx) -> observation (data)
    update(ctx, thought, observation) -> ctx'
    done(goal, ctx) -> bool
    """
    ctx = {}
    for _ in range(max_iters):
        if done(goal, ctx): break
        thought = reason(ctx)
        observation = tool(thought, ctx)          # exactly one action per turn
        ctx = update(ctx, thought, observation)
    return ctx
```

**Notes from later research (optional extensions).**

* Add short post-mortem “reflection” between attempts to raise pass\@1 on brittle tasks (Reflexion). ([arXiv][2])
* For highly branchy problems, a tree-search variant (LATS) can outperform greedy ReAct. ([arXiv][3])

---

# ReWOO — General Pattern

**Definition.** ReWOO (Reasoning WithOut Observation) *decouples* planning from tool I/O: the model first drafts a **plan/sketch** (no tools), then executes the required calls (often in batch/parallel), and finally synthesizes results. This reduces token/tool churn and is robust to tool failures. Reported results: up to **≈5× token efficiency** and **accuracy gains** on HotpotQA vs. interleaved baselines. ([arXiv][4])

**When to use.**

* Tool calls are expensive/slow or flaky; multiple independent reads can be parallelized. ([arXiv][4])
* You want the plan auditable *before* spending on tools. ([arXiv][4])

**Observed benefits (studies).**

* Fewer round-trips, better latency control; maintains or improves accuracy while cutting tokens. ([arXiv][4])

**Minimal loop (language-agnostic pseudocode in Python)**

```python
def rewoo_loop(goal, *, max_plans=8, plan_fn, batch_exec, synthesize, decide, done):
    """
    plan_fn(ctx) -> plan = {calls: [ToolCallSpec...], assumptions: [...], success_criteria: [...]}
    batch_exec(plan.calls) -> observations (list/map)
    synthesize(ctx, plan, observations) -> ctx'
    decide(ctx) -> {"answer" | "next"} and maybe sub-goal
    done(goal, ctx) -> bool
    """
    ctx = {}
    for _ in range(max_plans):
        if done(goal, ctx): break
        plan = plan_fn(ctx)                       # no tools here
        observations = batch_exec(plan["calls"])  # parallel/timeout/partial-ok
        ctx = synthesize(ctx, plan, observations)
        if decide(ctx) == "answer":
            break
    return ctx
```

**Evaluation pointers.** Use agent benchmarks to compare modes on success rate, tool cost, wall-time, and failure types (timeouts, 4xx/5xx). AgentBench provides multi-environment evaluation patterns relevant to both ReAct and ReWOO. Recent surveys also outline consistent agent KPIs. ([arXiv][5])

---

## Quick chooser

* **Local, incremental info needed each step?** → **ReAct.** ([arXiv][1])
* **Many reads, high latency/cost, or flaky tools?** → **ReWOO** (plan first, batch/parallel). ([arXiv][4])


[1]: https://arxiv.org/abs/2210.03629?utm_source=chatgpt.com "ReAct: Synergizing Reasoning and Acting in Language Models"
[2]: https://arxiv.org/abs/2303.11366?utm_source=chatgpt.com "Reflexion: Language Agents with Verbal Reinforcement Learning"
[3]: https://arxiv.org/abs/2310.04406?utm_source=chatgpt.com "Language Agent Tree Search Unifies Reasoning Acting and Planning in Language Models"
[4]: https://arxiv.org/abs/2305.18323?utm_source=chatgpt.com "ReWOO: Decoupling Reasoning from Observations for Efficient Augmented Language Models"
[5]: https://arxiv.org/abs/2308.03688?utm_source=chatgpt.com "[2308.03688] AgentBench: Evaluating LLMs as Agents"
