"""VAT (IVA) primitives — forward and reverse computation with commercial rounding."""
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel


CENT = Decimal("0.01")


def _round(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


class IVABreakdown(BaseModel):
    base: Decimal
    iva: Decimal
    total: Decimal
    rate: Decimal

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


def forward_iva(*, base: Decimal, rate: Decimal) -> IVABreakdown:
    """Given base price and VAT rate, return iva and total (with cent rounding)."""
    iva = _round(base * rate)
    base_r = _round(base)
    return IVABreakdown(base=base_r, iva=iva, total=_round(base_r + iva), rate=rate)


def reverse_iva(*, total: Decimal, rate: Decimal) -> IVABreakdown:
    """Given a total price that INCLUDES VAT, derive base and iva."""
    base = _round(total / (Decimal("1") + rate))
    iva = _round(total - base)
    return IVABreakdown(base=base, iva=iva, total=_round(total), rate=rate)
