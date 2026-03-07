"""
Provenance metadata utility for Intelli-Credit.
Attaches provenance JSON to every extracted datum and decision.
"""
import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class Provenance:
    """Provenance metadata for every extracted datum and decision."""
    source_file: str
    page: Optional[int] = None
    byte_offset: Optional[int] = None
    extraction_method: str = "unknown"
    confidence: Optional[float] = None
    agent_id: str = "system"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "Provenance":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ExtractedField:
    """A single extracted field with its value and provenance."""
    field_name: str
    field_value: str
    field_type: str = "string"  # string, number, date, gstin, pan
    provenance: Optional[Provenance] = None

    def to_dict(self) -> dict:
        d = {
            "field_name": self.field_name,
            "field_value": self.field_value,
            "field_type": self.field_type,
        }
        if self.provenance:
            d["provenance"] = self.provenance.to_dict()
        return d


@dataclass
class ExtractionResult:
    """Complete extraction result for a document."""
    document_id: str
    source_file: str
    extracted_fields: list[ExtractedField] = field(default_factory=list)
    raw_text: str = ""
    markdown: str = ""
    tables: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "source_file": self.source_file,
            "extracted_fields": [f.to_dict() for f in self.extracted_fields],
            "tables": self.tables,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def create_provenance(
    source_file: str,
    page: Optional[int] = None,
    extraction_method: str = "unknown",
    confidence: Optional[float] = None,
    agent_id: str = "system",
) -> Provenance:
    """Factory function to create provenance metadata."""
    return Provenance(
        source_file=source_file,
        page=page,
        extraction_method=extraction_method,
        confidence=confidence,
        agent_id=agent_id,
    )
