"""
trade_simulator.py — Simulación de trades sobre datos M1

Dado un setup (entrada, SL, TP, dirección) y los datos M1 del período post-entrada,
simula la evolución del trade tick a tick (barra M1) y determina el resultado.

Reglas de simulación V1 (todas confirmadas salvo buffer SL):
  - Entrada: primer open M1 tras la barra de confirmación M15 (modo conservador)
  - TP = entry ± 2R (R = distancia entry→SL)
  - SL = distal del POI ± 0.5 pips buffer
  - BE tipo A: si price alcanza entry ± 1R → SL se mueve a entry (punto de equilibrio)
  - TIME_EXIT: si price no llega a TP ni SL en 6 barras M15 (90 min en M1: 90 barras)
  - AMBIGUOUS: si TP y SL se cruzan en la misma barra M1
  - Costes: spread central 0.2 pips (ASK = BID + spread para BUY)
  - Precio BID de M1 se usa directamente para SL/TP checks

Precios efectivos:
  BUY:
    entry_ask = entry_bid + spread
    SL se activa cuando M1 low  <= sl_price  (BID terms)
    TP se activa cuando M1 high >= tp_price  (BID terms)
    BE  se activa cuando M1 high >= be_price (BID terms)
  SELL:
    entry_bid directamente
    SL se activa cuando M1 high >= sl_price  (BID terms)
    TP se activa cuando M1 low  <= tp_price  (BID terms)
    BE  se activa cuando M1 low  <= be_price (BID terms)

P&L final:
  Se calcula en términos BID: exit_bid - entry_bid (BUY) o entry_bid - exit_bid (SELL),
  luego se restan los costes del CostModel.

Exit codes:
  "TP"        — take profit alcanzado
  "SL"        — stop loss alcanzado (o stop en BE)
  "BE"        — stop loss en breakeven alcanzado (salida en entry, = SL en BE)
  "TIME_EXIT" — horizonte de 90 min expirado
  "AMBIGUOUS" — TP y SL en la misma barra M1

resultado binario:
  1 si net_pnl_pips > 0  (TP y BE)
  0 si net_pnl_pips <= 0 (SL, TIME_EXIT, AMBIGUOUS)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from src.backtesting.cost_model import CostModel, DEFAULT_COST_MODEL, PIP

MAX_BARS_M1 = 90       # 90 min × 1 bar/min = 6 barras M15
BE_TRIGGER_R = 1.0     # mover SL a entry cuando se alcanza +1R


@dataclass
class TradeResult:
    """Resultado de la simulación de un trade."""
    exit_reason:   str             # "TP" | "SL" | "BE" | "TIME_EXIT" | "AMBIGUOUS"
    exit_time:     pd.Timestamp
    exit_bid:      float           # precio BID de salida
    gross_pips:    float           # P&L bruto en pips (sin costes)
    net_pips:      float           # P&L neto en pips (con costes)
    net_usd:       float           # P&L neto en USD (1 lote estándar)
    resultado:     int             # 1 = positivo (net_pips > 0), 0 = no positivo


def simulate_trade(
    direction:  Literal["buy", "sell"],
    entry_bid:  float,
    sl_price:   float,   # precio SL en BID terms
    tp_price:   float,   # precio TP en BID terms
    m1_slice:   pd.DataFrame,
    *,
    cost_model: CostModel = DEFAULT_COST_MODEL,
    scenario:   str = "central",
    lots:       float = 1.0,
    be_trigger_r: float = BE_TRIGGER_R,
    max_bars:   int = MAX_BARS_M1,
) -> TradeResult:
    """
    Simula un trade sobre la ventana M1 `m1_slice`.

    Parámetros
    ----------
    direction  : "buy" o "sell"
    entry_bid  : precio BID de entrada (open de la primera barra M1)
    sl_price   : nivel de SL en BID terms
    tp_price   : nivel de TP en BID terms
    m1_slice   : DataFrame M1 desde el momento de entrada, con OHLC.
                 Primera fila = primera barra activa del trade.
    cost_model : modelo de costes a usar
    scenario   : "central" | "optimistic" | "pessimistic"
    lots       : número de lotes estándar (para P&L USD)
    be_trigger_r : multiplicador de R para activar BE (default 1.0 = +1R)
    max_bars   : máximo de barras M1 antes de TIME_EXIT (default 90)

    Devuelve
    --------
    TradeResult con todos los campos de resultado.
    """
    risk = abs(entry_bid - sl_price)
    if risk <= 0:
        # Configuración inválida → TIME_EXIT inmediato
        return TradeResult(
            exit_reason="TIME_EXIT",
            exit_time=pd.Timestamp(m1_slice["datetime"].iat[0]) if "datetime" in m1_slice.columns else pd.NaT,
            exit_bid=entry_bid,
            gross_pips=0.0,
            net_pips=-cost_model.__getattribute__(scenario).total_cost_pips(lots),
            net_usd=-cost_model.__getattribute__(scenario).total_cost_usd(lots),
            resultado=0,
        )

    be_level = entry_bid + be_trigger_r * risk if direction == "buy" else entry_bid - be_trigger_r * risk
    be_active = False
    current_sl = sl_price

    sc = getattr(cost_model, scenario)

    highs = m1_slice["high"].values
    lows  = m1_slice["low"].values
    dts   = m1_slice["datetime"].values if "datetime" in m1_slice.columns else m1_slice.index.values

    n_bars = min(len(m1_slice), max_bars)

    for j in range(n_bars):
        bar_high = highs[j]
        bar_low  = lows[j]
        bar_ts   = pd.Timestamp(dts[j])

        # Activar BE si aún no está activo
        if not be_active:
            if direction == "buy"  and bar_high >= be_level:
                be_active = True
                current_sl = entry_bid
            elif direction == "sell" and bar_low <= be_level:
                be_active = True
                current_sl = entry_bid

        # Check SL (con SL posiblemente movido a BE)
        if direction == "buy":
            sl_hit = bar_low  <= current_sl
            tp_hit = bar_high >= tp_price
        else:
            sl_hit = bar_high >= current_sl
            tp_hit = bar_low  <= tp_price

        # AMBIGUOUS: TP y SL en la misma barra M1
        if tp_hit and sl_hit:
            exit_bid   = entry_bid   # aproximación conservadora: exit en entry
            gross_pips = 0.0
            net_pips   = gross_pips - sc.total_cost_pips(lots)
            return TradeResult(
                exit_reason="AMBIGUOUS",
                exit_time=bar_ts,
                exit_bid=exit_bid,
                gross_pips=gross_pips,
                net_pips=net_pips,
                net_usd=CostModel.pnl_usd(net_pips, lots),
                resultado=0,
            )

        if tp_hit:
            exit_bid   = tp_price
            gross_pips = CostModel.pnl_pips(sc.entry_price(entry_bid, direction), tp_price, direction)
            net_pips   = cost_model.net_pnl_pips(sc.entry_price(entry_bid, direction), tp_price, direction, lots, scenario)
            return TradeResult(
                exit_reason="TP",
                exit_time=bar_ts,
                exit_bid=exit_bid,
                gross_pips=gross_pips,
                net_pips=net_pips,
                net_usd=CostModel.pnl_usd(net_pips, lots),
                resultado=1 if net_pips > 0 else 0,
            )

        if sl_hit:
            exit_bid   = current_sl
            reason     = "BE" if be_active else "SL"
            gross_pips = CostModel.pnl_pips(sc.entry_price(entry_bid, direction), exit_bid, direction)
            net_pips   = cost_model.net_pnl_pips(sc.entry_price(entry_bid, direction), exit_bid, direction, lots, scenario)
            return TradeResult(
                exit_reason=reason,
                exit_time=bar_ts,
                exit_bid=exit_bid,
                gross_pips=gross_pips,
                net_pips=net_pips,
                net_usd=CostModel.pnl_usd(net_pips, lots),
                resultado=1 if net_pips > 0 else 0,
            )

    # TIME_EXIT: cerramos al close de la última barra
    exit_bid   = m1_slice["close"].iat[n_bars - 1] if n_bars > 0 else entry_bid
    exit_ts    = pd.Timestamp(dts[n_bars - 1]) if n_bars > 0 else pd.NaT
    entry_eff  = sc.entry_price(entry_bid, direction)
    gross_pips = CostModel.pnl_pips(entry_eff, exit_bid, direction)
    net_pips   = cost_model.net_pnl_pips(entry_eff, exit_bid, direction, lots, scenario)
    return TradeResult(
        exit_reason="TIME_EXIT",
        exit_time=exit_ts,
        exit_bid=exit_bid,
        gross_pips=gross_pips,
        net_pips=net_pips,
        net_usd=CostModel.pnl_usd(net_pips, lots),
        resultado=1 if net_pips > 0 else 0,
    )


def get_m1_slice(
    m1: pd.DataFrame,
    entry_time: pd.Timestamp,
    max_bars: int = MAX_BARS_M1,
) -> pd.DataFrame:
    """
    Extrae la ventana M1 desde `entry_time` (inclusive) con hasta `max_bars` barras.

    m1 debe tener columna 'datetime' (UTC, no como índice).
    """
    if "datetime" not in m1.columns:
        raise ValueError("m1 debe tener columna 'datetime'")
    mask = m1["datetime"] >= entry_time
    subset = m1[mask].head(max_bars)
    return subset.reset_index(drop=True)
