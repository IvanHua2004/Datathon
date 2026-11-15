"""Tests unitaires du module rdc.format : mise en forme uniforme des nombres et unités."""
from rdc import format as fmt


def test_pct():
    assert fmt.pct(0.1234) == "12,3 %"
    assert fmt.pct(0.0) == "0,0 %"
    assert fmt.pct(-0.0567) == "-5,7 %"
    assert fmt.pct(1.0) == "100,0 %"
    assert fmt.pct(0.1234, decimales=2) == "12,34 %"
    assert fmt.pct(0.1234, decimales=0) == "12 %"


def test_dollars():
    assert fmt.dollars(100_000.0) == "100 000 $"
    assert fmt.dollars(1_234_567.89) == "1 234 600 $"  # arrondi aux 100 $
    assert fmt.dollars(0.0) == "0 $"
    assert fmt.dollars(-45_230.0) == "-45 200 $"
    assert fmt.dollars(99.0) == "100 $"
    assert fmt.dollars(49.0) == "0 $"


def test_nombre():
    assert fmt.nombre(3.14159) == "3,14"
    assert fmt.nombre(3.14159, decimales=3) == "3,142"
    assert fmt.nombre(0.0) == "0,00"
    assert fmt.nombre(-12.5, decimales=1) == "-12,5"


def test_annees():
    assert fmt.annees(1.0) == "1,0 an"
    assert fmt.annees(0.5) == "0,5 an"
    assert fmt.annees(2.0) == "2,0 ans"
    assert fmt.annees(5.3) == "5,3 ans"
    assert fmt.annees(10.0) == "10,0 ans"
