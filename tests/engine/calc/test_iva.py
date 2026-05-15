from decimal import Decimal
from gestnova_accounting.engine.calc.iva import forward_iva, reverse_iva


def test_forward_iva_21pct():
    result = forward_iva(base=Decimal("2400"), rate=Decimal("0.21"))
    assert result.base == Decimal("2400.00")
    assert result.iva == Decimal("504.00")
    assert result.total == Decimal("2904.00")


def test_forward_iva_10pct():
    result = forward_iva(base=Decimal("43.45"), rate=Decimal("0.10"))
    assert result.iva == Decimal("4.35")
    assert result.total == Decimal("47.80")


def test_reverse_iva_21pct():
    result = reverse_iva(total=Decimal("2904"), rate=Decimal("0.21"))
    assert result.base == Decimal("2400.00")
    assert result.iva == Decimal("504.00")
    assert result.total == Decimal("2904.00")


def test_reverse_iva_10pct_with_rounding():
    result = reverse_iva(total=Decimal("47.80"), rate=Decimal("0.10"))
    # 47.80 / 1.10 = 43.4545... → 43.45 (round half up to 2 decimals)
    assert result.base == Decimal("43.45")
    assert result.iva == Decimal("4.35")


def test_rounding_half_up_at_cent():
    """0.005 must round up to 0.01 (standard commercial rounding)."""
    # base 10.005 at 21% → iva = 2.10105 → rounds to 2.10
    result = forward_iva(base=Decimal("10.005"), rate=Decimal("0.21"))
    assert result.iva == Decimal("2.10")
