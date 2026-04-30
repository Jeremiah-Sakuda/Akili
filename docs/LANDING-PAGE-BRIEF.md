# Akili — Landing Page Brief for Web Designers

**Purpose:** Brief for designing and building a **marketing/landing page** for Akili to build buzz. The landing page will live in a **separate repo** from the main Akili product.  
**Audience:** Web designers, front-end developers, marketing site implementers.  
**Last updated:** February 2025.

---

## 1. What is Akili?

**One-liner:**  
Akili is the **reasoning control plane for mission-critical engineering**—a deterministic verification layer for technical documentation.

**Short description:**  
While LLMs are great at fluent reasoning, they fail where “mostly right” is unacceptable. Akili constrains AI (Gemini) within a strict structural framework: it turns dense PDFs, pinout tables, and schematics into **auditable, coordinate-grounded truth**. When you ask a question, you get either a **proven answer with exact locations** on the document—or a clear **refusal**. No citations; only proof.

**Tagline options (pick or adapt):**
- **“No citations. Only proof.”**
- **“The reasoning control plane for mission-critical engineering.”**
- **“Where AI shows its work.”**

---

## 2. Target audience

- **Primary:** Engineering leads, technical PMs, and teams in **mission-critical** domains (aerospace, medical devices, automotive, industrial control, defense) who need to trust answers from documentation.
- **Secondary:** Developers and researchers interested in **verifiable AI**, **deterministic QA**, and **document-grounded reasoning**.

Use a tone that is **confident, precise, and engineering-grade**—not playful or consumer-chat. Avoid hype; emphasize rigor and proof.

---

## 3. Value proposition and differentiators

| What Akili does | Why it matters |
|-----------------|----------------|
| **Coordinate-level grounding** | Every answer is tied to precise `(x, y)` locations on the source document—not “page 3” or a generic citation. |
| **Deterministic refusal** | If an answer can’t be mathematically derived from the ingested facts, Akili **refuses** instead of guessing. |
| **Structural canonicalization** | Raw document content is turned into typed objects (units, bijections, grids); ambiguous or low-confidence extractions are rejected at ingestion. |
| **Show the work** | The system doesn’t just return an answer—it **forces the model to show its work** against a verifiable map of the truth. |

**Key message:**  
Akili doesn’t “ask the AI for an answer.” It **forces the AI to prove the answer** against a canonical, coordinate-grounded store—or refuse.

---

## 4. How it works (simplified for landing page)

A simple three-step story works well for the page:

1. **Ingest** — Upload technical PDFs (datasheets, pinouts, schematics). Akili extracts typed facts and their **exact coordinates** on each page.
2. **Store** — Only validated, coordinate-grounded facts go into the “canonical truth store.” No free-text beliefs—only structural facts (units, bijections, grids).
3. **Query & verify** — Ask a question. You get either an **answer + proof** (list of locations that support it) or **REFUSED** (with a short reason). No hedging.

Optional: Include a simple diagram (e.g. PDF → Extract → Store → Query → Answer + proof or REFUSE). The main Akili repo has an ASCII architecture diagram in `README.md` that can inspire a visual.

---

## 5. Suggested landing page sections

Use these as a checklist; the designer can merge or reorder as needed.

| Section | Purpose | Notes |
|--------|---------|--------|
| **Hero** | Headline + subhead + primary CTA | Lead with one tagline; CTA e.g. “Request access” / “Join waitlist” / “Learn more.” |
| **Problem** | Why “mostly right” isn’t enough | Mission-critical engineering; cost of wrong answers; need for proof, not citations. |
| **Solution** | What Akili does in plain language | Coordinate-grounded answers; deterministic refuse; verification workspace, not chat. |
| **How it works** | 3 steps: Ingest → Store → Query & verify | Keep it simple; optional diagram. |
| **Differentiators** | Proof over citations, refusal over guessing | Short bullets or icons; use the table in §3. |
| **Use cases** | Who it’s for | Datasheets, pinout tables, schematics; engineering teams that need to trust document Q&A. |
| **Technical credibility** | Optional | One line: “Built with Gemini, FastAPI, and a typed canonical store.” No need to detail stack unless the audience is dev-heavy. |
| **CTA / Footer** | Waitlist, contact, or “Learn more” | Clear next step; link to main app when it’s public, or to a contact/waitlist form. |

---

## 6. Messaging and copy guidelines

- **Do:** Confident, precise, engineering-grade. “Proof,” “coordinates,” “deterministic,” “canonical,” “verification.”
- **Avoid:** Vague AI hype (“powered by AI”), playful tone, or implying that Akili “knows everything.” It only answers what can be **proven** from the ingested docs.
- **Refusal:** Frame as a **feature** (we refuse when we can’t prove), not a limitation.

**Sample headlines (mix and match):**
- “Where AI shows its work.”
- “No citations. Only proof.”
- “The reasoning control plane for mission-critical engineering.”
- “Technical documentation. Verified answers. Coordinate-level proof.”

**Sample body phrases:**
- “Every answer is tied to exact locations on your documents.”
- “If we can’t prove it, we refuse—no guessing.”
- “Turn datasheets, pinouts, and schematics into a verifiable truth store.”

---

## 7. Visual direction

Align with the **engineering / mission-critical** product:

- **Tone:** Confident, legible, minimal decoration. No playful or consumer-chat aesthetics.
- **Palette (suggested):**
  - **Verified / success:** Restrained green (e.g. `#0D7B4C`).
  - **Refuse / caution:** Amber (e.g. `#B45300`), not error red.
  - **Accent:** One clear primary (e.g. blue/cyan) for CTAs and links.
  - **Dark mode (optional):** Charcoal/slate background; same semantic colors.
- **Typography:** Clear hierarchy; consider technical sans or a readable sans for headings. Monospace optional for “proof” or coordinate-style accents.
- **Imagery:** Prefer diagrams, abstract “document → proof” visuals, or product UI screenshots (verification workspace, proof overlay). Avoid generic stock “team in office” unless it fits the audience.

The main app’s UI spec lives in `docs/UI-SPEC.md` (in the Akili repo); the landing page can echo the same palette and tone for brand consistency.

---

## 8. What the designer is building

- **Deliverable:** A **marketing/landing page** (separate repo from the main Akili app).
- **Scope:** Informational and conversion-focused (waitlist, “Request access,” or “Learn more”). No login, no document upload, no query UI—those stay in the main Akili app.
- **Tech:** Designer’s choice (static site, Next.js, etc.). No backend required for the landing page itself; forms can use a third-party service (e.g. Formspree, Netlify Forms) or link to an external waitlist/contact URL.

---

## 9. Assets and references

- **Repo:** Main Akili project is in a separate repo; share repo link or README if the designer needs technical depth.
- **Docs in main repo (for context):**
  - `README.md` — Product overview, architecture diagram, tech stack.
  - `docs/UX-DESIGN-BRIEF.md` — UX principles and flows for the **app** (not the landing page).
  - `docs/UI-SPEC.md` — Colors, typography, components for the **app**; reuse palette/tone for the landing page if desired.
  - `docs/ARCHITECTURE.md` — Deeper technical architecture; optional for “Technical credibility” section.
- **Logo / wordmark:** If Akili has a logo or wordmark, provide it. Otherwise “Akili” in the chosen typeface is sufficient.
- **Screenshots:** If the app is demo-able, 1–2 screenshots (e.g. verification workspace with proof overlay, or REFUSED state) can strengthen the “How it works” or “Product” section.

---

## 10. Out of scope for this brief

- Design or implementation of the **main Akili application** (that’s in the main repo and covered by `UX-DESIGN-BRIEF.md` and `UI-SPEC.md`).
- Backend, API, or auth for the landing page (only if the designer adds a simple form backend or waitlist integration).
- Final copy approval (use this doc as a starting point; stakeholder to approve headlines and CTAs).

---

## Quick reference: Akili in 3 sentences

1. **Akili** is a deterministic verification layer for technical documentation (PDFs, datasheets, pinouts, schematics).  
2. It turns documents into a **canonical, coordinate-grounded truth store** and only answers questions when the answer can be **proven** from that store—otherwise it **refuses**.  
3. **Tagline:** “No citations. Only proof.”

---

*Use this brief with the main repo’s README and UI-SPEC for a consistent, buzz-worthy landing page that clearly communicates Akili’s value to engineering and technical audiences.*
