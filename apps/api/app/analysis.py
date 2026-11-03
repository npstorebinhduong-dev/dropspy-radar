"""Deterministic, evidence-linked creative analysis. No model/network calls."""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

VERSION = "creative-rules-0.2"
RULES = {
    "offer": {"discount": r"\b\d{1,2}%\s*off\b", "free_shipping": r"\bfree (?:shipping|delivery)\b", "guarantee": r"\b(?:money.back|guarantee)\b"},
    "angle": {
        "urgency": r"\b(?:limited time|today only|while supplies last)\b",
        "social_proof": r"\b(?:trusted by|rated|reviews|customers love)\b",
        "convenience": r"\b(?:portable|easy|in seconds|cordless|foldable)\b",
        "problem_solution": r"\b(?:tired of|struggling with|say goodbye to)\b",
    },
    "cta": {"shop_now": r"\bshop now\b", "learn_more": r"\blearn more\b", "get_offer": r"\b(?:get yours|claim (?:your|the) offer)\b"},
}


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def status_evidence(ad, now=None):
    now = now or utc_now()
    age = max(0, int((now - ad.last_seen).total_seconds() // 3600))
    return {
        "reported_status": ad.status,
        "observed_at": ad.last_seen,
        "age_hours": age,
        "freshness": "demo" if ad.is_demo else "recent" if age <= 72 else "stale",
        "currently_running_verified": False,
        "reason": "Synthetic demo status" if ad.is_demo else "Source-reported at last observation; current delivery has not been independently verified",
    }


def analyze(ad, creatives, observation_count, related_ad_count, provenance=None):
    signals = []
    for index, creative in enumerate(creatives):
        for category, rules in RULES.items():
            for label, pattern in rules.items():
                for match in re.finditer(pattern, creative["text"], re.IGNORECASE):
                    signals.append(
                        {
                            "category": category,
                            "label": label,
                            "excerpt": match.group(),
                            "creative_index": index,
                            "start": match.start(),
                            "end": match.end(),
                            "source": "stored creative text",
                            "confidence": "demo" if ad.is_demo else "low",
                        }
                    )
    warnings = [
        "Text rules can miss context; no transcript, visual or landing-page audit was performed.",
        "Observation span and creative counts are research signals, not evidence of sales or profitability.",
    ]
    evidence = status_evidence(ad)
    if evidence["freshness"] == "stale":
        warnings.append("Active status may be out of date. Check the source before treating this ad as currently running.")
    if observation_count < 2:
        warnings.append("Only one observation: creative testing frequency and continuous delivery cannot be established.")
    return {
        "version": VERSION,
        "ad_id": ad.id,
        "is_demo": ad.is_demo,
        "method": "deterministic English text rules",
        "status_evidence": evidence,
        "signals": signals,
        "observations": {"count": observation_count, "span_days": max(0, (ad.last_seen - ad.first_seen).days), "first_seen": ad.first_seen, "last_seen": ad.last_seen},
        "creative_variants": {"count": len(creatives), "definition": "Distinct stored text fingerprints on this ad; not visual variants or testing frequency"},
        "advertiser": {"name": ad.advertiser, "related_ads": related_ad_count, "identity_method": "exact advertiser name in current dataset; not verified company identity"},
        "landing": {"domain": ad.landing_domain, "https": urlparse(ad.landing_url).scheme == "https", "audited": False},
        "source": provenance or {"kind": "demo" if ad.is_demo else "legacy_unknown", "source_url": ad.source_url},
        "limitations": warnings,
        "business_outcomes": {"roas": None, "revenue": None, "sales": None},
    }
