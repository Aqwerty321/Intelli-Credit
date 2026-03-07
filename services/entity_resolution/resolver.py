"""
Entity resolution service using Crocodile (or rapidfuzz fallback).
Resolves and deduplicates company names, director names, and GSTINs.
"""
import json
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ResolvedEntity:
    """A resolved entity with canonical name and aliases."""
    entity_id: str
    entity_type: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = "manual"


class EntityResolver:
    """Entity resolution engine with Crocodile primary and rapidfuzz fallback."""

    def __init__(self):
        self.entities: dict[str, ResolvedEntity] = {}
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """Detect available entity resolution backend."""
        try:
            import crocodile
            return "crocodile"
        except ImportError:
            pass
        try:
            from rapidfuzz import fuzz
            return "rapidfuzz"
        except ImportError:
            pass
        return "exact"

    def resolve(self, name: str, entity_type: str = "company") -> Optional[ResolvedEntity]:
        """Resolve an entity name to its canonical form."""
        normalized = self._normalize(name)

        # Check exact match first
        for eid, entity in self.entities.items():
            if self._normalize(entity.canonical_name) == normalized:
                return entity
            for alias in entity.aliases:
                if self._normalize(alias) == normalized:
                    return entity

        # Fuzzy match
        if self._backend == "rapidfuzz":
            return self._fuzzy_resolve(name, entity_type)
        elif self._backend == "crocodile":
            return self._crocodile_resolve(name, entity_type)

        return None

    def add_entity(self, entity: ResolvedEntity) -> None:
        """Register a known entity."""
        self.entities[entity.entity_id] = entity

    def resolve_or_create(self, name: str, entity_type: str = "company",
                          threshold: float = 0.85) -> ResolvedEntity:
        """Resolve to existing entity or create new one."""
        existing = self.resolve(name, entity_type)
        if existing and existing.confidence >= threshold:
            if name not in existing.aliases and name != existing.canonical_name:
                existing.aliases.append(name)
            return existing

        # Create new entity
        import hashlib
        entity_id = hashlib.sha256(f"{entity_type}:{name}".encode()).hexdigest()[:16]
        entity = ResolvedEntity(
            entity_id=entity_id,
            entity_type=entity_type,
            canonical_name=name,
            confidence=1.0,
            source=self._backend,
        )
        self.entities[entity_id] = entity
        return entity

    def _normalize(self, name: str) -> str:
        """Normalize entity name for comparison."""
        import re
        name = name.upper().strip()
        # Remove common suffixes
        for suffix in ["PVT. LTD.", "PVT LTD", "PRIVATE LIMITED", "LIMITED", "LTD.", "LTD",
                       "INC.", "INC", "CORP.", "CORP", "M/S", "M/S."]:
            name = name.replace(suffix, "")
        name = re.sub(r'\s+', ' ', name).strip()
        return name

    def _fuzzy_resolve(self, name: str, entity_type: str) -> Optional[ResolvedEntity]:
        """Resolve using rapidfuzz fuzzy matching."""
        from rapidfuzz import fuzz

        normalized = self._normalize(name)
        best_match = None
        best_score = 0

        for eid, entity in self.entities.items():
            if entity.entity_type != entity_type:
                continue

            score = fuzz.ratio(normalized, self._normalize(entity.canonical_name))
            if score > best_score:
                best_score = score
                best_match = entity

            for alias in entity.aliases:
                alias_score = fuzz.ratio(normalized, self._normalize(alias))
                if alias_score > best_score:
                    best_score = alias_score
                    best_match = entity

        if best_match and best_score >= 85:
            best_match.confidence = best_score / 100.0
            return best_match

        return None

    def _crocodile_resolve(self, name: str, entity_type: str) -> Optional[ResolvedEntity]:
        """Resolve using Crocodile entity linker."""
        # Crocodile integration - uses KG-based entity linking
        try:
            import crocodile
            # Crocodile API would be called here
            # For now, fall back to fuzzy matching
            return self._fuzzy_resolve(name, entity_type)
        except Exception:
            return self._fuzzy_resolve(name, entity_type)

    def to_dict(self) -> list[dict]:
        """Export all entities as a list of dicts."""
        return [
            {
                "entity_id": e.entity_id,
                "entity_type": e.entity_type,
                "canonical_name": e.canonical_name,
                "aliases": e.aliases,
                "confidence": e.confidence,
                "source": e.source,
            }
            for e in self.entities.values()
        ]
