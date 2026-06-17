# Phase 0 — Data Model & Client Config

**Status: COMPLETE**

Phase 0 defines the data shapes the whole system reads and writes. No browser code
yet — this is the spine. Every later phase (perception, recording, replay, healing)
inherits these shapes, which is why it comes first.

---

## Three governing principles

1. **Structure is stable; data is variable.** If a value differs between two clients
   or two environments, it lives in **ClientConfig** as a `${variable}`. If it's the
   same everywhere, it lives in the **Step** structure.
   - `username` → config. "There is a username field, role=textbox, name='User ID'" → step.

2. **Locators are semantic and ranked, never absolute.** A step stores an *ordered*
   list of ways to find an element: role+name first, label/placeholder next, visible
   text after, CSS/XPath as last resort. The replay engine tries them in order; when
   all fail, the healer wakes up. This is what lets one recording survive Oracle
   updates and run across clients.

3. **The saved step is the single unit of truth.** The agent *writes* it (Phase 4),
   the replay engine *reads* it (Phase 5), the healer *repairs* it (Phase 6). All
   three point at the same object.

---

## The layer stack

```
Primitives    -> always-available mechanical actions (click, type, wait, screenshot, scroll, press)
   |             Python knows HOW to do these. The AI decides WHICH to use.
Blocks        -> named, parameterized, reusable sequences of steps (login, go_home)
   |             Authored once, referenced by name. Fix in one place, all tests inherit.
InstructionSets -> the missions / tests (ordered block-refs + inline steps)
   |
Run           -> session_setup (login ONCE) + ordered list of tests to execute
```

**Login runs once** in `session_setup`, not per test. Each test assumes
"logged in, at Home" and starts with a cheap `go_home` to reset position. The
persistent browser profile means even `session_setup` usually skips real sign-in.

---

## Schema 1 — Step (one atomic action)

```json
{
  "id": "step_3",
  "action": "click",
  "intent": "Open the Manage Invoices task",
  "target": {
    "semantic_name": "Manage Invoices",
    "locators": [
      { "rank": 1, "strategy": "role",  "role": "link", "name": "Manage Invoices" },
      { "rank": 2, "strategy": "label", "value": "Manage Invoices" },
      { "rank": 3, "strategy": "text",  "value": "Manage Invoices" },
      { "rank": 4, "strategy": "css",   "value": "a[data-afr-fceid='...']" },
      { "rank": 5, "strategy": "xpath", "value": "//a[normalize-space()='Manage Invoices']" }
    ]
  },
  "value": null,
  "wait_condition": "redwood_settled",
  "risk_level": "safe"
}
```

| Field | Purpose |
|---|---|
| `id` | Stable handle so logs/healer can say "step_3 broke". |
| `action` | One generic verb: click, type, press, navigate, scroll, read, done. |
| `intent` | Plain-English goal. The healer reads this when all locators fail. |
| `target.semantic_name` | Human label; logging + quick fallback hint. |
| `target.locators` | **Ordered, ranked** locator list. Agent fills it automatically; healer appends/re-ranks over time. |
| `value` | `null` for click; literal or `${variable}` for type. |
| `wait_condition` | What "settled" means before this step (redwood_settled, element_visible, element_clickable, none). |
| `risk_level` | safe / write / destructive. Replay engine refuses above `safe` unless config allows. |

A `type` step uses a variable in `value`:

```json
{
  "action": "type",
  "intent": "Enter the user ID",
  "target": { "semantic_name": "User ID",
    "locators": [ { "rank": 1, "strategy": "role", "role": "textbox", "name": "User ID" } ] },
  "value": "${username}",
  "wait_condition": "element_visible",
  "risk_level": "safe"
}
```

---

## Schema 2 — Block (reusable, named, parameterized)

A block is a named list of steps that declares its own params. Three login variants
already exist as page objects (standard / microsoft_sso / idcs) — these become blocks.

```json
{
  "block_id": "login_password",
  "name": "Login (password, no SSO)",
  "intent": "Sign in using username and password",
  "params": ["username", "password"],
  "steps": [ "...ordered Step objects..." ]
}
```

Login stays **deterministic** (pre-authored blocks), not AI-driven, because:
secrets are involved, SSO/MFA redirects are fragile, and it's identical every run.
The AI healer is the fallback only when a login block breaks.

---

## Schema 3 — InstructionSet (a test / mission)

```json
{
  "name": "AP - Create Invoice",
  "goal": "Log in and create an invoice for the selected supplier",
  "sequence": [
    { "use_block": "go_home" },
    { "step": { "action": "click", "intent": "Open Navigator",
        "target": { "semantic_name": "Navigator",
          "locators": [ { "rank": 1, "strategy": "role", "role": "button", "name": "Navigator" } ] },
        "risk_level": "safe" } },
    { "step": { "action": "click", "intent": "Open Manage Invoices",
        "target": { "semantic_name": "Manage Invoices",
          "locators": [ { "rank": 1, "strategy": "role", "role": "link", "name": "Manage Invoices" } ] },
        "risk_level": "safe" } }
  ]
}
```

A `sequence` mixes `use_block` references and inline `step` objects.

---

## Schema 4 — Run (what to execute this session)

```json
{
  "run_name": "RCSD TEST nightly regression",
  "client": "RCSD/TEST",
  "session_setup": [
    { "use_block": "login" },
    { "use_block": "go_home" }
  ],
  "tests": [ "ap_create_invoice", "p2t_notifications", "hcm_user_search" ]
}
```

Login + go_home run ONCE here. Then each test runs against the live, logged-in browser.

---

## Schema 5 — ClientConfig (everything that changes per client)

Format: **YAML** (comments, readable, easy to copy per client). One file per
client/environment.

```yaml
client_id: "RCSD"
environment: "TEST"
base_url: "https://fa-euum-test-saasfaprod1.fa.ocs.oraclecloud.com"
login_type: "standard"          # standard | microsoft_sso | idcs

credentials:
  username_env: "RCSD_TEST_USERNAME"   # NAME of env var, not the value
  password_env: "RCSD_TEST_PASSWORD"   # actual secret lives in .env

login_settings:
  email_domain: "@pensionsbc.ca"       # SSO domain (was hardcoded in microsoft page object)

modules:                                # which modules this client tests
  scm: { enabled: true }
  finance: { enabled: true }
  procurement: { enabled: true }

variables:                              # the "any client, any instance" core
  business_unit: "RCSD BU"
  procurement_user: "j.smith"
  supplier: "Acme Office Supplies"
  invoice_amount: "100.00"

browser:
  headless: false
  slow_mo: 1000
  timeout: 60000
  viewport_width: 1920
  viewport_height: 1080
  profile_dir: ".pw-profile-rcsd-test"  # per-client persistent login

guardrails:
  dry_run: true            # fill but never Save/Submit
  allow_writes: false
  allow_destructive: false

ai_healer:
  enabled: true
  model: "gemma4:e4b"
```

### Key change from the current YAML files
- **Credentials become env-var NAMES, not values.** Real client files currently
  hold live passwords (incl. one with a unicode-escaped special char). Move secrets
  to `.env`; the config only names which var to read. This also fixes the
  special-character escaping problem.
- **`login_settings.email_domain`** pulled out of `login_page_microsoft.py` (was
  hardcoded `@pensionsbc`) — a per-client value that belongs in config.
- **`variables`** block added — the named data values steps reference as `${...}`.
  Same `${var}` substitution Testmodus already uses, so the systems stay compatible.
- **`guardrails`** = `DRY_RUN` promoted to config and split into degrees.

---

## The one rule to remember

> If a value differs between two clients or two environments → ClientConfig variable.
> If it's the same everywhere → Step structure.

---

## Next: Phase 1 — Perception Layer
Turn the healer's `_get_page_summary` into a standalone numbered-element reader
(`perceive(page)`) with: full locator-signature capture per element, an `index` +
`data-ai-index` stamp for lossless index->handle mapping, and a Redwood "settle gate"
(glass-pane/spinner gone, networkidle) run BEFORE every perceive.

Open question to decide at the start of Phase 1: capture every interactive element,
or only those visible in the viewport?