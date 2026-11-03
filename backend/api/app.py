"""
FastAPI Backend Application & Pega MCP Protocol Bridge
Provides REST endpoints for dispute claim intake, full pipeline execution,
analyst approval/override, case queries, and Pega Smart Dispute integration tools.
"""

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os

from backend.models.dispute import (
    DisputeCase,
    DisputeCaseState,
    DecisionOutcome,
    ChannelType,
    RegulatoryRegime,
)
from backend.agents.pipeline import SequentialDisputePipeline
from backend.neuro.neuro_engine import NeuroDisputeEngine
from backend.engine.regulatory_clock import RegulatoryClockEngine
from backend.tools.evidence_tools import EvidenceTools
from backend.tools.enterprise_data import MOCK_TRANSACTIONS_DB

app = FastAPI(
    title="Card & Payment Dispute Investigation Agent API",
    description="Regulatory-clock-aware multi-agent investigation system compliant with US Reg E, Reg Z, and EU PSR.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory Case Store for the session
ACTIVE_CASES_DB: Dict[str, DisputeCase] = {}


# --- Request & Response Payloads ---

class IngestClaimRequest(BaseModel):
    claim_id: Optional[str] = None
    cardholder_id: str = "CUST-1049"
    raw_text: str
    channel: ChannelType = ChannelType.MOBILE_APP_CHAT
    transaction_id: Optional[str] = None
    attachment_paths: List[str] = Field(default_factory=list)
    engine: Optional[str] = "native"  # "native" or "neuro" (Cognizant Neuro Studio)


class AnalystApprovalRequest(BaseModel):
    analyst_id: str = "ANALYST-DEMO-01"
    analyst_notes: str = "Verified evidence items against core ledger and approved."
    override_decision: Optional[DecisionOutcome] = None


class PegaMCPRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]


# --- Seed Pre-Configured Demo Scenarios ---

DEMO_SCENARIOS = [
    {
        "id": "scenario-1",
        "title": "US Reg E: Unauthorized ATM Skim in Miami",
        "regime": "REG_E_DEBIT",
        "cardholder_id": "CUST-1049",
        "cardholder_name": "Sarah Jenkins",
        "transaction_id": "TX-88201",
        "amount": "$420.00",
        "claim_text": "I noticed an unauthorized ATM cash withdrawal of $420 at SunTrust in Miami Beach (TX-88201) on my checking account. I reside in Seattle and was asleep at home. My physical card is still with me.",
        "expected_outcome": "10-Day Provisional Credit & Investigation Approval",
        "key_evidence": "Impossible travel (2,730 miles in 1 min), Mag-stripe fallback read at ATM, simultaneous home mobile app session."
    },
    {
        "id": "scenario-2",
        "title": "US Reg E: Friendly Fraud (Biometric FaceID on Home WiFi)",
        "regime": "REG_E_DEBIT",
        "cardholder_id": "CUST-3819",
        "cardholder_name": "Michael Chang",
        "transaction_id": "TX-90184",
        "amount": "$1,250.00",
        "claim_text": "I did not authorize this $1,250 digital purchase from PlayStation Network (TX-90184). My bank must refund me immediately under Reg E.",
        "expected_outcome": "Defensible Denial with Granular Fed-Compliant Factual Finding (No Boilerplate)",
        "key_evidence": "3DS 2.2 FIDO FaceID verified on cardholder's primary iPhone 15 Pro, home ISP network match, 18.5 hours active console gameplay."
    },
    {
        "id": "scenario-3",
        "title": "US Reg Z: Merchant Billing Error (Damaged Return)",
        "regime": "REG_Z_CREDIT",
        "cardholder_id": "CUST-7201",
        "cardholder_name": "Elena Rostova",
        "transaction_id": "TX-77312",
        "amount": "$899.00",
        "claim_text": "I bought a coat from Nordstrom (TX-77312) on my credit card. FedEx tracking confirms the shipment was damaged in transit and returned to Nordstrom on Oct 2. The merchant failed to issue a refund despite repeated emails.",
        "expected_outcome": "Chargeback Reason Code 4855 & Disputed Balance Collection Withheld",
        "key_evidence": "FedEx scan history confirms package returned damaged, cardholder written merchant communication verified."
    },
    {
        "id": "scenario-4",
        "title": "EU PSR: Bank Impersonation / Social Engineering Scam",
        "regime": "EU_PSR_PSD2",
        "cardholder_id": "CUST-5512",
        "cardholder_name": "David Müller",
        "transaction_id": "TX-66105",
        "amount": "€3,500.00",
        "claim_text": "A caller with the bank's official fraud phone number called me stating my account was compromised and guided me to transfer €3,500 to a secure holding account (TX-66105). It turned out to be an impersonation scam.",
        "expected_outcome": "Mandatory Full Reimbursement by D+1 under EU Payment Services Regulation",
        "key_evidence": "Telecom CLI spoofing confirmed, destination account flagged as neo-bank money mule."
    }
]


# Initialize cases on demand to ensure instant 0.5s server startup
_initialized = False

def ensure_demo_cases():
    global _initialized
    if not _initialized:
        # Pre-populate all 4 canonical scenarios via Cognizant Neuro Engine
        for idx, sc in enumerate(DEMO_SCENARIOS):
            case = NeuroDisputeEngine.run_neuro_investigation(
                claim_id=f"CLM-{idx + 1}",
                cardholder_id=sc["cardholder_id"],
                raw_text=sc["claim_text"],
                transaction_id=sc["transaction_id"],
            )
            ACTIVE_CASES_DB[case.case_id] = case
        _initialized = True


# --- API Routes ---

@app.get("/api/health")
def health_check():
    ensure_demo_cases()
    from backend.engine.gemini_client import GeminiClient
    ai_status = "LIVE_GEMINI" if GeminiClient.is_ai_live() else "LOCAL_HYBRID"
    return {
        "status": "healthy",
        "service": "Card & Payment Dispute Investigation Agent",
        "ai_engine": ai_status,
        "neuro_studio": "CONNECTED",
        "active_cases": len(ACTIVE_CASES_DB),
    }


@app.get("/api/neuro/network")
def get_neuro_network_topology():
    """
    Returns Cognizant Neuro® San HOCON network specification and manifest info.
    """
    hocon_file = os.path.join(os.path.dirname(__file__), "..", "neuro", "resolv_network.hocon")
    manifest_file = os.path.join(os.path.dirname(__file__), "..", "neuro", "manifest.hocon")
    
    hocon_content = ""
    manifest_content = ""
    if os.path.exists(hocon_file):
        with open(hocon_file, "r", encoding="utf-8") as f:
            hocon_content = f.read()
    if os.path.exists(manifest_file):
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_content = f.read()

    return {
        "network_id": NeuroDisputeEngine.NETWORK_ID,
        "front_man_agent": NeuroDisputeEngine.ENTRY_AGENT,
        "status": "ACTIVE",
        "hocon_specification": hocon_content,
        "manifest": manifest_content,
    }


@app.get("/api/scenarios")
def get_scenarios():
    """Returns preset canonical scenarios for one-click testing."""
    return {"scenarios": DEMO_SCENARIOS}


@app.get("/api/disputes/cases")
def list_cases():
    """Returns list of active dispute cases."""
    ensure_demo_cases()
    return {"cases": list(ACTIVE_CASES_DB.values())}


@app.get("/api/disputes/cases/{case_id}")
def get_case(case_id: str):
    """Retrieves full case state and audit trail."""
    case = ACTIVE_CASES_DB.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return case


@app.post("/api/disputes/investigate")
def run_investigation_endpoint(req: IngestClaimRequest):
    """
    Submits a dispute claim to the 5-stage sequential agent pipeline or Cognizant Neuro Engine.
    """
    claim_id = req.claim_id or f"CLM-{len(ACTIVE_CASES_DB) + 101}"
    if req.engine == "neuro":
        case = NeuroDisputeEngine.run_neuro_investigation(
            claim_id=claim_id,
            cardholder_id=req.cardholder_id,
            raw_text=req.raw_text,
            channel=req.channel,
            transaction_id=req.transaction_id,
            attachment_paths=req.attachment_paths,
        )
    else:
        case = SequentialDisputePipeline.run_investigation(
            claim_id=claim_id,
            cardholder_id=req.cardholder_id,
            raw_text=req.raw_text,
            channel=req.channel,
            transaction_id=req.transaction_id,
            attachment_paths=req.attachment_paths,
        )
    ACTIVE_CASES_DB[case.case_id] = case
    return case


@app.post("/api/disputes/cases/{case_id}/approve")
def approve_case_endpoint(case_id: str, req: AnalystApprovalRequest):
    """
    Human-in-the-Loop Analyst execution gate: approves or overrides decision
    and dispatches simulated core banking ledger posting.
    """
    case = ACTIVE_CASES_DB.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    updated_case = SequentialDisputePipeline.approve_and_execute(
        case=case,
        analyst_id=req.analyst_id,
        analyst_notes=req.analyst_notes,
        override_decision=req.override_decision,
    )
    ACTIVE_CASES_DB[case_id] = updated_case
    return updated_case


# --- Pega Smart Dispute MCP Tool Bridge ---

@app.post("/api/pega/mcp/invoke")
def pega_mcp_bridge(req: PegaMCPRequest):
    """
    Model Context Protocol (MCP) tool invocation endpoint for Pega Smart Dispute.
    Allows Pega case lifecycles to call investigation agents as pluggable MCP tools.
    """
    tool = req.tool_name
    args = req.arguments

    if tool == "compute_statutory_clock":
        regime = RegulatoryRegime(args.get("regime", "REG_E_DEBIT"))
        from datetime import date
        intake = date.fromisoformat(args.get("intake_date", str(date.today())))
        clock = RegulatoryClockEngine.compute_clock(
            regime=regime,
            intake_date=intake,
            is_new_account=args.get("is_new_account", False),
            is_foreign_or_pos=args.get("is_foreign_or_pos", False),
        )
        return {"status": "success", "result": clock.dict()}

    elif tool == "harvest_evidence_dossier":
        txn_id = args.get("transaction_id", "TX-88201")
        cardholder_id = args.get("cardholder_id", "CUST-1049")
        
        # Build ephemeral claim
        from backend.agents.intake_agent import IntakeAgent
        claim = IntakeAgent.process_claim(
            claim_id="MCP-EVI-TEMP",
            cardholder_id=cardholder_id,
            raw_text=f"Dispute for {txn_id}",
            known_transaction_id=txn_id,
        )
        from backend.agents.evidence_agent import EvidenceAgent
        dossier = EvidenceAgent.harvest_dossier(claim=claim)
        return {"status": "success", "result": dossier.dict()}

    elif tool == "evaluate_dispute_case":
        raw_text = args.get("claim_text", "")
        txn_id = args.get("transaction_id")
        cardholder_id = args.get("cardholder_id", "CUST-1049")
        claim_id = args.get("pega_case_id", f"PEGA-{len(ACTIVE_CASES_DB)+1}")
        case = NeuroDisputeEngine.run_neuro_investigation(
            claim_id=claim_id,
            cardholder_id=cardholder_id,
            raw_text=raw_text,
            transaction_id=txn_id,
        )
        ACTIVE_CASES_DB[case.case_id] = case
        return {"status": "success", "result": case.dict()}

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tool '{tool}'. Supported MCP tools: 'compute_statutory_clock', 'harvest_evidence_dossier', 'evaluate_dispute_case'."
        )


# Mount static frontend directory
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
