# LLM configuration and token budgeting

Genify uses **Databricks Foundation Model** serving endpoints for planning, section generation, interactive questions, and YAML merge correction. All limits are read from [`src/genify/app.yaml`](../src/genify/app.yaml) via [`get_config()`](../src/genify/backend/config.py)—do not hardcode budgets in code.

**Related:** [agentic-loop.md](agentic-loop.md) (where LLM runs), [design-decisions.md](design-decisions.md) (ADR-19: truncation vs tokens), [extending.md](extending.md) (prompt context knobs).

---

## 1. Two independent budgets

| Layer | Mechanism | What it limits |
|-------|-----------|----------------|
| **Message token budget** | [`trim_history()`](../src/genify/backend/llm/token_manager.py) with **`llm.max_prompt_tokens`** | Total **tiktoken** (`cl100k_base`) tokens across chat **messages** passed to `llm.chat()` (system + user + assistant history). |
| **Embedded text (characters)** | **`context_truncation.*`** via [`truncate_chars` / `tail_chars`](../src/genify/backend/context_text.py) | Size of **MCP context blobs** and tails **inside** a single user message (planning summary, section context, prior YAML tail, etc.). |

They work together: you can keep **`max_prompt_tokens`** high while still capping how much raw profiler/UC JSON is **stringified** into the prompt via **`context_truncation`**, and vice versa.

---

## 2. `config.llm` (main endpoint)

| Key | Role |
|-----|------|
| `endpoint_name` | Databricks serving endpoint name (overridable with **`LLM_ENDPOINT_NAME`**). |
| `max_tokens` | **Maximum completion tokens** per `chat()` call (output ceiling) for the main model. |
| `max_prompt_tokens` | **Input-side** budget for **`trim_history()`** before each `llm.chat()` in planner and executor—not the provider’s full context window, but the cap Genify enforces on serialized messages. |
| `temperature` | Sampling temperature for `chat()`. |

**Logging:** [`LLMClient.chat`](../src/genify/backend/llm/client.py) logs **input token count** (tiktoken over message contents) per call. Compare **actual** inputs to **`max_prompt_tokens`**.

---

## 3. `config.context_truncation` (characters)

| Key | Typical use |
|-----|----------------|
| `planning_chars_per_key` | Each MCP context key in the **planning** prompt ([`planner.py`](../src/genify/backend/agent/planner.py)). |
| `executor_section_chars_per_key` | Each key in the **section context** blob ([`executor.py`](../src/genify/backend/agent/executor.py)). |
| `prior_yaml_tail_chars` | Tail of **prior merged YAML** in section / incorporate prompts. |
| `interactive_known_data_chars` | **Known data** prefix in interactive question prompts. |

Use **`0`** where helpers support it to mean “no limit” for that path (see [extending.md](extending.md)).

---

## 4. `config.yaml_merge`

| Key | Role |
|-----|------|
| `merge_max_retries` | On merge validation failure, up to this many **extra `llm.chat` calls** per section to rewrite the fragment ([`merge_section_output`](../src/genify/backend/agent/executor.py)). |
| `nested_validation` | `off` \| `strip` — alignment with template for merge. |
| `canonical_json_enabled` | If `true`, dual-write parsed YAML to **`sessions.generated_json`** (optional downstream use). |

---

## 5. Summarizer endpoint (configured, not used by the agent today)

`app.yaml` / env expose **`SUMMARIZER_ENDPOINT_NAME`**, **`summarizer_max_tokens`**, **`summarizer_temperature`**. [`get_summarizer_llm_client()`](../src/genify/backend/llm/client.py) exists for future use (e.g. compressing large context). **The gather → plan → execute path does not call the summarizer**—only **`get_main_llm_client()`** is used in [`planner.py`](../src/genify/backend/agent/planner.py) and [`executor.py`](../src/genify/backend/agent/executor.py). **Do not** include summarizer calls in session cost estimates unless you add code that uses it.

---

## 6. Where `trim_history` runs

Applied before **`llm.chat()`** in **`generate_plan`**, **`execute_step`** / **`incorporate_answer`**, and **`merge_section_output`** (merge correction). Not invoked from [`core.py`](../src/genify/backend/agent/core.py) directly—[`run_agent`](../src/genify/backend/agent/core.py) delegates to planner/executor.

Strategy: keep **system** messages, keep the **four** most recent non-system messages, then pack older middle messages until under **`max_prompt_tokens`** (see `token_manager.py`).

---

## 7. Estimating maximum cost per LLM call

Serving pricing is **workspace- and model-specific**. Use [Databricks pricing](https://www.databricks.com/product/pricing/product-pricing/instance-types) and your contract, or **billing / system tables** for observed spend.

### 7.1 Upper bound (worst-case single request)

For **one** `chat()` on the **main** endpoint:

- **Output tokens (billable upper bound):** at most **`config.llm.max_tokens`** if the model fills the completion.
- **Input tokens (conservative ceiling):** after **`trim_history`**, use logged input tokens, or bound by **`≤ max_prompt_tokens`** for planning.

If **price per 1K input tokens** \(P_{\text{in}}\) and **price per 1K output tokens** \(P_{\text{out}}\) apply:

\[
\text{max cost per call} \lesssim
\frac{T_{\text{in}}}{1000} P_{\text{in}} +
\frac{T_{\text{out}}}{1000} P_{\text{out}}
\]

Conservative substitutions: \(T_{\text{in}} =\) **`max_prompt_tokens`** (or logged), \(T_{\text{out}} =\) **`max_tokens`**. This is a **theoretical upper bound**, not typical usage.

### 7.2 Observed cost

Use **`LLMClient.chat`** logs (input tokens) and workspace **usage** / system tables for real dollars.

---

## 8. Estimating LLM cost per session

One **`run_agent`** from plan through **complete** uses only the **main** endpoint in stock code.

**Rough structure:**

1. **Plan:** **1** `llm.chat` when `plan` is empty (cached plan → **0** on later streams).
2. **Per plan step** (N = `len(plan)`): at least **1** generation call; **interactive** steps add question/partial calls; **merge** adds up to **`merge_max_retries`** correction calls per step when validation fails.

\[
C_{\text{calls}} \lesssim 1 + \sum_{i=1}^{N} (1 + q_i + m_i)
\]

- \(q_i\) = extra interactive LLM calls for step \(i\) (often **0** hands-off).
- \(m_i \in [0, \texttt{merge\_max\_retries}]\) = merge correction rounds.

**Session LLM cost** \(\lesssim \sum_k \text{cost}(\text{call } k)\) using §7.1 or average observed tokens.

**Multi-table:** One plan/execute loop; MCP gather may touch **multiple tables** (warehouse cost). **Not** extra LLM loops unless you change the agent.

**Non-LLM:** MCP/SQL warehouse, Lakebase, **SSE** transport are separate from LLM token billing.

---

## 9. Operational checklist

- [ ] **`max_tokens`** large enough for YAML sections; lower for a harder output cap.
- [ ] **`max_prompt_tokens`** large enough that **`trim_history`** does not drop needed conversation (interactive sessions).
- [ ] **`context_truncation`** when MCP strings dominate before tokenization.
- [ ] Monitor logs and **`merge_max_retries`** (extra calls on merge failures).

---

## 10. SSE vs LLM limits

**Server-Sent Events** are not LLM tokens. The default agent uses **`LLMClient.chat()`** (not streaming completions for the main loop). Budgeting is **`chat()`** payloads + **`max_tokens`**.
