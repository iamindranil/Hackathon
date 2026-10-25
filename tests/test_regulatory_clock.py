"""
Unit tests for Deterministic Regulatory Clock Engine
"""

from datetime import date
from backend.models.dispute import RegulatoryRegime, ClockUrgency
from backend.engine.regulatory_clock import RegulatoryClockEngine


def test_us_federal_holidays():
    holidays_2026 = RegulatoryClockEngine.get_us_federal_holidays(2026)
    
    # 2026 Thanksgiving is Nov 26, 2026 (4th Thursday)
    assert date(2026, 11, 26) in holidays_2026, "Thanksgiving 2026 must be present"
    
    # Christmas 2026 is Friday, Dec 25, 2026
    assert date(2026, 12, 25) in holidays_2026, "Christmas 2026 must be present"
    
    # Juneteenth 2026 is Friday, June 19, 2026
    assert date(2026, 6, 19) in holidays_2026, "Juneteenth 2026 must be present"
    
    # Independence Day July 4, 2026 is Saturday -> observed Friday July 3
    assert date(2026, 7, 3) in holidays_2026, "Independence Day observed Friday must be present"
    print("[OK] US Federal Holidays test passed.")


def test_reg_e_clock_standard():
    # Intake on Monday, Nov 16, 2026
    # 10 business days must skip weekends (Nov 21-22, Nov 28-29) AND Thanksgiving (Nov 26)
    intake = date(2026, 11, 16)
    clock = RegulatoryClockEngine.compute_clock(
        regime=RegulatoryRegime.REG_E_DEBIT,
        intake_date=intake,
        is_new_account=False,
        is_foreign_or_pos=False,
        has_provisional_credit=True,
        current_date=date(2026, 11, 16)
    )

    # Day 1: Tue 17
    # Day 2: Wed 18
    # Day 3: Thu 19
    # Day 4: Fri 20
    # Sat 21, Sun 22 (skip)
    # Day 5: Mon 23
    # Day 6: Tue 24
    # Day 7: Wed 25
    # Thu 26 (Thanksgiving holiday - skip!)
    # Day 8: Fri 27
    # Sat 28, Sun 29 (skip)
    # Day 9: Mon 30
    # Day 10: Tue Dec 1, 2026
    expected_prov_credit = date(2026, 12, 1)
    assert clock.provisional_credit_deadline == expected_prov_credit, (
        f"Expected {expected_prov_credit}, got {clock.provisional_credit_deadline}"
    )

    # Standard investigation deadline: 45 calendar days from Nov 16 = Dec 31, 2026
    expected_final = date(2026, 12, 31)
    assert clock.investigation_deadline == expected_final, (
        f"Expected {expected_final}, got {clock.investigation_deadline}"
    )
    print("[OK] Reg E Standard Clock calculation (with Thanksgiving holiday skip) passed.")


def test_reg_e_clock_extended_pos_foreign():
    intake = date(2026, 11, 16)
    clock = RegulatoryClockEngine.compute_clock(
        regime=RegulatoryRegime.REG_E_DEBIT,
        intake_date=intake,
        is_new_account=True,      # New account gets 90 days
        is_foreign_or_pos=False,
        has_provisional_credit=True,
        current_date=date(2026, 11, 16)
    )
    # 90 calendar days from Nov 16, 2026 = Feb 14, 2027
    expected_final = date(2027, 2, 14)
    assert clock.investigation_deadline == expected_final, (
        f"Expected {expected_final}, got {clock.investigation_deadline}"
    )
    print("[OK] Reg E Extended 90-day Clock test passed.")


def test_reg_z_clock():
    intake = date(2026, 10, 1)
    clock = RegulatoryClockEngine.compute_clock(
        regime=RegulatoryRegime.REG_Z_CREDIT,
        intake_date=intake,
        current_date=date(2026, 10, 1)
    )
    # 30-day written acknowledgment: Oct 31, 2026
    assert clock.acknowledgment_deadline == date(2026, 10, 31)
    # 90-day resolution: Dec 30, 2026
    assert clock.investigation_deadline == date(2026, 12, 30)
    print("[OK] Reg Z Clock test passed.")


def test_eu_psr_clock():
    intake = date(2026, 10, 23)  # Friday
    clock = RegulatoryClockEngine.compute_clock(
        regime=RegulatoryRegime.EU_PSR_PSD2,
        intake_date=intake,
        current_date=date(2026, 10, 23)
    )
    # Next business day after Friday is Monday Oct 26
    assert clock.provisional_credit_deadline == date(2026, 10, 26)
    # 15 business days fraud hold
    assert clock.business_days_applied == 15
    print("[OK] EU PSR Clock test passed.")


def test_urgency_statuses():
    intake = date(2026, 10, 1)
    # Evaluated 9 days after intake -> 1 business day left for provisional credit
    clock_urgent = RegulatoryClockEngine.compute_clock(
        regime=RegulatoryRegime.REG_E_DEBIT,
        intake_date=intake,
        current_date=date(2026, 10, 14)
    )
    assert clock_urgent.urgency in (ClockUrgency.CRITICAL, ClockUrgency.EXPEDITED)
    print("[OK] Clock Urgency test passed.")


if __name__ == "__main__":
    test_us_federal_holidays()
    test_reg_e_clock_standard()
    test_reg_e_clock_extended_pos_foreign()
    test_reg_z_clock()
    test_eu_psr_clock()
    test_urgency_statuses()
    print("\nALL REGULATORY CLOCK TESTS PASSED SUCCESSFULLY!")
