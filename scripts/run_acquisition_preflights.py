"""35 local approval checks, no transport. Never performs a live pilot."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
from app.acquisition.benchmark import benchmark, write_artifact
from app.acquisition.contracts import Access, AcquisitionError, Query

ROOT = Path(__file__).resolve().parents[1]

KEYWORDS = ["solar garden lights", "pet grooming", "portable blender", "posture corrector", "car accessories"]


class NoNetwork:
    def __init__(self, access):
        self.access = access

    def collect_page(self, query, checkpoint):
        raise AcquisitionError("preflight_only_no_transport")


def main():
    import tempfile

    config = json.loads((ROOT / "docs/acquisition/sources.example.json").read_text())
    rows = []
    with tempfile.TemporaryDirectory(prefix="dropspy-preflight-") as temp:
        for key in ["meta-public", "meta-official", "tiktok-top", "locaihost", "steadyfetch", "silentflow", "data_xplorer"]:
            access = Access.model_validate(config.get(key, config["provider-dataset"])["access"])
            if key not in config:
                access = access.model_copy(update={"source_name": key + " candidate; schema/rights unverified"})
            for index, keyword in enumerate(KEYWORDS):
                result = benchmark(NoNetwork(access), Query(keyword=keyword), Path(temp) / f"{key}-{index}.json")
                rows.append(result["summary"] | {"candidate": key, "data_request_attempted": False, "kind": "approval preflight, not live pilot"})
    write_artifact(ROOT / "docs/acquisition/evidence/disabled-preflights.json", {"note": "35 local gate evaluations, zero ad data requests. Null counts are unmeasured, not zero-result searches.", "results": rows})
    print(f"{len(rows)} local preflights; no network transport configured")


if __name__ == "__main__":
    main()
