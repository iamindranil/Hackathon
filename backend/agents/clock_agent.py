"""
Agent 2: Regulatory Clock Sentinel
Initializes the deterministic statutory clock for the claim.
Calculates provisional credit deadlines, investigation deadlines,
written notification limits, and live SLA urgency.
"""

from datetime import date
from typing import Optional
from backend.models.dispute import DisputeClaim, RegulatoryClock, RegulatoryRegime
from backend.engine.regulatory_clock import RegulatoryClockEngine


class ClockAgent:
    """
    Deterministic Regulatory Clock Agent.
    Zero hallucination - enforces federal banking calendar calculations.
    """

    @classmethod
    def initialize_clock(
        cls,
        claim: DisputeClaim,
        regime: RegulatoryRegime,
        evaluation_date: Optional[date] = None,
    ) -> RegulatoryClock:
        """
        Derives regulatory clock based on claim transaction parameters.
        """
        intake_date = claim.intake_timestamp.date()
        today = evaluation_date or date.today()

        txn = claim.transactions[0] if claim.transactions else None
        is_new_account = txn.is_new_account if txn else False
        is_foreign_or_pos = txn.is_foreign_or_pos if txn else False

        clock = RegulatoryClockEngine.compute_clock(
            regime=regime,
            intake_date=intake_date,
            is_new_account=is_new_account,
            is_foreign_or_pos=is_foreign_or_pos,
            has_provisional_credit=True,
            current_date=today,
        )

        return clock
