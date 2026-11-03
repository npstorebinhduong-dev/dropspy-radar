import json
from pathlib import Path

from .base import AdRecord

FIXTURE = Path(__file__).with_name("fixtures") / "demo.json"


class DemoCollector:
    def collect(self) -> list[AdRecord]:
        records = [AdRecord.model_validate(row) for row in json.loads(FIXTURE.read_text())]
        if any(not row.is_demo for row in records):
            raise ValueError("demo fixtures must be labeled is_demo=true")
        return records
