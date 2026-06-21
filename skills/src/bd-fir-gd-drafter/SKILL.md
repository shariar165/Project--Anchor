---
name: bd-fir-gd-drafter
description: >
  Use this skill whenever a user in Bangladesh needs to draft a police or legal complaint
  document: an FIR (First Information Report / এজাহার), a General Diary entry (GD / জিডি),
  or a legal notice (লিগ্যাল নোটিশ). Triggers: "write/draft an FIR", "file a GD", "general
  diary", "police complaint", "legal notice", "report to police", "lost my phone/NID GD",
  "someone is threatening me", "এজাহার", "জিডি", "থানায় অভিযোগ", "লিগ্যাল নোটিশ", "নালিশ".
  Always trigger for casual phrasings like "I need to report this to the police" or "how do
  I complain about X". Produces neutral, factual, submission-ready drafts in English or
  Bangla. Grounds Anchor's national-mode complaint_draft intent (services/rag pipeline) via
  references/grounding.md — keep them in sync. For court documents the user already HAS,
  use bd-legal-doc-reader instead; for university applications use uni-admin-application.
---

# Bangladesh FIR / GD / Legal Notice Drafter

A skill for drafting the three documents ordinary people in Bangladesh most often need to
start a legal process: a **GD** (General Diary — for non-cognizable matters, lost items,
threats, preventive record), an **FIR** (the first report of a cognizable offence at a
police station), and a **legal notice** (a formal demand sent before civil action).

The user is usually distressed and not a lawyer. Your job is to turn their account into a
clear, factual, submission-ready document — never to dramatise, accuse beyond the facts,
or invent details.

---

## Step 1 — Identify the document

| User need | Document | Reference |
|---|---|---|
| Lost item, threat, preventive record, non-cognizable issue | **General Diary (GD)** | `references/gd.md` |
| A cognizable crime (theft, assault, dowry, cyber harassment, etc.) | **FIR / এজাহার** | `references/fir.md` |
| Formal demand before a civil suit (money owed, breach, defamation) | **Legal Notice** | `references/legal-notice.md` |

If unsure, ask ONE question: *"Do you want to (a) put something on record / report a lost
item — a GD, (b) report a crime to the police — an FIR, or (c) formally demand someone do
something before going to court — a legal notice?"*

Read the matching reference before drafting.

---

## Step 2 — Gather the facts (ask only for what is essential and missing)

- **Complainant**: full name, father's/mother's name, age, address, NID, phone.
- **Opposite party** (if known): name, address, relationship to complainant — or
  "unknown/unidentified" if not known. Never fabricate a name.
- **What happened**: a plain chronological account — who, what, when, where, how.
- **Date, time, and place** of the incident (be specific and unambiguous).
- **Witnesses** (if any) and **evidence** (documents, messages, photos, medical report).
- **Loss/harm**: injury, amount stolen, item lost (with identifiers), damage.
- **Police station / jurisdiction** (the thana where the incident happened, for GD/FIR).
- **Language**: English or Bangla.

If the user gives a brief account ("he threatened me yesterday"), build a clean factual
narrative from it — ask for elaboration only when a missing fact changes the document.

---

## Step 3 — Draft

Follow the structure in the matching reference. Apply these standards to all three:

- **Tone**: neutral, factual, respectful. State facts, not conclusions of law or insults.
- **Chronological**: narrate events in the order they happened, with dates/times.
- **No fabrication**: if a detail is unknown, write "[to be filled]" or "unknown" — never
  invent names, section numbers, amounts, or witnesses.
- **Sections**: you may *suggest* likely applicable sections (see the statute map in
  `bd-legal-answer`) but mark them as "likely applicable, to be confirmed" — the police or
  a lawyer set the final sections.
- **Length**: as short as completeness allows. One page where possible.

---

## Step 4 — Output & disclaimer

Present the draft with clear spacing and the signature/date block. Then always include:

> *This is a drafting aid, not legal advice. A police officer or lawyer may revise the
> wording and the applicable sections. For a cognizable offence or court matter, consult a
> verified lawyer before filing.* (Bangla: *এটি একটি খসড়া সহায়তা, আইনি পরামর্শ নয়। থানা বা
> আইনজীবী ধারা ও ভাষা পরিবর্তন করতে পারেন। গুরুতর অপরাধ বা আদালতের বিষয়ে আইনজীবীর পরামর্শ নিন।*)

Offer follow-up: translate to the other language, produce a `.docx`, tighten the tone, or
explain the user's rights (hand off to `bd-legal-answer`).
