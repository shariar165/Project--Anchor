---
name: diu-notice-generator
description: >
  Use this skill whenever a university administrator needs to draft or publish an official
  notice for Daffodil International University (DIU). Triggers: "write a notice", "draft a
  notice", "publish a notice", "campus announcement", "exam notice", "library notice",
  "holiday/closure notice", "fee/payment notice", "event/seminar notice", "hostel notice",
  "registrar notice", "notice to students", or ANY administrator broadcasting information to
  students, teachers, or staff. Produces formal, institutional notices in English and Bangla
  with the correct Registrar's Office sign-off. Also used by the Anchor admin Notice Generator
  backend (services/api notice_ai_svc.py) to ground its Ollama prompt — keep the two in sync.
---

# DIU Notice Generator

A skill for drafting professional, institutional notices issued by **Daffodil International
University (DIU)** — a private university in Dhaka, Bangladesh. Notices are short broadcasts
to students, teachers, or staff, distributed via the Anchor student app (push / SMS / email).

---

## Step 1 — Identify the Notice Category

Map the request to a category and read the matching reference before drafting.

| Category | Reference File |
|---|---|
| Examination (routine, hall, results, permission) | `references/exam-notice.md` |
| Library (hours, access, dues) | `references/library-notice.md` |
| Holiday / Closure | `references/holiday-notice.md` |
| Fee / Payment | `references/fee-notice.md` |
| Event / Seminar / Convocation | `references/event-notice.md` |
| Hostel / Residential | `references/hostel-notice.md` |
| General / Administrative | use the standard structure below |

For bilingual rules and Bangla conventions, read `references/bilingual-style.md`.

---

## Step 2 — Gather the Facts

Extract from the administrator's prompt; ask only for what is essential and missing:

- **What** is being announced (the core message)
- **When** — dates, times, deadlines (use explicit dates, e.g. "8–15 June 2026")
- **Where** — building, hall, portal, office (if relevant)
- **Action required** — what the reader must do, if anything
- **Audience** — university-wide, a department, a batch, a section, a hall
- **Language** — English or Bangla

---

## Step 3 — Write the Notice

### Standard structure

```
[Salutation]

[Paragraph 1 — the announcement: what + when + where, stated up front.]

[Paragraph 2 — any action required, conditions, or details. Optional.]

[Closing courtesy line. Optional.]

Registrar's Office
Daffodil International University
```

- **Salutation**: "Dear Students," (or "Dear All," for mixed audiences).
- **Body**: 1–3 short paragraphs. Lead with the key facts. Be specific about dates/times.
- **Sign-off**: always close with the Registrar's Office / Daffodil International University.

### Writing standards

- **Tone**: formal, institutional, clear, courteous. Never casual or promotional.
- **No** emojis, slang, marketing language, or exclamation spam.
- **Length**: concise — typically 60–150 words.
- **Subject line**: short and informative, e.g. "Library extended hours · Finals week Spring 2026".
- **Tense**: present/future for upcoming events; be precise, not dramatic.

---

## Step 4 — Bangla Notices

When the language is Bangla, write the **entire** notice in natural Bangla (not transliteration):

- Salutation: "প্রিয় শিক্ষার্থীবৃন্দ,"
- Sign-off:
  ```
  রেজিস্ট্রার কার্যালয়
  ড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি
  ```
- Use Bangla numerals where natural, but keep dates unambiguous.

See `references/bilingual-style.md` for vocabulary and tone guidance.

---

## Step 5 — Output

Return the notice as a **subject line** and a **body**. The body must include the salutation
and the Registrar sign-off. When integrated programmatically, return JSON:

```json
{"subject": "<short subject>", "body": "<full notice text>"}
```

After presenting, offer to: translate to the other language, adjust the tone
(formal ↔ warm), shorten for SMS, or scope to a specific audience.
