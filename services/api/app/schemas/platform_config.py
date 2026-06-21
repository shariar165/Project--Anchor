"""Platform configuration defaults + request schema.

DEFAULT_PLATFORM_CONFIG mirrors the values the admin UI previously hardcoded
(apps/admin/src/settings.jsx). Stored PlatformConfig rows are deep-merged over
these defaults so GET /v1/super-admin/config always returns a complete object.
"""
from typing import Any
from pydantic import BaseModel, Field


DISCLAIMER_EN = (
    "Anchor AI provides information for educational purposes only and does not "
    "constitute legal advice. For binding guidance, consult a licensed legal "
    "practitioner. The platform routes complaints to your institution; it does "
    "not adjudicate disputes."
)
DISCLAIMER_BN = (
    "Anchor AI শুধুমাত্র তথ্যগত সহায়তা প্রদান করে এবং এটি কোনো আইনি পরামর্শ নয়। "
    "বাধ্যতামূলক নির্দেশনার জন্য, একজন লাইসেন্সধারী আইনজীবীর পরামর্শ নিন। এই "
    "প্ল্যাটফর্ম অভিযোগ আপনার প্রতিষ্ঠানে রাউট করে — এটি বিরোধ নিষ্পত্তি করে না।"
)


DEFAULT_PLATFORM_CONFIG: dict[str, dict[str, Any]] = {
    "escalation": {
        "level1_to_level2_hours": 72,
        "level2_to_level3_days": 7,
        "alert_auto_escalation_minutes": 30,
        "max_tenant_timer_days": 14,
    },
    "rate_limits": {
        "complaint_filing_per_24h": 5,
        "active_alerts_per_24h": 3,
        "news_publishing_per_hour": 2,
        "ai_queries_per_hour": 60,
    },
    "trust_thresholds": {
        "bronze_verified_posts": 5,
        "silver_trusted_posts": 10,
        "gold_sourceful_posts": 15,
        "demotion_false_posts": 2,
    },
    "bans": {
        "alert_false_alarm_days": 30,
        "news_false_publication_days": 30,
        "complaint_spam_days": 14,
        "permanent_ban_requires": "2 super admin approvals",
    },
    "ai_thresholds": {
        "auto_publish_news": 0.90,
        "auto_reject_news": 0.40,
        "auto_flag_false_alarm": 0.85,
        "pattern_detection_signal": "Surface to Dean when ≥ 3 reports",
        "self_verification_min": 0.95,
    },
    "disclaimer": {
        "en": DISCLAIMER_EN,
        "bn": DISCLAIMER_BN,
    },
    "retention": {
        "resolved_case": "2 academic years",
        "evidence": "5 years",
        "delete_inactive_accounts": "2 years",
    },
    "pdpo": {
        "right_to_access": True,
        "right_to_rectification": True,
        "right_to_erasure": True,
        "data_localization": True,
        "cross_border_transfer_review": True,
        "breach_notification_window": "72 hours (Ordinance default)",
    },
}


def merged_config(stored: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Deep-merge stored section values over the defaults (one level deep)."""
    out: dict[str, dict[str, Any]] = {}
    for section, defaults in DEFAULT_PLATFORM_CONFIG.items():
        merged = dict(defaults)
        if isinstance(stored.get(section), dict):
            merged.update(stored[section])
        out[section] = merged
    # Preserve any extra stored sections not present in defaults.
    for section, val in stored.items():
        if section not in out:
            out[section] = val
    return out


class ConfigUpdate(BaseModel):
    """Partial update: only the provided sections are upserted."""
    sections: dict[str, dict[str, Any]] = Field(default_factory=dict)
