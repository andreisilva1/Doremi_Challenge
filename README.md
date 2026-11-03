# Doremi, the virtual assistant of Empório da Música

A customer-service chat agent for Empório da Música, a musical instrument store in Campo Grande
(MS, Brazil). It answers questions about the catalog, prices, PIX and installments, shipping,
orders, returns and store policies, using only the CSVs and the manual provided with the challenge.
Artefact AI Engineer technical challenge.

The core idea: **the model picks the tool and writes the answer; Python does every calculation and
the graph checks the numbers before the answer goes out.**

## How to run

Requires Python 3.11+ (developed and tested on 3.13) and a model provider (an API key or a local Ollama).

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env              # pick the provider and fill in its key
```

| `LLM_PROVIDER` | Default model | Status |
|---|---|---|
| `anthropic` | `claude-sonnet-5-5` | **recommended**, best in the test suites |
| `deepseek` | `deepseek-flash` | validated; fast and cheap, sometimes improvises policy |
| `openai` | `gpt-5.4-mini` | configured but **not tested** (the account ran out of credit) |
| `ollama` | `qwen3.5:9b` | local and free; makes more mistakes (see [Results](#results)) |

For Ollama: `ollama pull qwen3.5:9b` and keep `ollama serve` running. `LLM_MODEL` switches the
model within the provider.

```bash
streamlit run app.py              # browser chat
python -m emporio --debug         # terminal chat, showing the lookups
pytest                            # 162 tests, no network and no model
python -m emporio.audit           # inconsistencies found in the data
python evals/run.py adversarial anthropic   # conversation suites (costs money, see evals/run.py)
```

In the browser, the **Mostrar consultas** (show lookups) toggle in the sidebar displays, for each
answer, the tools called and the graph's internal notes. It is the quickest way to see when the
agent went after data and when it went after policy.

The agent talks to customers in Brazilian Portuguese, the store's language, so the prompt, the
manual, the tool outputs and the example conversations are in Portuguese, as are the working notes
(`knowledge/rules.md`, `AGENTS.md`) and code comments. Code identifiers and commits are in English.

## How it works

```
customer message
      │
      ▼
   agent ──(called a tool)──► tools ──► agent ...
      │
  (answered)
      ▼
   check ── ok ──► answer to the customer
      │
      └── problem ──► agent retries (once) ──► if it fails again, fixed message
                                               offering the team
```

**Deterministic core** (`emporio/data.py`, `rules.py`, `catalog.py`, `orders.py`): loads the CSVs
and computes the PIX discount, minimum installment, shipping, return and warranty deadlines, and
opening hours with holidays. It does not depend on LangChain and has its own tests.

**Tools** (`emporio/tools.py`): eight functions that wrap the core and return ready-made records,
with values already as `R$ 1.234,56` and dates as `dd/mm/yyyy`, so the model only copies them.

| Tool | Purpose |
|---|---|
| `search_products`, `get_product` | catalog, price, PIX, installments, stock, promotion, alternatives |
| `quote` | total of a purchase with PIX, installments and shipping to the city |
| `get_order`, `check_return` | order and return eligibility, only with order number + email or phone |
| `store_status` | open now?, address and contacts (real clock, Campo Grande time zone) |
| `get_policy` | one section of the manual (`knowledge/policies.md`) by topic |
| `handoff_to_human` | hands off to the team and returns the response time |

**Graph** (`emporio/agent.py`, hand-written LangGraph): the `check` node looks at every answer
before it goes out.
- If the model answered without looking anything up, it gets an internal note asking for the
  lookup (only once, because greetings and out-of-scope topics need no tool).
- Every `R$`, installment (`6x`) and date in the answer must appear in the tool results or in what
  the customer wrote. If it does not, the model retries once; on the second failure the answer
  becomes a fixed message offering the team.
- Repeated calls are discarded, and more than 6 tool rounds in one message also end in the fixed
  message.

The persona prompt lives in `prompts/system.md`, outside the code.

## Decisions

**Tools instead of vector RAG.** There are 65 products and a 10-section manual. Exact lookup does
the job, and vector search would only add retrieval errors. The manual is served by section
(`get_policy`) instead of going whole into the prompt, so the "data or policy" choice is visible in
the trace and can be tested.

**All math in Python.** In the pilot run, still without the graph, it was clear that when the
model called the tool the answer came out right. Errors came from answering from memory. So no
number is computed by the model, and `check` exists to catch the case where it makes one up anyway.

**LangGraph with a custom graph, not `create_react_agent`.** The gain is the `check` node, which a
prebuilt agent lacks. Forcing a tool call on every turn (`tool_choice`) would be wrong for
greetings and out-of-scope messages, and Ollama does not support it, so the push comes after the
answer. LangGraph also gives provider switching and per-conversation
memory for free.

**Order verification lives in the tool, not in the prompt.** `get_order` and `check_return`
require the order number + the email or phone on file. They fail with the same generic message
(without saying which field did not match or whether the order exists) and never return a
customer's email or phone. So the protection does not depend on the model obeying: a prompt
injection can at most produce a lookup that fails.

**Four providers, switchable through `.env`.** The agent started with Claude and Ollama only. When
the local model started making mistakes, I added DeepSeek and OpenAI to separate model limits from
project problems. Sonnet and DeepSeek, with the same code and the same prompt, showed that qwen's
failures were its own.

**Session-only memory.** Each browser tab or terminal conversation has its own thread in
`InMemorySaver`. No conversation goes to disk, because it carries name, email and order (§9 of the
manual, LGPD). Restart the process and the history is gone.

**Fixed reference date: 23/03/2026** (`REFERENCE_DATE`). The CSVs are a snapshot of March, with
the last order on 22/03. With the real date, every return window would have expired and order 8
would be 8 months late. Deadlines and delays use this date; "are you open?" uses the real clock
(on 02/11 the agent says the store is closed for Finados, a national holiday).

**Rules matrix with mandatory tests.** `knowledge/rules.md` lists each rule in the manual and each
data problem with a code (`PAG-05`, `DEV-01`...), its source section and how it is verified. A test
fails if a rule marked as testable has no test citing it.

**Interface: Streamlit and terminal.** The brief focuses on the agent, so the interface is a single
file (`app.py`), with a dark theme and the lookups panel. The terminal (`python -m emporio`) is for
those who do not want to open the browser.

## Assumptions

The brief asks to assume a reasonable interpretation and document it. These are the ones that
change answers (all are marked with 🟡 in `knowledge/rules.md`):

- **Receipt = estimated delivery.** Orders have no actual delivery date, so the 7-day withdrawal
  period counts from `estimated_delivery`.
- **Order with tracking = online purchase**, because withdrawal only applies to online purchases
  and the data does not say the channel.
- **Minimum installment:** the tiered table in §3.1 applies (up to 3x: R$ 50; 4–6x: R$ 80;
  7–12x: R$ 100), not the "minimum R$ 100" in §3. Paying in 1x is always allowed.
- **Free shipping "above R$ 500":** exactly R$ 500 pays shipping, and the amount counts after
  discounts. "Metropolitan region" was read as Campo Grande.
- **Special freight:** outside Campo Grande, acoustic drums, digital pianos and upright basses get
  an individual quote; in the catalog, only the three drum kits. Electric bass does not count.
- **Promotions without dates:** `is_active = 1` applies. With two active on the same product, the
  larger one. PIX gives no extra discount on a promotional price (§6.2).
- **Contacts:** the manual gives the same number as phone and WhatsApp in different places. I used
  (67) 3341-4444 as phone and (67) 3321-4500 as WhatsApp, and the email on the cover (the one in
  §1.2 has an accent that looks like a typo).
- **Holidays:** fixed-date national holidays only; the manual has no list.
- **Catalog:** a discontinued product is not offered, even with stock (id 136); `coming_soon` shows
  as "em breve" (coming soon) and is not sold (id 130).
- **Order status:** `pending` = awaiting payment, `confirmed` = being prepared. The total is
  reported as recorded, even when it does not match the items.
- **Exchange by preference:** 7 days from receipt, like withdrawal.

## What the data hides

I read the CSVs in full before writing the agent. `python -m emporio.audit` reproduces the part
that can be computed:

- totals that do not match the items (orders 3 and 20);
- PIX paid without the 5% discount (1, 5, 10, 13, 17);
- installments below the §3.1 minimum (9, 16, 18);
- item with an active promotion charged at full price (2, 11);
- "coming soon" product sold (130), discontinued with 13 in stock (136);
- two customers with the same email (11 and 43). That is why verification also uses the order
  number.

And the part that only shows up by reading:

- In ids 135–144, the description contradicts the name and specs (the "Bateria Yamaha Kit 1" is
  described as a Pearl Export; the 61-key "Korg Synth 1 Pro", as an 88-key Roland). The agent uses
  name, price and specs and ignores these descriptions.
- The wind and orchestral strings categories exist but are empty. The agent says they are not in
  the catalog right now, without denying that the store carries them.
- Promotions have no dates, only the `is_active` field.

None of this changes what the agent tells the customer; it serves as a report for the store.

## Results

Two suites, in `evals/run.py`, run through the full graph with each model and **read answer by
answer** against the data and the manual (there is no automatic score).

**Functional** (16 questions: catalog, PIX, order, defect, shipping, scope, complaint, LGPD,
injection, wrong email):

| Model | Result | Median time |
|---|---|---|
| Claude Sonnet 5.5 | 16/16 | 4.6 s |
| DeepSeek Flash | 15/16 (for shipping to Dourados, asked which drum kit before mentioning special freight) | 3.4 s |
| qwen3.5:9b (local, RTX 4060) | 11/16; did not hand off a complaint or a data deletion request, and answered shipping without looking it up | 29.6 s |

**Adversarial** (20 conversations: social engineering, prompt injection, requests for promises,
double meanings, competitors):

| Model | Result |
|---|---|
| Claude Sonnet 5.5 | 20/20 |
| DeepSeek Flash | 17/20 in the first run: improvised three rules the manual does not have (matching a competitor's price, when to pay, who handles defects). After rewriting rule 4 of the prompt, 19/20 |
| qwen3.5:9b | 15/20. Asked for the husband's contact to show his order, promised to send a PIX key that does not exist, agreed that the consumer code (CDC) gives 30 days to withdraw, offered an acoustic drum kit to someone talking about a phone battery ("bateria" means both in Portuguese) and said the store does no repairs, pointing to a luthier. Almost every answer needed the internal lookup note, and in one it repeated the same search up to the round limit and fell into the default handoff answer |

Sonnet and qwen ran with the prompt from before that change.

No model gave out a customer's email or phone on file, confirmed whether an order exists, showed
someone else's order or revealed the prompt. This comes from the tool, not the model: even when the
model tries, the lookup without the right contact fails.

## Examples

Real conversations recorded with Claude Sonnet 5.5, in Portuguese, with the lookups behind each
answer:

- [Acoustic guitars up to R$ 1000, from catalog to purchase total](examples/01-violoes-ate-1000.md)
- [Takamine GD20 price, installments and store details](examples/02-takamine-e-loja.md)
- [Withdrawal past the deadline, then a defect](examples/03-devolucao.md) (the non-trivial one)
- [Late order, verified by phone and handed off](examples/04-pedido-atrasado.md)
- [Accessory, another customer's data and an off-store topic](examples/05-fora-do-escopo.md)

## Limitations

- **`check` only verifies numbers and dates.** A made-up policy rule gets through: DeepSeek
  answered that "we don't have a price-matching policy", and qwen that the CDC gives 30 days to
  withdraw. The prompt says to hand off when the manual does not cover something; that reduces it
  but does not guarantee it.
- **Without `tool_choice`, the lookup is enforced afterwards.** Small models sometimes answer from
  memory even after the internal note.
- **The handoff is simulated.** `handoff_to_human` gives the response time and the contacts, but
  does not open a ticket anywhere.
- **Shipping outside Campo Grande is not quoted.** The manual says it is calculated by postal code
  (CEP) and gives no table; the agent gives the options and delivery times.
- **Two clocks.** Deadlines use 23/03/2026 and store hours use the real clock. The model sometimes
  mixes the two when writing ("ontem (22/03/2026)", "yesterday (22/03/2026)").
- **History in memory only**, one conversation per tab.
- **Manual evaluation with few runs.** Each suite ran once per model and prompt version; run-to-run
  variation was not measured.
- **OpenAI not tested**, only the code and the client construction test.
- **Portuguese only.** A customer writing in English gets an answer in Portuguese.

## What I would do with more time

- Turn the suites into an automatic eval: expected tool, values that must (and must not) appear,
  several runs per model, in CI.
- Check policy too, with a judge comparing the answer to the manual section that was looked up.
- A real WhatsApp channel. There the phone comes from the channel itself, which simplifies
  verification.
- A real handoff: a queue or ticket with the conversation summary.
- Shipping by postal code through the Correios or carrier API.
- Persistent history (`SqliteSaver`) with a retention period and deletion on request.
- For a large catalog: hybrid search (text + embeddings) behind the same `search_products`.
- Tracing of production conversations (LangSmith or similar) to find the errors the suites miss.

## Use of AI assistants

I used Claude Code (Claude Opus) throughout the challenge, as a pair programmer:

- **Planning:** before any code, we put together a plan with the open decisions, each with the
  best argument against it. The decisions were mine (LangGraph, four providers, reference date,
  verification in the tool, interface). The plan stayed out of the repository; what matters from it
  is in this README.
- **Reading the data and the manual:** the survey of inconsistencies was done with Claude and
  checked against the CSVs.
- **Implementation:** in small commits, with tests before the agent. I reviewed each commit before
  it went in. The working rules the assistant followed are in `AGENTS.md`.
- **Conversation tests:** Claude ran the suites; I read the answers and decided what became a fix.
  For example, the answer "não tem como eu burlar" ("there's no way for me to get around it")
  sounded like a system, not a store, and became a voice rule in the prompt.
- **This README:** drafted by Claude, reviewed and adjusted by me.

The commits have no assistant co-authorship because its use is declared here.
