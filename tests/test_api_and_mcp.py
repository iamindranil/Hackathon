"""
Tests for FastAPI Backend and Pega MCP Protocol Bridge
"""

from fastapi.testclient import TestClient
from backend.api.app import app

client = TestClient(app)


def test_health_check():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["active_cases"] >= 4
    print("[OK] API health check passed.")


def test_get_scenarios():
    res = client.get("/api/scenarios")
    assert res.status_code == 200
    data = res.json()
    assert len(data["scenarios"]) == 4
    print("[OK] Scenarios retrieval passed.")


def test_investigate_and_approve():
    # Submit claim
    payload = {
        "claim_id": "TEST-CLM-99",
        "cardholder_id": "CUST-1049",
        "raw_text": "ATM withdrawal was not made by me (TX-88201)",
        "transaction_id": "TX-88201",
    }
    res = client.post("/api/disputes/investigate", json=payload)
    assert res.status_code == 200
    case = res.json()
    assert case["case_id"] == "CASE-TEST-CLM-99"
    assert case["state"] == "PENDING_ANALYST_APPROVAL"
    assert case["clock"]["regime"] == "REG_E_DEBIT"

    # Analyst Approval
    appr_payload = {
        "analyst_id": "ANALYST-TEST",
        "analyst_notes": "Reviewed and approved provisional credit.",
    }
    appr_res = client.post(f"/api/disputes/cases/{case['case_id']}/approve", json=appr_payload)
    assert appr_res.status_code == 200
    appr_case = appr_res.json()
    assert appr_case["state"] == "RESOLVED_APPROVED"
    assert appr_case["analyst_approved"] is True
    print("[OK] Investigate and Analyst Approval endpoints passed.")


def test_pega_mcp_bridge():
    # 1. MCP Clock tool
    mcp_clock_payload = {
        "tool_name": "compute_statutory_clock",
        "arguments": {
            "regime": "REG_E_DEBIT",
            "intake_date": "2026-10-25"
        }
    }
    res1 = client.post("/api/pega/mcp/invoke", json=mcp_clock_payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "success"
    assert "provisional_credit_deadline" in res1.json()["result"]

    # 2. MCP Case Evaluation tool
    mcp_case_payload = {
        "tool_name": "evaluate_dispute_case",
        "arguments": {
            "pega_case_id": "PEGA-CASE-9901",
            "cardholder_id": "CUST-7201",
            "transaction_id": "TX-77312",
            "claim_text": "Nordstrom damaged coat return not refunded"
        }
    }
    res2 = client.post("/api/pega/mcp/invoke", json=mcp_case_payload)
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"
    assert res2.json()["result"]["adjudication"]["proposed_decision"] == "CHARGEBACK_INITIATED"
    print("[OK] Pega Smart Dispute MCP Tool Bridge passed.")


if __name__ == "__main__":
    test_health_check()
    test_get_scenarios()
    test_investigate_and_approve()
    test_pega_mcp_bridge()
    print("\nALL FASTAPI AND PEGA MCP TESTS PASSED SUCCESSFULLY!")
