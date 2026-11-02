"""
trade_simulator.py — Simulación de trades sobre datos M1

Dado un setup (entrada, SL, TP, dirección) y los datos M1 del período post-entrada,
simula la evolución del trade bar a bar (M1) y determina el resultado.

Horizonte máximo:
  El límite es de 90 MINUTOS de tiempo transcurrido desde la entrada efectiva,
  no 90 barras M1. Si hay huecos de datos (fines de semana, festivos, broker down),
  el número de barras disponibles puede ser menor. El trade cierra en la última
  barra disponible dentro del horizonte.

  get_m1_slice() filtra las barras por tiempo antes de pasarlas al simulador.
  simulate_trade() procesa todas las barras del slice sin límite de conteo.

Reglas de simulación V1:
  - Entrada: primer open M1 tras la barra de confirmación M15 (modo conservador)
  - TP = entry ± 2R (R = distancia entry→SL)
  - SL = distal del POI ± 0.5 pips buffer (P-C provisional)
  - BE tipo A: si price alcanza entry ± 1R → SL se mueve a entry
  - TIME_EXIT: si price no llega a TP ni SL dentro del horizonte de 90 min
  - AMBIGUOUS: si TP y SL se cruzan en la misma barra M1

Precios efectivos:
  BUY:
    entry_ask = entry_bid + spread
    SL se activa cuando M1 low  <= sl_price  (BID terms)
    TP se activa cuando M1 high >= tp_price  (BID terms)
    BE se activa cuando M1 high >= be_price  (BID terms)
  SELL:
    entry_bid directamente
    SL se activa cuando M1 high >= sl_price  (BID terms)
    TP se activa cuando M1 low  <= tp_price  (BID terms)
    BE se activa cuando M1 low  <= be_price  (BID terms)

Resultado binario:
  resultado = 1 si net_pips > 0
  resultado = 0 si net_pips <= 0

  Exit codes y resultado esperado:
    TP        → resultado = 1 (salvo coste > gross, teóricamente imposible con 2R)
    SL        → resultado = 0 (pérdida bruta + costes)
    BE        → resultado = 0 (gross ≈ 0, costes negativos)
    TIME_EXIT → resultado = 1 si net_pips > 0, else 0 (depende del precio al cierre)
    AMBIGUOUS → resultado = 0 (conservador; excluido del CSV principal)

Manejo de huecos de datos M1:
  Si get_m1_slice devuelve 0 barras (no hay M1 para ese horario), el trade se
  registra como TIME_EXIT en entry_time con net_pips = -coste.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from src.backtesting.cost_model import CostModel, DEFAULT_COST_MODEL, PIP

MAX_HORIZON_MINUTES = 90   # 6 barras M15 = 90 min (PD-019)
BE_TRIGGER_R        = 1.0  # mover SL a entry cuando se alcanza +1R


@dataclass
class TradeResult:
    """Resultado de la simulación de un trade."""
    exit_reason:   str             # "TP" | "SL" | "BE" | "TIME_EXIT" | "AMBIGUOUS"
    entry_time:    pd.Timestamp    # tiempo de apertura de la primera barra M1
    exit_time:     pd.Timestamp
    exit_bid:      float
    gross_pips:    float
    net_pips:      float
    net_usd:       float
    resultado:     int             # 1 si net_pips > 0, else 0


def simulate_trade(
    direction:    Literal["buy", "sell"],
    entry_bid:    float,
    sl_price:     float,
    tp_price:     float,
    m1_slice:     pd.DataFrame,
    *,
    cost_model:   CostModel = DEFAULT_COST_MODEL,
    scenario:     str = "central",
    lots:         float = 1.0,
    be_trigger_r: float = BE_TRIGGER_R,
) -> TradeResult:
    """
    Simula un trade sobre la ventana M1 `m1_slice`.

    m1_slice debe contener solo las barras dentro del horizonte temporal
    (generado por get_m1_slice). El simulador procesa todas las barras
    sin límite de conteo adicional.

    Parámetros
    ----------
    direction   : "buy" o "sell"
    entry_bid   : precio BID de entrada (open de la primera barra M1 del slice)
    sl_price    : nivel de SL en BID terms
    tp_price    : nivel de TP en BID terms
    m1_slice    : DataFrame M1 dentro del horizonte de 90 min, con OHLC y 'datetime'.
    cost_model  : modelo de costes
    scenario    : "central" | "optimistic" | "pessimistic"
    lots        : número de lotes estándar
    be_trigger_r: multiplicador de R para activar BE
    """
    # Determinar entry_time desde el slice (primer bar del trade)
    if len(m1_slice) > 0 and "datetime" in m1_slice.columns:
        entry_time_ts = pd.Timestamp(m1_slice["datetime"].iat[0])
    else:
        entry_time_ts = pd.NaT

    risk = abs(entry_bid - sl_price)
    if risk <= 0:
        sc = getattr(cost_model, scenario)
        return TradeResult(
            exit_reason="TIME_EXIT",
            entry_time=entry_time_ts,
            exit_time=entry_time_ts,
            exit_bid=entry_bid,
            gross_pips=0.0,
            net_pips=-sc.total_cost_pips(lots),
            net_usd=-sc.total_cost_usd(lots),
            resultado=0,
        )

    be_level   = entry_bid + be_trigger_r * risk if direction == "buy" else entry_bid - be_trigger_r * risk
    be_active  = False
    current_sl = sl_price

    sc = getattr(cost_model, scenario)

    if len(m1_slice) == 0:
        return TradeResult(
            exit_reason="TIME_EXIT",
            entry_time=entry_time_ts,
            exit_time=entry_time_ts,
            exit_bid=entry_bid,
            gross_pips=0.0,
            net_pips=-sc.total_cost_pips(lots),
            net_usd=-sc.total_cost_usd(lots),
            resultado=0,
        )

    highs = m1_slice["high"].values
    lows  = m1_slice["low"].values
    closes = m1_slice["close"].values
    dts   = m1_slice["datetime"].values if "datetime" in m1_slice.columns else m1_slice.index.values

    for j in range(len(m1_slice)):
        bar_high = highs[j]
        bar_low  = lows[j]
        bar_ts   = pd.Timestamp(dts[j])

        # Activar BE
        if not be_active:
            if direction == "buy"  and bar_high >= be_level:
                be_active  = True
                current_sl = entry_bid
            elif direction == "sell" and bar_low <= be_level:
                be_active  = True
                current_sl = entry_bid

        if direction == "buy":
            sl_hit = bar_low  <= current_sl
            tp_hit = bar_high >= tp_price
        else:
            sl_hit = bar_high >= current_sl
            tp_hit = bar_low  <= tp_price

        # AMBIGUOUS
        if tp_hit and sl_hit:
            gross_pips = 0.0
            net_pips   = gross_pips - sc.total_cost_pips(lots)
            return TradeResult(
                exit_reason="AMBIGUOUS",
                entry_time=entry_time_ts,
                exit_time=bar_ts,
                exit_bid=entry_bid,
                gross_pips=gross_pips,
                net_pips=net_pips,
                net_usd=CostModel.pnl_usd(net_pips, lots),
                resultado=0,
            )

        if tp_hit:
            entry_eff  = sc.entry_price(entry_bid, direction)
            gross_pips = CostModel.pnl_pips(entry_eff, tp_price, direction)
            net_pips   = cost_model.net_pnl_pips(entry_eff, tp_price, direction, lots, scenario)
            return TradeResult(
                exit_reason="TP",
                entry_time=entry_time_ts,
                exit_time=bar_ts,
                exit_bid=tp_price,
                gross_pips=gross_pips,
                net_pips=net_pips,
                net_usd=CostModel.pnl_usd(net_pips, lots),
                resultado=1 if net_pips > 0 else 0,
            )

        if sl_hit:
            reason     = "BE" if be_active else "SL"
            entry_eff  = sc.entry_price(entry_bid, direction)
            gross_pips = CostModel.pnl_pips(entry_eff, current_sl, direction)
            net_pips   = cost_model.net_pnl_pips(entry_eff, current_sl, direction, lots, scenario)
            return TradeResult(
                exit_reason=reason,
                entry_time=entry_time_ts,
                exit_time=bar_ts,
                exit_bid=current_sl,
                gross_pips=gross_pips,
                net_pips=net_pips,
                net_usd=CostModel.pnl_usd(net_pips, lots),
                resultado=1 if net_pips > 0 else 0,
            )

    # TIME_EXIT: cerramos al close de la última barra disponible en el slice
    last_idx   = len(m1_slice) - 1
    exit_bid   = closes[last_idx]
    exit_ts    = pd.Timestamp(dts[last_idx])
    entry_eff  = sc.entry_price(entry_bid, direction)
    gross_pips = CostModel.pnl_pips(entry_eff, exit_bid, direction)
    net_pips   = cost_model.net_pnl_pips(entry_eff, exit_bid, direction, lots, scenario)
    return TradeResult(
        exit_reason="TIME_EXIT",
        entry_time=entry_time_ts,
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
    max_duration: pd.Timedelta = pd.Timedelta(minutes=MAX_HORIZON_MINUTES),
) -> pd.DataFrame:
    """
    Extrae la ventana M1 para un trade dado su tiempo de entrada.

    El horizonte es temporal: incluye barras cuyo open está en
    [entry_time, entry_time + max_duration). Para barras M1, la última barra
    incluida tiene open = entry_time + 89 min (close = entry_time + 90 min).

    Si hay huecos de datos (mercado cerrado, festivos), se devuelven solo las
    barras que existen dentro del intervalo. Un slice vacío indica que no hay
    datos M1 para el horizonte del trade.

    m1 debe tener columna 'datetime' (UTC, no como índice).
    """
    if "datetime" not in m1.columns:
        raise ValueError("m1 debe tener columna 'datetime'")
    end_time = entry_time + max_duration
    mask = (m1["datetime"] >= entry_time) & (m1["datetime"] < end_time)
    return m1[mask].reset_index(drop=True)
