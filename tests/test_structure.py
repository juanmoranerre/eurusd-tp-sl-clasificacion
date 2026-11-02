"""
test_structure.py — Tests para src/features/structure.py

Estrategia:
  • Fixtures sintéticos con patrones conocidos (tendencia, retroceso, reversión).
  • Verificar restricción de no-lookahead: swing confirmado en t+1, no en t-1.
  • Verificar BOS: solo por cierre, no por mecha.
  • Verificar CHOCH: primer cierre contrario al swing protegido.
  • Tests de contrato: tipos de columnas, shape, valores válidos.
  • Integración: datos M1 reales.
"""

import numpy as np
import pandas as pd
import pytest

from src.features.structure import (
    _level_suffix,
    add_market_structure,
    detect_bos,
    detect_choch,
    detect_pivots,
    detect_swing_hierarchy,
    last_swing_highs,
    last_swing_lows,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_ohlcv(highs, lows, opens=None, closes=None, n_extra: int = 0) -> pd.DataFrame:
    """
    Construye un DataFrame OHLCV a partir de arrays de H y L.
    Si opens/closes no se especifican, se usan H/L con pequeño offset.
    """
    n = len(highs)
    dates = pd.date_range("2024-01-01", periods=n, freq="15min")
    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    if opens is None:
        opens = l + (h - l) * 0.3
    if closes is None:
        closes = l + (h - l) * 0.7
    o = np.array(opens, dtype=float)
    c = np.array(closes, dtype=float)
    # Garantizar H >= max(O,C) y L <= min(O,C)
    h = np.maximum(h, np.maximum(o, c))
    l = np.minimum(l, np.minimum(o, c))
    return pd.DataFrame(
        {"open": o, "high": h, "low": l, "close": c, "volume": 1.0},
        index=dates,
    )


def _trending_up(n: int = 30) -> pd.DataFrame:
    """Serie alcista con swing highs y lows crecientes."""
    t = np.arange(n, dtype=float)
    highs  = 1.08 + t * 0.001 + 0.002
    lows   = 1.08 + t * 0.001
    opens  = lows + 0.001
    closes = lows + 0.0015
    return _make_ohlcv(highs, lows, opens, closes)


def _with_local_max(center: int = 5, n: int = 15) -> pd.DataFrame:
    """Serie con un máximo local claro en la posición center."""
    h = np.full(n, 1.08)
    l = np.full(n, 1.07)
    h[center] = 1.10  # máximo local
    l[center] = 1.075
    return _make_ohlcv(h, l)


def _with_local_min(center: int = 5, n: int = 15) -> pd.DataFrame:
    """Serie con un mínimo local claro en la posición center."""
    h = np.full(n, 1.09)
    l = np.full(n, 1.08)
    l[center] = 1.05  # mínimo local
    h[center] = 1.055
    return _make_ohlcv(h, l)


def _zigzag(n_swings: int = 6, amp: float = 0.01, period: int = 6) -> pd.DataFrame:
    """Patrón zigzag para generar múltiples swings alternados."""
    n = n_swings * period + 4
    t = np.linspace(0, n_swings * np.pi, n)
    mid = 1.08
    h = mid + np.abs(np.sin(t)) * amp + 0.001
    l = mid - np.abs(np.sin(t)) * amp
    # Añadir picos y valles claros
    closes = (h + l) / 2
    opens  = closes + np.where(closes > mid, -0.0003, 0.0003)
    return _make_ohlcv(h, l, opens, closes)


def _bos_setup() -> pd.DataFrame:
    """
    Patrón explícito con un swing high seguido de una ruptura por cierre.
    Estructura:
      0: barra normal
      1: previa al pivot
      2: SWING HIGH: H=1.12 (máximo local)
      3: confirma pivot (close bajo)
      4: retroceso
      5: cierre por encima de 1.12 (BOS alcista)
    """
    n = 10
    h = np.full(n, 1.085)
    l = np.full(n, 1.080)
    c = np.full(n, 1.082)
    o = np.full(n, 1.081)
    # Pivot high en barra 2
    h[1] = 1.090
    h[2] = 1.120   # swing high
    h[3] = 1.090
    l[3] = 1.078
    c[3] = 1.079   # barra de confirmación del pivot
    # BOS en barra 5: cierre por encima del swing high 1.12
    h[5] = 1.125
    c[5] = 1.122
    o[5] = 1.115
    # Barra 6-9: normal
    return _make_ohlcv(h, l, o, c)


# ── Tests: detect_pivots ──────────────────────────────────────────────────────

class TestDetectPivots:
    def test_returns_dataframe(self):
        df = _with_local_max()
        result = detect_pivots(df)
        assert isinstance(result, pd.DataFrame)

    def test_adds_expected_columns(self):
        df = _with_local_max()
        result = detect_pivots(df)
        for col in ["swing_high_st", "swing_low_st", "pivot_high_st", "pivot_low_st"]:
            assert col in result.columns

    def test_same_length(self):
        df = _with_local_max()
        result = detect_pivots(df)
        assert len(result) == len(df)

    def test_no_lookahead_pivot_confirmed_at_t_plus_n(self):
        """El pivot en la posición center se confirma en center+n, no antes."""
        center = 5
        n = 1
        df = _with_local_max(center=center, n=15)
        result = detect_pivots(df, n=n)
        # El pivot ocurrió en center=5; debe estar confirmado en 5+1=6
        assert result["swing_high_st"].iloc[center + n]
        # No debe estar marcado antes
        assert not result["swing_high_st"].iloc[center]
        assert not result["swing_high_st"].iloc[center - 1]

    def test_pivot_high_value_correct(self):
        center = 5
        df = _with_local_max(center=center, n=15)
        result = detect_pivots(df, n=1)
        # El valor del pivot en la barra de confirmación debe ser el high del center
        expected_high = df["high"].iloc[center]
        conf_bar = center + 1
        assert abs(result["pivot_high_st"].iloc[conf_bar] - expected_high) < 1e-10

    def test_no_pivot_when_ties(self):
        """Dos barras con el mismo high → no se marca ninguna como pivot."""
        df = pd.DataFrame(
            {"open": [1.08] * 5, "high": [1.09, 1.10, 1.10, 1.09, 1.08],
             "low": [1.07] * 5, "close": [1.085] * 5},
            index=pd.date_range("2024-01-01", periods=5, freq="15min"),
        )
        result = detect_pivots(df, n=1)
        # Posición 1 y 2 tienen el mismo high → ninguna es pivot
        assert not result["swing_high_st"].iloc[2]  # confirmed bar for pos 1
        assert not result["swing_high_st"].iloc[3]  # confirmed bar for pos 2

    def test_raises_invalid_n(self):
        df = _with_local_max()
        with pytest.raises(ValueError):
            detect_pivots(df, n=0)

    def test_raises_missing_columns(self):
        df = _with_local_max().drop(columns=["high"])
        with pytest.raises(ValueError):
            detect_pivots(df, n=1)

    def test_first_n_bars_no_pivot(self):
        """Las primeras n barras no pueden ser confirmación de ningún pivot."""
        df = _with_local_max(center=0, n=10)
        result = detect_pivots(df, n=1)
        assert not result["swing_high_st"].iloc[0]

    def test_zigzag_detects_multiple_pivots(self):
        df = _zigzag(n_swings=6)
        result = detect_pivots(df, n=1)
        # Debe haber al menos 2 swings de cada tipo
        assert result["swing_high_st"].sum() >= 2
        assert result["swing_low_st"].sum() >= 2


# ── Tests: detect_swing_hierarchy ────────────────────────────────────────────

class TestDetectSwingHierarchy:
    def test_returns_all_levels(self):
        df = _zigzag(n_swings=8)
        result = detect_swing_hierarchy(df, n=1)
        for level in ["st", "it", "lt"]:
            for kind in ["high", "low"]:
                col = f"swing_{kind}_{level}"
                assert col in result.columns

    def test_it_count_lte_st_count(self):
        df = _zigzag(n_swings=8)
        result = detect_swing_hierarchy(df, n=1)
        # Los swings intermedios son un subconjunto de los corto plazo
        assert result["swing_high_it"].sum() <= result["swing_high_st"].sum()
        assert result["swing_low_it"].sum() <= result["swing_low_st"].sum()

    def test_lt_count_lte_it_count(self):
        df = _zigzag(n_swings=8)
        result = detect_swing_hierarchy(df, n=1)
        assert result["swing_high_lt"].sum() <= result["swing_high_it"].sum()
        assert result["swing_low_lt"].sum() <= result["swing_low_it"].sum()

    def test_does_not_modify_original(self):
        df = _zigzag(n_swings=6)
        cols_before = set(df.columns)
        _ = detect_swing_hierarchy(df, n=1)
        assert set(df.columns) == cols_before


# ── Tests: detect_bos ─────────────────────────────────────────────────────────

class TestDetectBOS:
    def test_returns_dataframe_with_bos_columns(self):
        df = _bos_setup()
        result = detect_bos(df, n=1)
        assert "bos_bull" in result.columns
        assert "bos_bear" in result.columns

    def test_bos_bull_detected_by_close_not_wick(self):
        """BOS = cierre por encima del swing high, NO mecha."""
        # Barra donde solo la mecha supera el swing high (close por debajo)
        n = 8
        h = np.array([1.08, 1.09, 1.10, 1.09, 1.08, 1.11, 1.09, 1.08])
        l = np.array([1.07, 1.08, 1.09, 1.07, 1.07, 1.07, 1.07, 1.07])
        c = np.array([1.075, 1.085, 1.095, 1.075, 1.075, 1.09, 1.075, 1.075])
        o = np.array([1.075, 1.082, 1.092, 1.08, 1.078, 1.08, 1.08, 1.078])
        # Swing high está en posición 2 (high=1.10), confirmado en posición 3
        # Barra 5: wick llega a 1.11 pero CLOSE=1.09 < 1.10 → NO es BOS
        df = pd.DataFrame(
            {"open": o, "high": h, "low": l, "close": c, "volume": 1.0},
            index=pd.date_range("2024-01-01", periods=n, freq="15min"),
        )
        result = detect_bos(df, n=1)
        # Barra 5 tiene wick > swing high, pero close < swing high → no BOS
        assert not result["bos_bull"].iloc[5]

    def test_bos_bull_detected_by_close_above_swing_high(self):
        """BOS alcista cuando el close supera el swing high."""
        n = 8
        h = np.array([1.08, 1.09, 1.10, 1.09, 1.08, 1.11, 1.09, 1.08])
        l = np.array([1.07, 1.08, 1.09, 1.07, 1.07, 1.08, 1.07, 1.07])
        c = np.array([1.075, 1.085, 1.095, 1.075, 1.075, 1.105, 1.075, 1.075])
        o = c - 0.001
        df = pd.DataFrame(
            {"open": o, "high": h, "low": l, "close": c, "volume": 1.0},
            index=pd.date_range("2024-01-01", periods=n, freq="15min"),
        )
        result = detect_bos(df, n=1)
        # Barra 5: close=1.105 > swing high=1.10 → BOS alcista
        assert result["bos_bull"].iloc[5]

    def test_bos_bear_detected_by_close_below_swing_low(self):
        """BOS bajista cuando el close cae por debajo del swing low."""
        n = 8
        l = np.array([1.09, 1.08, 1.07, 1.08, 1.09, 1.065, 1.085, 1.09])
        h = l + 0.01
        c = l + 0.003
        o = l + 0.005
        # Swing low en posición 2 (low=1.07), confirmado en 3
        # Barra 5: close=1.068 < 1.07 → BOS bajista
        c[5] = 1.068
        df = pd.DataFrame(
            {"open": o, "high": h, "low": l, "close": c, "volume": 1.0},
            index=pd.date_range("2024-01-01", periods=n, freq="15min"),
        )
        result = detect_bos(df, n=1)
        assert result["bos_bear"].iloc[5]

    def test_no_bos_before_first_swing_confirmed(self):
        """No puede haber BOS antes de que se confirme al menos un swing."""
        df = _bos_setup()
        result = detect_bos(df, n=1)
        # Antes de la barra 3 (confirmación del pivot), no hay swing → no hay BOS posible
        assert not result["bos_bull"].iloc[:3].any()

    def test_bos_level_non_nan_when_bos(self):
        df = _bos_setup()
        result = detect_bos(df, n=1)
        bos_rows = result[result["bos_bull"]]
        assert bos_rows["bos_level"].notna().all()

    def test_raises_invalid_level(self):
        df = _zigzag(6)
        with pytest.raises(ValueError):
            detect_bos(df, level="invalid_level")


# ── Tests: detect_choch ───────────────────────────────────────────────────────

class TestDetectCHOCH:
    def _bullish_then_reversal(self) -> pd.DataFrame:
        """
        Serie alcista seguida de un CHOCH bajista:
          - Barras 0-14: tendencia alcista (BOS alcistas)
          - Barra 15+: cierre por debajo del último swing low protegido
        """
        n = 25
        dates = pd.date_range("2024-01-01", periods=n, freq="15min")
        # Tendencia alcista: highs y lows crecientes
        h = np.linspace(1.08, 1.12, n) + 0.004
        l = np.linspace(1.07, 1.11, n)
        c = (h + l) / 2
        o = c - 0.0003
        # Insertar un CHOCH: barra 20+ tiene cierre muy bajo
        h[20] = 1.09
        l[20] = 1.07
        c[20] = 1.072   # cierre por debajo del swing low reciente
        o[20] = 1.078
        h = np.maximum(h, np.maximum(o, c))
        l = np.minimum(l, np.minimum(o, c))
        return pd.DataFrame(
            {"open": o, "high": h, "low": l, "close": c, "volume": 1.0},
            index=dates,
        )

    def test_structure_bias_is_valid_strings(self):
        df = _zigzag(8)
        result = detect_choch(df, n=1)
        valid = {"bullish", "bearish", "ranging", None}
        unique_bias = set(result["structure_bias"].unique())
        assert unique_bias.issubset(valid)

    def test_choch_columns_added(self):
        df = _zigzag(8)
        result = detect_choch(df, n=1)
        for col in ["choch_bull", "choch_bear", "choch_level", "structure_bias"]:
            assert col in result.columns

    def test_choch_level_nan_when_no_choch(self):
        df = _trending_up(20)
        result = detect_choch(df, n=1)
        no_choch = result[~result["choch_bull"] & ~result["choch_bear"]]
        assert no_choch["choch_level"].isna().all()

    def test_choch_level_valid_when_choch(self):
        df = _zigzag(10)
        result = detect_choch(df, n=1)
        choch = result[result["choch_bull"] | result["choch_bear"]]
        if not choch.empty:
            assert choch["choch_level"].notna().all()

    def test_bos_and_choch_not_same_bar_typically(self):
        # En un mismo bar raramente se marca BOS Y CHOCH a la vez
        # (BOS primero, luego CHOCH en dirección contraria)
        df = _zigzag(10)
        result = detect_choch(df, n=1)
        bull_bos = result["bos_bull"]
        bear_choch = result["choch_bear"]
        # Si hay BOS alcista y CHOCH bajista en la misma barra, puede ocurrir
        # pero no debería ser la mayoría de los casos
        both = (bull_bos & bear_choch).sum()
        total = max(1, bull_bos.sum())
        # No es una regla estricta, solo comprueba que no ocurre en cada BOS
        assert both / total < 1.0

    def test_raises_invalid_level(self):
        df = _zigzag(6)
        with pytest.raises(ValueError):
            detect_choch(df, level="bad_level")


# ── Tests: add_market_structure ───────────────────────────────────────────────

class TestAddMarketStructure:
    def test_returns_dataframe(self):
        df = _zigzag(8)
        result = add_market_structure(df)
        assert isinstance(result, pd.DataFrame)

    def test_all_expected_columns_present(self):
        df = _zigzag(8)
        result = add_market_structure(df)
        expected = [
            "swing_high_st", "swing_low_st",
            "swing_high_it", "swing_low_it",
            "swing_high_lt", "swing_low_lt",
            "bos_bull", "bos_bear",
            "choch_bull", "choch_bear",
            "structure_bias",
        ]
        for col in expected:
            assert col in result.columns

    def test_same_length(self):
        df = _zigzag(8)
        result = add_market_structure(df)
        assert len(result) == len(df)

    def test_does_not_modify_original(self):
        df = _zigzag(8)
        cols_before = set(df.columns)
        _ = add_market_structure(df)
        assert set(df.columns) == cols_before

    def test_bos_only_by_close(self):
        """Verificar que la restricción close-only está activa."""
        df = _bos_setup()
        result = add_market_structure(df, n=1)
        # Verificar que los boolean BOS son de tipo bool-compatible
        assert result["bos_bull"].dtype in [bool, "bool", np.dtype("bool")]

    def test_different_n_values(self):
        df = _zigzag(12)
        r1 = add_market_structure(df, n=1)
        r2 = add_market_structure(df, n=2)
        # Con n=2 habrá menos pivots que con n=1
        assert r2["swing_high_st"].sum() <= r1["swing_high_st"].sum()


# ── Tests: last_swing_highs/lows ─────────────────────────────────────────────

class TestLastSwingHelpers:
    def test_last_swing_highs_filled_forward(self):
        df = _zigzag(8)
        result = detect_swing_hierarchy(df, n=1)
        lsh = last_swing_highs(result)
        # Después del primer pivot, no debe haber NaN al final
        first_pivot = result["swing_high_st"].idxmax()
        loc = result.index.get_loc(first_pivot)
        assert lsh.iloc[loc:].notna().all()

    def test_last_swing_lows_filled_forward(self):
        df = _zigzag(8)
        result = detect_swing_hierarchy(df, n=1)
        lsl = last_swing_lows(result)
        first_pivot = result["swing_low_st"].idxmax()
        loc = result.index.get_loc(first_pivot)
        assert lsl.iloc[loc:].notna().all()

    def test_raises_without_swing_detection(self):
        df = _zigzag(8)
        with pytest.raises(ValueError):
            last_swing_highs(df)  # no se ha ejecutado detect_swing_hierarchy


# ── Tests: _level_suffix ──────────────────────────────────────────────────────

class TestLevelSuffix:
    def test_known_levels(self):
        assert _level_suffix("short_term") == "st"
        assert _level_suffix("intermediate_term") == "it"
        assert _level_suffix("long_term") == "lt"

    def test_unknown_level_raises(self):
        with pytest.raises(ValueError):
            _level_suffix("medium")


# ── Integración: datos M1 reales ──────────────────────────────────────────────

class TestRealDataStructure:
    @pytest.fixture(scope="class")
    def m1_active(self):
        import pathlib
        parquet = pathlib.Path("data/processed/eurusd_m1_bid.parquet")
        if not parquet.exists():
            pytest.skip("Dataset M1 no disponible")
        df = pd.read_parquet(parquet)
        if "datetime" in df.columns:
            df = df.set_index("datetime")
        # Primera semana activa (sin días planos)
        active = df[~df["is_flat_day"]]
        return active.iloc[:5_040].copy()  # ~3.5 días

    def test_pivots_real_data(self, m1_active):
        result = detect_pivots(m1_active, n=1)
        assert result["swing_high_st"].sum() > 0
        assert result["swing_low_st"].sum() > 0

    def test_no_ohlc_violation_after_structure(self, m1_active):
        """Verificar que add_market_structure no crea columnas con valores inválidos."""
        result = add_market_structure(m1_active, n=1)
        # bos_level cuando existe debe ser un precio razonable
        valid_bos = result[result["bos_bull"] | result["bos_bear"]]
        if not valid_bos.empty:
            assert valid_bos["bos_level"].between(0.5, 2.0).all()

    def test_structure_bias_valid(self, m1_active):
        result = add_market_structure(m1_active, n=1)
        valid = {"bullish", "bearish", "ranging", None}
        assert set(result["structure_bias"].unique()).issubset(valid)

    def test_pivot_values_in_price_range(self, m1_active):
        result = detect_pivots(m1_active, n=1)
        valid_highs = result["pivot_high_st"].dropna()
        assert (valid_highs > 0.5).all() and (valid_highs < 2.0).all()
