"""Campos Pydantic reutilizables para validación de entrada."""
from pydantic import BaseModel, Field


def QtyField(**kw):
    return Field(gt=0, max_digits=18, decimal_places=6, **kw)


def CurrencyField(**kw):
    return Field(min_length=3, max_length=3, pattern="^[A-Z]{3}$", **kw)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)
