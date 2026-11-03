"""python -m app.acquisition.cli --config ... --source ... --output ..."""
import argparse
import json
from pathlib import Path

from ..db import Session
from .adapters import FileDatasetAdapter, MetaAuthorizedAdapter, ProviderDatasetAdapter, TikTokCreativeCenterAdapter, registry_gate
from .benchmark import benchmark, export_import, write_artifact
from .contracts import Access, Query


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--keyword", default="solar garden lights")
    parser.add_argument("--country", default="US")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--export", help="Optional explicit v0.2 import-format file; never automatically ingests")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())[args.source]
    access = Access.model_validate(config["access"])
    query = Query(keyword=args.keyword, country=args.country, limit=args.limit)
    kind = config["adapter"]
    if kind == "file":
        adapter = FileDatasetAdapter(access, config["filename"], config.get("mapping"), Query.model_validate(config["dataset_query"]))
    elif kind == "meta":
        adapter = MetaAuthorizedAdapter(access, config.get("verified_api_version"))
    elif kind == "provider_dataset":
        adapter = ProviderDatasetAdapter(access, config["dataset_id"], Query.model_validate(config["dataset_query"]), config["mapping"])
    elif kind == "tiktok_top":
        adapter = TikTokCreativeCenterAdapter(access)
    else:
        parser.error("Unknown adapter")
    with Session() as session:
        result = benchmark(adapter, query, args.output, gate=lambda a, q: registry_gate(session, a, q), resume=args.resume)
    if args.export and result["records"]:
        write_artifact(args.export, export_import(result))
    print(json.dumps(result["summary"], indent=2))
    if result["error_type"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
