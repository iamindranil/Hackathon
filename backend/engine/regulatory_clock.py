"""
Deterministic Regulatory Clock Engine
Calculates statutory deadlines and live SLA urgency for US Regulation E,
US Regulation Z, and EU Payment Services Regulation (PSR / PSD2).
"""

from datetime import date, timedelta
from typing import Set, Optional
from backend.models.dispute import RegulatoryRegime, RegulatoryClock, ClockUrgency


class RegulatoryClockEngine:
    """
    Non-probabilistic statutory clock calculator compliant with:
    - US 12 CFR § 1005.11 (Regulation E - Electronic Fund Transfers)
    - US 12 CFR § 1026.13 (Regulation Z - Truth in Lending Billing Errors)
    - EU PSD2 / PSR 2026 (Payment Services Regulation)
    """

    @staticmethod
    def get_us_federal_holidays(year: int) -> Set[date]:
        """
        Computes standard US Federal Reserve Bank holidays for a given year.
        If a holiday falls on Sunday, the following Monday is observed.
        If a holiday falls on Saturday, preceding Friday is observed by banks.
        """
        holidays = set()

        # Fixed-date holidays
        fixed = [
            (1, 1),    # New Year's Day
            (6, 19),   # Juneteenth National Independence Day
            (7, 4),    # Independence Day
            (11, 11),  # Veterans Day
            (12, 25),  # Christmas Day
        ]

        for month, day in fixed:
            hol = date(year, month, day)
            if hol.weekday() == 6:  # Sunday -> Monday
                holidays.add(hol + timedelta(days=1))
            elif hol.weekday() == 5:  # Saturday -> Friday
                holidays.add(hol - timedelta(days=1))
            else:
                holidays.add(hol)

        # Floating holidays
        def nth_weekday(y, m, weekday, n):
            # n: 1-indexed (1st, 2nd, etc.)
            d = date(y, m, 1)
            count = 0
            while True:
                if d.weekday() == weekday:
                    count += 1
                    if count == n:
                        return d
                d += timedelta(days=1)

        def last_weekday(y, m, weekday):
            d = date(y, m + 1, 1) - timedelta(days=1) if m < 12 else date(y, 12, 31)
            while d.weekday() != weekday:
                d -= timedelta(days=1)
            return d

        # Martin Luther King Jr. Day: 3rd Monday in Jan
        holidays.add(nth_weekday(year, 1, 0, 3))
        # Washington's Birthday (Presidents' Day): 3rd Monday in Feb
        holidays.add(nth_weekday(year, 2, 0, 3))
        # Memorial Day: Last Monday in May
        holidays.add(last_weekday(year, 5, 0))
        # Labor Day: 1st Monday in Sept
        holidays.add(nth_weekday(year, 9, 0, 1))
        # Columbus Day: 2nd Monday in Oct
        holidays.add(nth_weekday(year, 10, 0, 2))
        # Thanksgiving Day: 4th Thursday in Nov
        holidays.add(nth_weekday(year, 11, 3, 4))

        return holidays

    @classmethod
    def is_business_day(cls, d: date, regime: RegulatoryRegime) -> bool:
        """Determines if a date is a standard banking business day."""
        # Weekend check
        if d.weekday() in (5, 6):
            return False
        
        # Check Fed bank holidays for US regimes
        holidays = cls.get_us_federal_holidays(d.year)
        if d in holidays:
            return False
            
        return True

    @classmethod
    def add_business_days(cls, start: date, business_days: int, regime: RegulatoryRegime) -> date:
        """Adds N banking business days strictly skipping weekends & bank holidays."""
        cur = start
        added = 0
        while added < business_days:
            cur += timedelta(days=1)
            if cls.is_business_day(cur, regime):
                added += 1
        return cur

    @classmethod
    def count_business_days_between(cls, start: date, end: date, regime: RegulatoryRegime) -> int:
        """Counts business days between start (exclusive) and end (inclusive)."""
        if end <= start:
            return 0
        count = 0
        cur = start + timedelta(days=1)
        while cur <= end:
            if cls.is_business_day(cur, regime):
                count += 1
            cur += timedelta(days=1)
        return count

    @classmethod
    def compute_clock(
        cls,
        regime: RegulatoryRegime,
        intake_date: date,
        is_new_account: bool = False,
        is_foreign_or_pos: bool = False,
        has_provisional_credit: bool = True,
        current_date: Optional[date] = None,
    ) -> RegulatoryClock:
        """
        Deterministically derives statutory milestones based on legal regime rules.
        """
        today = current_date or date.today()
        statutory_start_date = intake_date

        if regime == RegulatoryRegime.REG_E_DEBIT:
            # 12 CFR § 1005.11(c)(1): 10 business days for provisional credit or resolution
            prov_credit_deadline = cls.add_business_days(statutory_start_date, 10, regime)
            
            # 12 CFR § 1005.11(c)(2) & (c)(3):
            # If provisional credit is issued, up to 45 calendar days.
            # Extended to 90 calendar days if:
            # - New account (opened within 30 days of notice)
            # - Point-of-sale (POS) debit transaction
            # - Transaction took place outside the United States
            if has_provisional_credit:
                calendar_extension = 90 if (is_new_account or is_foreign_or_pos) else 45
                investigation_deadline = statutory_start_date + timedelta(days=calendar_extension)
            else:
                # Without provisional credit, bank MUST finish in 10 business days
                investigation_deadline = prov_credit_deadline
                
            # 12 CFR § 1005.11(c)(2)(iv): Report results within 3 business days of concluding investigation
            customer_notice_deadline = cls.add_business_days(investigation_deadline, 3, regime)
            
            days_to_prov = (prov_credit_deadline - today).days
            days_to_final = (investigation_deadline - today).days
            
            citation = "12 CFR § 1005.11(c) [US Reg E 10-Day Provisional Credit & 45/90-Day Resolution]"

            # Urgency check (based on the immediate nearest milestone)
            target_days = days_to_prov if days_to_prov >= 0 else days_to_final
            if target_days < 0:
                urgency = ClockUrgency.BREACHED
            elif target_days <= 1:
                urgency = ClockUrgency.CRITICAL
            elif target_days <= 3:
                urgency = ClockUrgency.EXPEDITED
            else:
                urgency = ClockUrgency.NORMAL

            return RegulatoryClock(
                regime=regime,
                intake_date=intake_date,
                statutory_start_date=statutory_start_date,
                acknowledgment_deadline=None,
                provisional_credit_deadline=prov_credit_deadline,
                investigation_deadline=investigation_deadline,
                customer_notice_deadline=customer_notice_deadline,
                days_to_provisional_credit=days_to_prov,
                days_to_final_resolution=days_to_final,
                urgency=urgency,
                statutory_citation=citation,
                business_days_applied=cls.count_business_days_between(statutory_start_date, prov_credit_deadline, regime),
                calendar_days_applied=(investigation_deadline - statutory_start_date).days,
            )

        elif regime == RegulatoryRegime.REG_Z_CREDIT:
            # 12 CFR § 1026.13(c)(1): Written acknowledgment within 30 calendar days
            ack_deadline = statutory_start_date + timedelta(days=30)
            
            # 12 CFR § 1026.13(c)(2): Resolution within 2 complete billing cycles, but not later than 90 days
            investigation_deadline = statutory_start_date + timedelta(days=90)
            customer_notice_deadline = investigation_deadline
            
            days_to_final = (investigation_deadline - today).days
            citation = "12 CFR § 1026.13(c) [US Reg Z 30-Day Written Ack & 2-Billing-Cycle / 90-Day Resolution]"

            if days_to_final < 0:
                urgency = ClockUrgency.BREACHED
            elif days_to_final <= 3:
                urgency = ClockUrgency.CRITICAL
            elif days_to_final <= 7:
                urgency = ClockUrgency.EXPEDITED
            else:
                urgency = ClockUrgency.NORMAL

            return RegulatoryClock(
                regime=regime,
                intake_date=intake_date,
                statutory_start_date=statutory_start_date,
                acknowledgment_deadline=ack_deadline,
                provisional_credit_deadline=None,
                investigation_deadline=investigation_deadline,
                customer_notice_deadline=customer_notice_deadline,
                days_to_provisional_credit=None,
                days_to_final_resolution=days_to_final,
                urgency=urgency,
                statutory_citation=citation,
                business_days_applied=cls.count_business_days_between(statutory_start_date, ack_deadline, regime),
                calendar_days_applied=90,
            )

        elif regime == RegulatoryRegime.EU_PSR_PSD2:
            # EU PSD2 Art. 73 & new Payment Services Regulation:
            # Immediate refund: by end of next business day (D+1)
            immediate_refund_deadline = cls.add_business_days(statutory_start_date, 1, regime)
            
            # If objectively justified suspicion of fraud, bank may hold for max 15 business days
            investigation_deadline = cls.add_business_days(statutory_start_date, 15, regime)
            customer_notice_deadline = immediate_refund_deadline
            
            days_to_prov = (immediate_refund_deadline - today).days
            days_to_final = (investigation_deadline - today).days
            citation = "EU PSD2 Art. 73 / PSR Recitals [Immediate D+1 Refund or Max 15 Business Days Fraud Suspicion Hold]"

            if days_to_prov < 0:
                urgency = ClockUrgency.BREACHED
            elif days_to_prov == 0:
                urgency = ClockUrgency.CRITICAL
            elif days_to_prov <= 2:
                urgency = ClockUrgency.EXPEDITED
            else:
                urgency = ClockUrgency.NORMAL

            return RegulatoryClock(
                regime=regime,
                intake_date=intake_date,
                statutory_start_date=statutory_start_date,
                acknowledgment_deadline=None,
                provisional_credit_deadline=immediate_refund_deadline,
                investigation_deadline=investigation_deadline,
                customer_notice_deadline=customer_notice_deadline,
                days_to_provisional_credit=days_to_prov,
                days_to_final_resolution=days_to_final,
                urgency=urgency,
                statutory_citation=citation,
                business_days_applied=15,
                calendar_days_applied=(investigation_deadline - statutory_start_date).days,
            )

        raise ValueError(f"Unsupported regulatory regime: {regime}")
