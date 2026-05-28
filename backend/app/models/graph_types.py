"""Graph enums shared across models and memory layers."""

from enum import StrEnum


class RelationType(StrEnum):
    """Weighted semantic edge between two thoughts."""

    RELATED_TO = "related_to"
    CONTRADICTS = "contradicts"
    CAUSES = "causes"
    REINFORCES = "reinforces"
    DERIVED_FROM = "derived_from"


RELATION_PROPAGATION: dict[RelationType, float] = {
    RelationType.RELATED_TO: 1.0,
    RelationType.CONTRADICTS: -0.5,
    RelationType.CAUSES: 1.0,
    RelationType.REINFORCES: 1.2,
    RelationType.DERIVED_FROM: 0.9,
}
