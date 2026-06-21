# Feed categories & keyword hints

The Verification Feed sorts posts into five categories. The pre-screen requires at least one
of a category's keyword hints to appear in the text; otherwise the post is held for
`manual_review` as a possible category mismatch (this is lenient by design — a single hint
clears it). Keep this list aligned with `_CATEGORY_HINTS` in `feed_prescreen.py`.

| Category | What it covers | Keyword hints (EN + BN) |
|---|---|---|
| **incident** | A real-world event causing harm or emergency right now | accident, fire, collapse, explosion, robbery, crash, collision, flood, injured, victim, emergency, ambulance, police, হামলা, আগুন, দুর্ঘটনা |
| **missing_person** | A person who is lost, missing, or abducted | missing, lost, disappeared, last seen, search, kidnap, abduct, নিখোঁজ, হারিয়ে, খোঁজ |
| **road** | Road/traffic conditions and obstructions | road, traffic, highway, street, bridge, jam, block, lane, pothole, signal, রাস্তা, যানজট, সড়ক |
| **safety** | A hazard or warning people should be aware of | danger, hazard, unsafe, warning, suspicious, threat, gas, leak, alert, beware, সতর্ক, বিপদ |
| **civic_event** | Community drives, campaigns, public announcements | event, drive, campaign, announcement, notice, program, community, public, initiative, কর্মসূচি, অনুষ্ঠান |

## Choosing a category
- A car crash blocking a road is an **incident** if people are hurt, a **road** report if it
  is purely a traffic obstruction. Prefer the higher-urgency category when in doubt.
- A "missing child" is **missing_person**, not incident.
- A gas leak with no injury yet is **safety**; once it causes a fire/explosion it is **incident**.

## On mismatch
A category mismatch is a soft signal, not a violation. The right action is usually to ask the
poster to recategorise (or to recategorise it during review), not to reject the post.
