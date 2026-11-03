from urllib.parse import urlparse


def score(ad, variants: int, recurrence: int):
    days = max(0, (ad.last_seen - ad.first_seen).days)
    components = [
        ("ad_longevity", min(days / 60, 1) * 40, 40, f"{days} days between first/last observation; not proof of continuous delivery", "medium"),
        ("creative_variants", min(variants / 5, 1) * 25, 25, f"{variants} distinct creative text fingerprints on this ad", "medium"),
        ("advertiser_recurrence", min(recurrence / 5, 1) * 20, 20, f"{recurrence} ads from this advertiser in this dataset", "low"),
        ("landing_quality", 15 if urlparse(ad.landing_url).scheme == "https" else 0, 15, "HTTPS URL syntax only; landing page not fetched or audited", "low"),
    ]
    return {
        "version": "0.1",
        "value": round(sum(x[1] for x in components)),
        "confidence": "demo" if ad.is_demo else "low",
        "components": [
            {
                "metric": key,
                "value": round(value, 1),
                "maximum": maximum,
                "source": "synthetic demo fixture" if ad.is_demo else "stored observations",
                "evidence": evidence,
                "confidence": "demo" if ad.is_demo else confidence,
            }
            for key, value, maximum, evidence, confidence in components
        ],
        "disclaimer": "Research heuristic, not sales, ROAS or revenue prediction.",
    }
