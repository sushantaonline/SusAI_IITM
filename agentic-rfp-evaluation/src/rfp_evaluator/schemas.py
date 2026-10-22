
from pydantic import BaseModel, Field


class CriterionEvaluation(BaseModel):
    score: float = Field(ge=0, le=10)
    justification: str
    evidence: str


class SupplierEvaluation(BaseModel):
    supplier_name: str
    criteria: dict[str, CriterionEvaluation]
    risks: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
