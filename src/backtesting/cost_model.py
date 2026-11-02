"""
cost_model.py — Modelo de costes de transacción para EUR/USD (FTMO-like)

Supuestos V1:
  - Solo datos BID históricos (Dukascopy). ASK se aproxima: ASK = BID + spread.
  - BUY: entrada a ASK, salida a BID.
  - SELL: entrada a BID, salida a ASK.
  - Comisión: por defecto round-turn (PD-021b PENDING, configurable).
  - Swap overnight: no implementado en V1 (operaciones <90 min).

Ver docs/roadmap_v2.md (V2-007, V2-008) para lo que se pospone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PIP = 0.0001          # 1 pip EUR/USD
CONTRACT_SIZE = 100_000  # unidades base por lote estándar
PIP_VALUE_PER_LOT = PIP * CONTRACT_SIZE  # 10 USD por pip por lote


@dataclass(frozen=True)
class CostScenario:
    """Escenario único de costes para una operación."""

    spread_pips: float = 0.2
    slippage_pips: float = 0.0
    commission_usd_per_lot: float = 5.0
    commission_mode: Literal["round_turn", "per_side"] = "round_turn"

    @property
    def spread_price(self) -> float:
        return self.spread_pips * PIP

    @property
    def slippage_price(self) -> float:
        return self.slippage_pips * PIP

    def entry_price(
        self,
        bid: float,
        direction: Literal["buy", "sell"],
    ) -> float:
        """Precio de entrada efectivo desde el BID de apertura de la siguiente vela."""
        if direction == "buy":
            return bid + self.spread_price + self.slippage_price
        return bid - self.slippage_price

    def exit_price(
        self,
        bid: float,
        direction: Literal["buy", "sell"],
    ) -> float:
        """Precio de salida efectivo al cerrar la posición."""
        if direction == "buy":
            return bid - self.slippage_price
        return bid + self.spread_price + self.slippage_price

    def total_cost_pips(self, lots: float = 1.0) -> float:
        """Coste total en pips (spread + slippage + comisión equivalente en pips)."""
        commission_pips = self._commission_pips(lots)
        return self.spread_pips + 2 * self.slippage_pips + commission_pips

    def total_cost_usd(self, lots: float = 1.0) -> float:
        """Coste total en USD para `lots` lotes estándar."""
        spread_usd = self.spread_pips * PIP_VALUE_PER_LOT * lots
        slip_usd = 2 * self.slippage_pips * PIP_VALUE_PER_LOT * lots
        comm_usd = self._commission_usd(lots)
        return spread_usd + slip_usd + comm_usd

    def _commission_usd(self, lots: float) -> float:
        if self.commission_mode == "round_turn":
            return self.commission_usd_per_lot * lots
        return 2 * self.commission_usd_per_lot * lots  # entrada + salida

    def _commission_pips(self, lots: float) -> float:
        return self._commission_usd(lots) / (PIP_VALUE_PER_LOT * lots)


@dataclass
class CostModel:
    """Contenedor de escenarios y calculador de P&L neto.

    Usage::

        model = CostModel.central()
        entry = model.central.entry_price(bid=1.08000, direction="buy")
        exit_p = model.central.exit_price(bid=1.08400, direction="buy")
        pnl = model.pnl_pips(entry, exit_p, direction="buy")
        net_pnl = pnl - model.central.total_cost_pips(lots=1.0)
    """

    central: CostScenario = field(
        default_factory=lambda: CostScenario(0.2, 0.0, 5.0, "round_turn")
    )
    optimistic: CostScenario = field(
        default_factory=lambda: CostScenario(0.1, 0.0, 5.0, "round_turn")
    )
    pessimistic: CostScenario = field(
        default_factory=lambda: CostScenario(0.5, 0.2, 5.0, "round_turn")
    )

    @classmethod
    def make_default(cls) -> "CostModel":
        """Devuelve el modelo con todos los escenarios en sus valores por defecto."""
        return cls()

    @staticmethod
    def pnl_pips(entry: float, exit_price: float, direction: Literal["buy", "sell"]) -> float:
        """P&L bruto en pips (sin costes)."""
        raw = (exit_price - entry) if direction == "buy" else (entry - exit_price)
        return raw / PIP

    @staticmethod
    def pnl_usd(pnl_pips: float, lots: float = 1.0) -> float:
        """P&L en USD dado el número de pips y lotes."""
        return pnl_pips * PIP_VALUE_PER_LOT * lots

    def net_pnl_pips(
        self,
        entry: float,
        exit_price: float,
        direction: Literal["buy", "sell"],
        lots: float = 1.0,
        scenario: Literal["central", "optimistic", "pessimistic"] = "central",
    ) -> float:
        """P&L neto en pips (bruto menos todos los costes)."""
        sc = getattr(self, scenario)
        gross = self.pnl_pips(entry, exit_price, direction)
        return gross - sc.total_cost_pips(lots)

    def net_pnl_usd(
        self,
        entry: float,
        exit_price: float,
        direction: Literal["buy", "sell"],
        lots: float = 1.0,
        scenario: Literal["central", "optimistic", "pessimistic"] = "central",
    ) -> float:
        """P&L neto en USD."""
        net_pips = self.net_pnl_pips(entry, exit_price, direction, lots, scenario)
        return self.pnl_usd(net_pips, lots)


# ── Instancia global con escenario central de referencia ──────────────────────
DEFAULT_COST_MODEL = CostModel()
