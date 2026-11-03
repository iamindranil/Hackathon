/**
 * RESOLV.AI - Frontend Controller
 * Connects UI with FastAPI backend and live Regulatory Clock Engine.
 */

let currentCase = null;
let scenarios = [];
let countdownInterval = null;
let stepAnimationTimer = null;

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  setupEventListeners();
  await checkAiStatus();
  await loadScenarios();
});

// --- AI Status Check ---
async function checkAiStatus() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const statusText = document.getElementById("aiStatusText");
    const dot = document.getElementById("aiStatusDot");
    if (data.ai_engine === "LIVE_GEMINI") {
      statusText.innerHTML = `GEMINI ENGINE: <strong style="color: #4ade80;">LIVE AI (.ENV)</strong>`;
      dot.className = "status-dot pulse-green";
    } else {
      statusText.innerHTML = `GEMINI ENGINE: <strong>LOCAL HYBRID</strong>`;
      dot.className = "status-dot pulse-purple";
    }
  } catch (err) {
    console.error("Health check error:", err);
  }
}

// --- Tab Controller ---
function setupTabs() {
  const tabAfterBtn = document.getElementById("tabAfterBtn");
  const tabBeforeBtn = document.getElementById("tabBeforeBtn");
  const tabAfterContent = document.getElementById("tabAfterContent");
  const tabBeforeContent = document.getElementById("tabBeforeContent");

  tabAfterBtn.addEventListener("click", () => {
    tabAfterBtn.classList.add("active");
    tabBeforeBtn.classList.remove("active");
    tabAfterContent.classList.add("active");
    tabBeforeContent.classList.remove("active");
  });

  tabBeforeBtn.addEventListener("click", () => {
    tabBeforeBtn.classList.add("active");
    tabAfterBtn.classList.remove("active");
    tabBeforeContent.classList.add("active");
    tabAfterContent.classList.remove("active");
  });
}

// --- Event Listeners ---
function setupEventListeners() {
  document.getElementById("runInvestigationBtn").addEventListener("click", runInvestigation);
  document.getElementById("approveActionBtn").addEventListener("click", () => approveCase(false));
  document.getElementById("overrideActionBtn").addEventListener("click", () => approveCase(true));
}

// --- Load Preset Scenarios ---
async function loadScenarios() {
  try {
    const res = await fetch("/api/scenarios");
    const data = await res.json();
    scenarios = data.scenarios || [];

    const container = document.getElementById("scenarioButtons");
    container.innerHTML = "";

    scenarios.forEach((sc, idx) => {
      const btn = document.createElement("button");
      btn.className = `scenario-btn ${idx === 0 ? "active" : ""}`;
      btn.innerHTML = `<span>#0${idx + 1}</span> ${sc.title.split(":")[0]} (${sc.amount})`;
      btn.addEventListener("click", () => selectScenario(sc, btn));
      container.appendChild(btn);
    });

    if (scenarios.length > 0) {
      // Just populate first scenario without blocking
      document.getElementById("claimTextInput").value = scenarios[0].claim_text;
      document.getElementById("txnIdInput").value = scenarios[0].transaction_id;
      // Pre-load case for initial view
      const caseRes = await fetch("/api/disputes/cases");
      const casesData = await caseRes.json();
      if (casesData.cases && casesData.cases.length > 0) {
        currentCase = casesData.cases[0];
        renderCase(currentCase);
      }
    }
  } catch (err) {
    console.error("Failed to load scenarios:", err);
  }
}

// --- Scenario Selection ---
function selectScenario(sc, btnElement) {
  document.querySelectorAll(".scenario-btn").forEach((b) => b.classList.remove("active"));
  if (btnElement) btnElement.classList.add("active");

  document.getElementById("claimTextInput").value = sc.claim_text;
  document.getElementById("txnIdInput").value = sc.transaction_id;

  // Run with animated visual stepper
  runInvestigation();
}

// --- Animated Stepper while LLM processes ---
function startLiveStepperAnimation() {
  const steps = [
    { id: "stepIntake", desc: "Agent 1: Ingesting claim & parsing with Gemini..." },
    { id: "stepClock", desc: "Agent 2: Non-hallucinating calendar math & SLA lock..." },
    { id: "stepEvidence", desc: "Agent 3: Querying 3DS, IP telemetry & merchant APIs..." },
    { id: "stepAssess", desc: "Agent 4: Gemini analyzing statutory tests under Reg E/Z..." },
    { id: "stepLetter", desc: "Agent 5: Gemini drafting bespoke Fed-compliant notice..." },
  ];

  document.getElementById("pipelineStateBadge").textContent = "Agents Reasoning...";
  document.getElementById("pipelineStateBadge").className = "badge badge-warning";

  steps.forEach((s) => {
    const el = document.getElementById(s.id);
    el.classList.remove("completed");
    el.classList.remove("active");
  });

  let currentIdx = 0;
  function advance() {
    if (currentIdx < steps.length) {
      const step = steps[currentIdx];
      const el = document.getElementById(step.id);
      el.classList.add("active");
      const descEl = el.querySelector(".step-desc");
      if (descEl) descEl.textContent = step.desc;
      currentIdx++;
      stepAnimationTimer = setTimeout(advance, 1100);
    }
  }
  advance();
}

function stopLiveStepperAnimation() {
  if (stepAnimationTimer) clearTimeout(stepAnimationTimer);
}

// --- Run 5-Agent Investigation ---
async function runInvestigation() {
  const rawText = document.getElementById("claimTextInput").value.trim();
  const txnId = document.getElementById("txnIdInput").value.trim();
  const channel = document.getElementById("channelSelect").value;

  if (!rawText) {
    alert("Please enter a dispute claim text.");
    return;
  }

  const runBtn = document.getElementById("runInvestigationBtn");
  runBtn.innerHTML = `&#x23F3; Live Gemini Reasoning (~4s)...`;
  runBtn.disabled = true;

  // Start visual step progression
  startLiveStepperAnimation();

  try {
    const payload = {
      raw_text: rawText,
      transaction_id: txnId || undefined,
      channel: channel,
      engine: "neuro",
    };

    const res = await fetch("/api/disputes/investigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error("Investigation request failed.");

    currentCase = await res.json();
    stopLiveStepperAnimation();
    renderCase(currentCase);
  } catch (err) {
    stopLiveStepperAnimation();
    console.error("Error executing investigation:", err);
    alert("Failed to execute investigation. Check server logs.");
  } finally {
    runBtn.innerHTML = `<span class="btn-icon">&#x25B6;</span> Execute 5-Agent Investigation`;
    runBtn.disabled = false;
  }
}

// --- Render Case Data ---
function renderCase(c) {
  // 1. Intake Header
  const regimeBadge = document.getElementById("intakeRegimeBadge");
  regimeBadge.textContent = c.clock ? c.clock.regime : "REG_E_DEBIT";

  // 2. Regulatory Clock Sentinel
  renderClock(c.clock);

  // 3. Pipeline Stepper
  renderStepper(c);

  // 4. Evidence Dossier
  renderEvidence(c.evidence);

  // 5. Adjudication Proposal
  renderAdjudication(c.adjudication);

  // 6. Determination Letter
  renderLetter(c.letter);

  // 7. Reset Approval Box
  document.getElementById("approvalStatusBadge").textContent = c.analyst_approved
    ? "Approved & Executed"
    : "Pending Approval";
  document.getElementById("approvalStatusBadge").className = c.analyst_approved
    ? "badge badge-success"
    : "badge badge-warning";

  const receipt = document.getElementById("executionReceipt");
  if (c.analyst_approved) {
    const lastAudit = c.audit_trail[c.audit_trail.length - 1];
    receipt.style.display = "block";
    document.getElementById("receiptJson").textContent = JSON.stringify(lastAudit.details.ledger_posting, null, 2);
  } else {
    receipt.style.display = "none";
  }
}

// --- Render Regulatory Clock & Countdown ---
function renderClock(clock) {
  if (!clock) return;

  const urgencyPill = document.getElementById("clockUrgencyPill");
  urgencyPill.textContent = clock.urgency;
  urgencyPill.className = `urgency-pill ${clock.urgency.toLowerCase()}`;

  document.getElementById("intakeDateVal").textContent = clock.intake_date;
  document.getElementById("provDeadlineVal").textContent = clock.provisional_credit_deadline || "N/A (Reg Z)";
  document.getElementById("finalDeadlineVal").textContent = clock.investigation_deadline;
  document.getElementById("noticeDeadlineVal").textContent = clock.customer_notice_deadline;
  document.getElementById("statutoryCiteText").textContent = clock.statutory_citation;

  // Live countdown calculation
  if (countdownInterval) clearInterval(countdownInterval);

  const targetDateStr = clock.provisional_credit_deadline || clock.investigation_deadline;
  document.getElementById("provisionalDateStr").textContent = `Statutory Target: ${targetDateStr}`;

  const targetDate = new Date(targetDateStr);
  targetDate.setHours(23, 59, 59);

  function updateTimer() {
    const now = new Date();
    const diffMs = targetDate - now;

    if (diffMs <= 0) {
      document.getElementById("provisionalCountdown").textContent = "DEADLINE REACHED";
      document.getElementById("clockProgressFill").style.width = "100%";
      return;
    }

    const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diffMs / (1000 * 60 * 60)) % 24);
    const mins = Math.floor((diffMs / 1000 / 60) % 60);
    const secs = Math.floor((diffMs / 1000) % 60);

    document.getElementById("provisionalCountdown").textContent = `${days}d ${hours}h ${mins}m ${secs}s`;

    const elapsedRatio = Math.min(100, Math.max(10, ((10 - days) / 10) * 100));
    document.getElementById("clockProgressFill").style.width = `${elapsedRatio}%`;
  }

  updateTimer();
  countdownInterval = setInterval(updateTimer, 1000);
}

// --- Render Completed Stepper ---
function renderStepper(c) {
  document.getElementById("stepIntakeDesc").textContent = `Category: ${c.claim.claimed_category} | Regime: ${c.clock.regime}`;
  document.getElementById("stepClockDesc").textContent = `Provisional SLA: ${c.clock.provisional_credit_deadline || 'N/A'} | Resolution: ${c.clock.investigation_deadline}`;
  document.getElementById("stepEvidenceDesc").textContent = `Harvested ${c.evidence.items.length} artifacts across Core, 3DS & Merchant`;
  document.getElementById("stepAssessDesc").textContent = `Decision: ${c.adjudication.proposed_decision} (Conf: ${Math.round(c.adjudication.confidence_score * 100)}%)`;
  document.getElementById("stepLetterDesc").textContent = `Letter #${c.letter.letter_id} drafted with ${c.letter.relied_upon_documents.length} relied documents`;

  document.querySelectorAll(".step-item").forEach((el) => {
    el.classList.remove("active");
    el.classList.add("completed");
  });
  document.getElementById("pipelineStateBadge").textContent = "Completed (Ready for HITL)";
  document.getElementById("pipelineStateBadge").className = "badge badge-success";
}

// --- Render Evidence Dossier ---
function renderEvidence(evidence) {
  const container = document.getElementById("evidenceList");
  container.innerHTML = "";

  document.getElementById("evidenceCountBadge").textContent = `${evidence.items.length} Artifacts`;

  evidence.items.forEach((item) => {
    const card = document.createElement("div");
    const isFraud = item.indicates_fraud === true;
    const isLegit = item.indicates_fraud === false;

    card.className = `evidence-card ${isFraud ? "flagged" : isLegit ? "verified" : ""}`;
    card.innerHTML = `
      <div class="ev-header">
        <span class="ev-title">${item.title}</span>
        <span class="ev-type">${item.source_type}</span>
      </div>
      <div class="ev-desc">${item.relevance_summary}</div>
      <span class="ev-telemetry-tag">Ref: ${item.evidence_id} • Conf: ${Math.round(item.confidence_score * 100)}%</span>
    `;
    container.appendChild(card);
  });
}

// --- Render Adjudication ---
function renderAdjudication(adj) {
  const banner = document.getElementById("decisionBanner");
  banner.className = "decision-banner";

  const outcomeTitle = document.getElementById("decisionOutcomeTitle");
  const outcomeSub = document.getElementById("decisionOutcomeSub");
  outcomeTitle.textContent = adj.proposed_decision;
  outcomeSub.textContent = adj.primary_legal_basis;

  if (adj.proposed_decision.includes("APPROVE") || adj.proposed_decision.includes("GRANT")) {
    banner.classList.add("approve");
  } else if (adj.proposed_decision.includes("DENY")) {
    banner.classList.add("deny");
  } else if (adj.proposed_decision.includes("CHARGEBACK")) {
    banner.classList.add("chargeback");
  }

  document.getElementById("confidenceTag").textContent = `Confidence: ${Math.round(adj.confidence_score * 100)}%`;

  // Statutory Tests
  const testsList = document.getElementById("statutoryTestsList");
  testsList.innerHTML = "";

  adj.statutory_tests.forEach((test) => {
    const item = document.createElement("div");
    item.className = "test-item";
    item.innerHTML = `
      <span class="test-icon ${test.satisfied ? 'test-pass' : 'test-fail'}">${test.satisfied ? '&#x2714;' : '&#x2716;'}</span>
      <div class="test-text">
        <strong>${test.test_name} (${test.statutory_rule}):</strong> ${test.rationale}
      </div>
    `;
    testsList.appendChild(item);
  });
}

// --- Render Determination Letter ---
function renderLetter(letter) {
  const preview = document.getElementById("letterTextPreview");
  preview.innerHTML = `
    <p style="margin-bottom: 8px;"><strong>Date:</strong> ${letter.date_issued} | <strong>Notice Ref:</strong> ${letter.letter_id}</p>
    <p style="margin-bottom: 8px;"><strong>Dear ${letter.recipient_name},</strong></p>
    <p style="margin-bottom: 8px; line-height: 1.6;">${letter.detailed_factual_explanation}</p>
    <p style="font-size: 10.5px; color: #94a3b8; font-style: italic;">${letter.right_to_request_documents_notice}</p>
  `;

  const reliedList = document.getElementById("reliedDocsList");
  reliedList.innerHTML = "";
  letter.relied_upon_documents.forEach((doc) => {
    const li = document.createElement("li");
    li.textContent = doc;
    reliedList.appendChild(li);
  });
}

// --- Human-in-the-Loop Analyst Execution ---
async function approveCase(isOverride) {
  if (!currentCase) {
    alert("No active case to approve. Run an investigation first.");
    return;
  }

  const notes = document.getElementById("analystNotesInput").value.trim();
  const overrideDecision = isOverride ? prompt("Enter Override Decision (APPROVE_IMMEDIATE_REFUND, DENY_CLAIM, etc.):", "APPROVE_IMMEDIATE_REFUND") : null;

  try {
    const payload = {
      analyst_id: "J.Smith-SR-09",
      analyst_notes: notes,
      override_decision: overrideDecision || undefined,
    };

    const res = await fetch(`/api/disputes/cases/${currentCase.case_id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error("Approval failed.");

    currentCase = await res.json();
    renderCase(currentCase);
    alert(`Case ${currentCase.case_id} successfully signed off! Core banking ledger posting dispatched.`);
  } catch (err) {
    console.error("Approval error:", err);
    alert("Failed to submit analyst sign-off.");
  }
}
