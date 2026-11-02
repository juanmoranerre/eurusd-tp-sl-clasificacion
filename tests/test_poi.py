"""
test_poi.py — Tests para src/features/poi.py
"""

import numpy as np
import pandas as pd
import pytest

from src.features.poi import (
    POI, POIDirection, POIState, POIType,
    add_poi_features,
    detect_fvg,
    detect_order_blocks,
    track_poi_states,
)


def _df(highs, lows, opens=None, closes=None):
    n = len(highs)
    h = np.array(highs, dtype=float)
    l = np.array(lows,  dtype=float)
    c = np.array(closes if closes is not None else [(h[i]+l[i])/2 for i in range(n)], dtype=float)
    o = np.array(opens  if opens  is not None else [(h[i]+l[i])/2 - 0.0002 for i in range(n)], dtype=float)
    h = np.maximum(h, np.maximum(o, c))
    l = np.minimum(l, np.minimum(o, c))
    return pd.DataFrame(
        {"open": o, "high": h, "low": l, "close": c, "volume": 1.0},
        index=pd.date_range("2024-01-01", periods=n, freq="15min"),
    )


class TestDetectFVG:
    def test_bullish_fvg(self):
        # c1.high < c3.low → FVG alcista en barra 2
        df = _df([1.08, 1.09, 1.12], [1.07, 1.08, 1.11])
        result = detect_fvg(df)
        # FVG alcista: high(c1=0)=1.08 < low(c3=2)=1.11 → marcado en barra 2
        assert result["fvg_bull"].iloc[2]
        assert not result["fvg_bull"].iloc[0]
        assert not result["fvg_bull"].iloc[1]

    def test_bearish_fvg(self):
        # c1.low > c3.high → FVG bajista
        df = _df([1.10, 1.09, 1.06], [1.09, 1.08, 1.05])
        result = detect_fvg(df)
        assert result["fvg_bear"].iloc[2]

    def test_no_fvg_overlapping_bars(self):
        # Barras que se solapan: no hay gap
        df = _df([1.09, 1.09, 1.09], [1.08, 1.08, 1.08])
        result = detect_fvg(df)
        assert not result["fvg_bull"].any()
        assert not result["fvg_bear"].any()

    def test_fvg_size_correct(self):
        df = _df([1.08, 1.09, 1.12], [1.07, 1.08, 1.11])
        result = detect_fvg(df)
        # Gap = low(c3) - high(c1) = 1.11 - 1.08 = 0.03
        assert abs(result["fvg_size"].iloc[2] - 0.03) < 1e-10

    def test_fvg_adds_expected_columns(self):
        df = _df([1.08]*5, [1.07]*5)
        result = detect_fvg(df)
        for col in ["fvg_bull", "fvg_bear", "fvg_high", "fvg_low", "fvg_size"]:
            assert col in result.columns

    def test_no_lookahead_first_two_bars(self):
        # No puede haber FVG en las dos primeras barras
        df = _df([1.08, 1.09, 1.12], [1.07, 1.08, 1.11])
        result = detect_fvg(df)
        assert not result["fvg_bull"].iloc[0]
        assert not result["fvg_bull"].iloc[1]


class TestDetectOrderBlocks:
    def test_bullish_ob_detected(self):
        # c[i-1] bajista + c[i] alcista grande → OB alcista en barra i
        n = 6
        o = [1.08, 1.085, 1.082, 1.078, 1.075, 1.08]
        c = [1.083, 1.083, 1.079, 1.075, 1.072, 1.085]
        h = [1.085, 1.087, 1.084, 1.080, 1.078, 1.095]
        l = [1.078, 1.082, 1.079, 1.073, 1.070, 1.078]
        df = _df(h, l, o, c)
        result = detect_order_blocks(df, impulse_min_size=0.005)
        assert result["ob_bull"].any()

    def test_bearish_ob_detected(self):
        n = 6
        o = [1.09, 1.085, 1.088, 1.090, 1.092, 1.09]
        c = [1.085, 1.087, 1.090, 1.093, 1.095, 1.080]
        h = [1.091, 1.088, 1.091, 1.094, 1.097, 1.093]
        l = [1.084, 1.083, 1.087, 1.089, 1.091, 1.079]
        df = _df(h, l, o, c)
        result = detect_order_blocks(df, impulse_min_size=0.005)
        assert result["ob_bear"].any()

    def test_ob_columns_added(self):
        df = _df([1.08]*5, [1.07]*5)
        result = detect_order_blocks(df)
        for col in ["ob_bull", "ob_bear", "ob_high", "ob_low", "ob_open", "ob_close"]:
            assert col in result.columns

    def test_ob_high_not_nan_when_ob(self):
        n = 4
        o = [1.08, 1.082, 1.079, 1.075]
        c = [1.083, 1.079, 1.076, 1.095]
        h = [1.085, 1.083, 1.080, 1.098]
        l = [1.078, 1.078, 1.074, 1.074]
        df = _df(h, l, o, c)
        result = detect_order_blocks(df, impulse_min_size=0.005)
        ob_rows = result[result["ob_bull"] | result["ob_bear"]]
        if not ob_rows.empty:
            assert ob_rows["ob_high"].notna().all()


class TestPOIClass:
    def test_poi_init(self):
        poi = POI(
            poi_type=POIType.FVG,
            direction=POIDirection.BULLISH,
            proximal=1.09,
            distal=1.08,
            created_at=pd.Timestamp("2024-01-01"),
        )
        assert poi.state == POIState.FRESH
        assert poi.touches == 0

    def test_poi_midpoint(self):
        poi = POI(POIType.FVG, POIDirection.BULLISH, 1.09, 1.08, pd.Timestamp("2024-01-01"))
        assert abs(poi.midpoint - 1.085) < 1e-10

    def test_poi_contains(self):
        poi = POI(POIType.FVG, POIDirection.BULLISH, 1.09, 1.08, pd.Timestamp("2024-01-01"))
        assert poi.contains(1.085)
        assert not poi.contains(1.095)

    def test_poi_state_touched(self):
        # wick enters zone (low <= proximal=1.09) but close stays above proximal → TOUCHED
        poi = POI(POIType.FVG, POIDirection.BULLISH, 1.09, 1.08, pd.Timestamp("2024-01-01"))
        poi.update_state(low=1.088, high=1.095, close=1.095)
        assert poi.state == POIState.TOUCHED

    def test_poi_state_partially_mitigated(self):
        # close inside zone (distal=1.08 < close=1.085 < proximal=1.09) → partially_mitigated
        poi = POI(POIType.FVG, POIDirection.BULLISH, 1.09, 1.08, pd.Timestamp("2024-01-01"))
        poi.update_state(low=1.082, high=1.095, close=1.085)
        assert poi.state == POIState.PARTIALLY_MITIGATED

    def test_poi_state_invalidated_bearish(self):
        # Cierre por encima del distal (para bearish: distal es el extremo superior)
        poi = POI(POIType.ORDER_BLOCK, POIDirection.BEARISH, proximal=1.09, distal=1.10,
                  created_at=pd.Timestamp("2024-01-01"))
        poi.update_state(low=1.09, high=1.105, close=1.102)
        assert poi.state == POIState.INVALIDATED

    def test_poi_state_not_updated_after_invalidation(self):
        poi = POI(POIType.FVG, POIDirection.BULLISH, 1.09, 1.08, pd.Timestamp("2024-01-01"))
        poi.state = POIState.INVALIDATED
        poi.update_state(low=1.085, high=1.095, close=1.092)
        # Estado no cambia
        assert poi.state == POIState.INVALIDATED


class TestAddPOIFeatures:
    def test_returns_dataframe(self):
        df = _df([1.08]*10, [1.07]*10)
        result = add_poi_features(df)
        assert isinstance(result, pd.DataFrame)

    def test_all_columns_present(self):
        df = _df([1.08]*10, [1.07]*10)
        result = add_poi_features(df)
        for col in ["fvg_bull", "fvg_bear", "ob_bull", "ob_bear"]:
            assert col in result.columns

    def test_same_length(self):
        df = _df([1.08]*10, [1.07]*10)
        result = add_poi_features(df)
        assert len(result) == len(df)


class TestTrackPOIStates:
    def test_active_count_non_negative(self):
        df = _df([1.10]*5, [1.08]*5)
        poi = POI(POIType.FVG, POIDirection.BULLISH, proximal=1.09, distal=1.085,
                  created_at=pd.Timestamp("2024-01-01"))
        result = track_poi_states(df, [poi])
        assert (result["active_pois_count"] >= 0).all()

    def test_count_decreases_after_invalidation(self):
        # Precio cierra por debajo del distal → POI invalidado
        n = 4
        df = _df(
            [1.10, 1.10, 1.10, 1.10],
            [1.09, 1.09, 1.09, 1.082],
            opens=[1.095]*4,
            closes=[1.098, 1.098, 1.098, 1.083],
        )
        poi = POI(POIType.FVG, POIDirection.BULLISH, proximal=1.09, distal=1.085,
                  created_at=pd.Timestamp("2024-01-01"))
        result = track_poi_states(df, [poi])
        # Última barra: close=1.083 < distal=1.085 → invalidado → count=0
        assert result["active_pois_count"].iloc[-1] == 0
