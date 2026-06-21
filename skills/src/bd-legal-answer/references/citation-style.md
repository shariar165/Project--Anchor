# Citation style & the CITATIONS_JSON contract

Every legal claim in the answer must be traceable to a retrieved source. Two layers:

## 1. Inline markers
After each claim, put the source chunk ID in square brackets:

> Demanding dowry is a criminal offence [chunk-dowry-3], punishable by imprisonment and fine
> [chunk-dowry-3]. To report it, file a complaint at the nearest police station [wf-gd-filing].

- Use the exact `chunk_id` from the context header (e.g. `[penal-1860-420]`, `[wf-fir]`).
- A workflow/procedure chunk is cited at the PRACTICAL STEP.
- Do not invent IDs. If no chunk supports a sentence, the sentence does not belong in the answer.

## 2. Structured block (machine-readable)
After the prose, on its own line, emit:

```
CITATIONS_JSON: [{"id": "chunk_id", "title": "Act Name § Section", "source": "corpus"}]
```

- `id` — the chunk ID used inline.
- `title` — human-readable: `"Dowry Prohibition Act 1980 § 4"`.
- `source` — `"corpus"` for the curated legal corpus, `"web"` for web-search fallback.
- The pipeline strips this block from the user-facing text and renders a **Sources** list;
  it also falls back to scraping inline `[id]` markers, so always do both.

## Authority ranking in titles
When the same point has multiple sources, lead with the highest authority:
Constitution → Act/Ordinance → Rules → case law → web. Mark web sources clearly as lower
authority — the user must know to verify them before acting.

## Amendment status
If a chunk notes a provision is amended or repealed, say so. Never present repealed law as
current (e.g. cite the Cyber Security Act 2023, not the repealed Digital Security Act 2018,
unless the question is explicitly historical).
