"""Local-only import command: python -m app.import_ads /path/authorized.json."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from .collectors.base import AdRecord
from .db import Base, Session, engine
from .ingest import ingest
from .models import Ad, AdProvenance


class AuthorizedDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,49}$")
    kind: str = Field(pattern="^authorized_file$")
    corpus: str = Field(pattern="^paid_ad$")
    rights_reference: str = Field(min_length=10, max_length=500)
    permission_attested: bool
    records: list[AdRecord] = Field(min_length=1, max_length=1000)

    @field_validator("rights_reference")
    @classmethod
    def nonblank_reference(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("A meaningful rights reference is required")
        return value.strip()

    @model_validator(mode="after")
    def validate_rights_and_records(self):
        if not self.permission_attested:
            raise ValueError("Operator must attest permission to use this paid-ad dataset")
        now = datetime.now(timezone.utc) + timedelta(minutes=5)
        for record in self.records:
            if record.is_demo:
                raise ValueError("Demo data cannot be relabeled as an authorized real import")
            if not 1 <= len(record.source_id) <= 100 or ":" in record.source_id:
                raise ValueError("External ad IDs must be 1–100 characters without ':'")
            for stamp in (record.first_seen, record.last_seen):
                value = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp
                if value > now:
                    raise ValueError("Observation timestamps cannot be in the future")
        return self


def import_dataset(session, dataset):
    records = [row.model_copy(update={"source_id": f"{dataset.source_id}:{row.source_id}"}) for row in dataset.records]
    ingest(session, records, commit=False)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for original, record in zip(dataset.records, records):
        ad = session.scalar(select(Ad).where(Ad.source_id == record.source_id, Ad.platform == record.platform, Ad.is_demo.is_(False)))
        provenance = session.get(AdProvenance, ad.id)
        if provenance is None:
            session.add(AdProvenance(ad_id=ad.id, source_id=dataset.source_id, external_id=original.source_id, rights_reference=dataset.rights_reference, imported_at=now))
        else:
            if provenance.rights_reference != dataset.rights_reference:
                raise ValueError("Existing source rights reference differs; review before reusing this source ID")
            provenance.imported_at = now
    session.flush()
    return {"records_processed": len(records), "source_id": dataset.source_id}


def main():
    parser = argparse.ArgumentParser(description="Import a paid-ad dataset you are authorized to use (local CLI only)")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    # Read with a byte cap even if the file changes after stat; no remote URL fetching.
    with args.path.open("rb") as handle:
        payload = handle.read(1024 * 1024 + 1)
    if len(payload) > 1024 * 1024:
        parser.error("Dataset must be at most 1 MiB")
    try:
        dataset = AuthorizedDataset.model_validate_json(payload)
    except ValueError:
        parser.error("Invalid dataset. Check required fields, rights attestation, real-data flag, IDs and observation timestamps.")
    Base.metadata.create_all(engine)
    try:
        with Session.begin() as session:
            result = import_dataset(session, dataset)
    except ValueError:
        parser.error("Source rights reference conflicts with an existing import; transaction rolled back.")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
