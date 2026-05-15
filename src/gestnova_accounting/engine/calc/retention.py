"""ES professional retention rates (Art. 101.5 LIRPF)."""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from ..rule_lookup import RuleLookup


CENT = Decimal("0.01")


def _round(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def compute_retention_es(
    *, lookup: RuleLookup, base: Decimal, is_new_professional: bool, on_date: date
) -> dict:
    rule = lookup.get("ES", "professional_retention_rates", on_date)
    rate_key = "new_professional_first_3_years" if is_new_professional else "standard"
    rate = Decimal(str(rule.data[rate_key]))
    amount = _round(base * rate)
    return {
        "base": _round(base),
        "rate": rate,
        "amount": amount,
        "rules_applied": [
            {"rule": "professional_retention_rates", "effective_from": str(rule.effective_from), "source": rule.source}
        ],
    }
