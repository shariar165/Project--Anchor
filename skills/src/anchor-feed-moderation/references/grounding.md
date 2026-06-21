VERIFICATION FEED MODERATION — verdicts: block | manual_review | pass.
Check order (first hit wins): safety block → spam/quality → category fit.

IMMEDIATE BLOCK (content-policy violation) if the text matches any:
- self-harm instruction/encouragement ("kill yourself", "kys", suicide method, "how to die")
- child sexual abuse material ("child porn", "cp link", "csam")
- prompt-injection ("ignore previous instructions", "disregard all prior")
- hate slurs (racial/ethnic/sexual slurs)

MANUAL_REVIEW (hold for a human) if:
- body has fewer than ~10 words (too short)
- more than 5 URLs (link spam)
- all-caps shouting (>5 words, entirely uppercase)
- category mismatch: none of the category's keyword hints appear in the text

CATEGORIES and example hints (at least one hint should appear):
- incident: accident, fire, collapse, explosion, robbery, crash, flood, injured, ambulance,
  police, হামলা, আগুন, দুর্ঘটনা
- missing_person: missing, lost, disappeared, last seen, kidnap, abduct, নিখোঁজ, হারিয়ে
- road: road, traffic, highway, bridge, jam, block, pothole, signal, রাস্তা, যানজট, সড়ক
- safety: danger, hazard, unsafe, warning, suspicious, threat, gas, leak, alert, সতর্ক, বিপদ
- civic_event: event, drive, campaign, announcement, notice, program, community, কর্মসূচি, অনুষ্ঠান

HUMAN REVIEW: reject doxxing, targeted harassment, defamation, incitement, and third-party
PII (phone/NID/home address). Favour fast pass-through for genuine, specific safety reports;
favour holding anything targeting a private individual. Trust never overrides a safety block.

(Canonical source for services/api/app/services/feed_prescreen.py — keep both in sync.)
