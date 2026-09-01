"""
test_knowledge.py
=================
Step 5.1 automated test suite for the Meridian Hospital Knowledge Base + RAG.

22 test scenarios covering:
  1-9:    Hospital information queries (English)
  10-16:  Multilingual knowledge queries
  17-19:  Transactional ops still use appointment tools (NOT RAG)
  20:     Emergency overrides knowledge flow
  21:     Context switching (info → appointment → info)
  22:     No hallucinated hospital information

Run:
    python test_knowledge.py

Step 5.1 — Meridian Hospital POC
"""

import sys
import os
import uuid
import datetime
import pytz

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import agent.agent_service as agent_service
import knowledge.knowledge_retriever as knowledge_retriever
import knowledge.knowledge_service as knowledge_service

passed_tests = []
failed_tests = []


def call_agent(conv_id, message, patient_code=None, lang="ENGLISH"):
    return agent_service.process_agent_message(conv_id, patient_code, message, lang)


def log_result(name, passed, detail=""):
    if passed:
        passed_tests.append(name)
        print(f"[PASS] {name}")
    else:
        failed_tests.append(name)
        print(f"[FAIL] {name}" + (f" - {detail}" if detail else ""))


def run_tests():

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 1: Hospital overview question
    # ──────────────────────────────────────────────────────────────────────────
    try:
        results = knowledge_retriever.search("Tell me about Meridian Hospital", top_k=3)
        found = len(results) > 0 and any(
            "meridian" in r["content"].lower() or "hospital" in r["content"].lower()
            for r in results
        )
        log_result("Scenario 1: Hospital overview question", found)
    except Exception as e:
        log_result("Scenario 1: Hospital overview question", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 2: Department question
    # ──────────────────────────────────────────────────────────────────────────
    try:
        results = knowledge_retriever.search("What departments do you have?", top_k=3)
        found = len(results) > 0 and any(
            "cardiology" in r["content"].lower() or "department" in r["content"].lower()
            for r in results
        )
        log_result("Scenario 2: Department question", found)
    except Exception as e:
        log_result("Scenario 2: Department question", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 3: Doctor question
    # ──────────────────────────────────────────────────────────────────────────
    try:
        results = knowledge_retriever.search("Who are the doctors?", top_k=3)
        found = len(results) > 0 and any(
            "dr." in r["content"].lower() or "doctor" in r["content"].lower()
            for r in results
        )
        log_result("Scenario 3: Doctor question", found)
    except Exception as e:
        log_result("Scenario 3: Doctor question", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 4: OPD timing question
    # ──────────────────────────────────────────────────────────────────────────
    try:
        results = knowledge_retriever.search("What are the OPD timings?", top_k=3)
        found = len(results) > 0 and any(
            "opd" in r["content"].lower() or "timing" in r["content"].lower()
            or "schedule" in r["content"].lower()
            for r in results
        )
        log_result("Scenario 4: OPD timing question", found)
    except Exception as e:
        log_result("Scenario 4: OPD timing question", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 5: Hospital location question
    # ──────────────────────────────────────────────────────────────────────────
    try:
        results = knowledge_retriever.search("Where is Meridian Hospital located?", top_k=3)
        found = len(results) > 0 and any(
            "healthcare lane" in r["content"].lower() or
            "location" in r["content"].lower() or
            "address" in r["content"].lower() or
            "walfs" in r["content"].lower()
            for r in results
        )
        log_result("Scenario 5: Hospital location question", found)
    except Exception as e:
        log_result("Scenario 5: Hospital location question", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 6: Facility question
    # ──────────────────────────────────────────────────────────────────────────
    try:
        results = knowledge_retriever.search("What facilities does the hospital have?", top_k=3)
        found = len(results) > 0 and any(
            "facility" in r["content"].lower() or
            "pharmacy" in r["content"].lower() or
            "ambulance" in r["content"].lower() or
            "laboratory" in r["content"].lower()
            for r in results
        )
        log_result("Scenario 6: Facility question", found)
    except Exception as e:
        log_result("Scenario 6: Facility question", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 7: Pre-admission question (via agent)
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        res = call_agent(conv_id, "What is the pre-admission process?")
        found = (
            res["intent"] == "PRE_ADMISSION" and
            res["response"] and
            (
                "pre-admission" in res["response"].lower() or
                "admission" in res["response"].lower() or
                "procedure" in res["response"].lower()
            ) and
            knowledge_service.NO_KNOWLEDGE_RESPONSE not in res["response"]
        )
        log_result("Scenario 7: Pre-admission question", found)
    except Exception as e:
        log_result("Scenario 7: Pre-admission question", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 8: Admission documents question
    # ──────────────────────────────────────────────────────────────────────────
    try:
        results = knowledge_retriever.search("What documents are required for admission?", top_k=3)
        found = len(results) > 0 and any(
            "document" in r["content"].lower() or
            "id" in r["content"].lower() or
            "admission" in r["content"].lower()
            for r in results
        )
        log_result("Scenario 8: Admission documents question", found)
    except Exception as e:
        log_result("Scenario 8: Admission documents question", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 9: Unknown question — no hallucination
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        # Ask about something definitely not in the knowledge base
        res = call_agent(conv_id, "What is the hospital's policy on alien patients from Mars?")
        # Should return no-knowledge response, not an invented answer
        no_hallucination = (
            res["response"] is not None and
            (
                "don't have verified" in res["response"].lower() or
                "verified information" in res["response"].lower() or
                "can help you with" in res["response"].lower() or
                # If it routes to UNKNOWN or returns a graceful fallback
                res["intent"] in ["UNKNOWN", "GREETING", "HOSPITAL_INFORMATION"]
            )
        )
        # Critical: must NOT invent facts about "alien patients"
        no_fabrication = "alien" not in res["response"].lower() or "don't" in res["response"].lower()
        log_result("Scenario 9: Unknown question — no hallucination",
                   no_hallucination and no_fabrication)
    except Exception as e:
        log_result("Scenario 9: Unknown question — no hallucination", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 10: English knowledge query (via agent)
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        res = call_agent(conv_id, "What departments does Meridian Hospital have?", lang="ENGLISH")
        found = (
            res["intent"] == "HOSPITAL_INFORMATION" and
            res["response"] and
            len(res["response"]) > 20
        )
        log_result("Scenario 10: English knowledge query", found)
    except Exception as e:
        log_result("Scenario 10: English knowledge query", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 11: Tamil knowledge query
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        # Tamil: "மருத்துவமனை எங்கே உள்ளது?" (Where is the hospital?)
        res = call_agent(conv_id, "மருத்துவமனை எங்கே உள்ளது?", lang="TAMIL")
        # Should not crash and should return a meaningful response
        log_result("Scenario 11: Tamil knowledge query",
                   res["success"] and res["response"] and len(res["response"]) > 5)
    except Exception as e:
        log_result("Scenario 11: Tamil knowledge query", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 12: Hindi knowledge query
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        # Hindi: "अस्पताल कहाँ है?" (Where is the hospital?)
        res = call_agent(conv_id, "अस्पताल कहाँ है?", lang="HINDI")
        log_result("Scenario 12: Hindi knowledge query",
                   res["success"] and res["response"] and len(res["response"]) > 5)
    except Exception as e:
        log_result("Scenario 12: Hindi knowledge query", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 13: Telugu knowledge query
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        # Telugu: "ఆసుపత్రి ఎక్కడ ఉంది?" (Where is the hospital?)
        res = call_agent(conv_id, "ఆసుపత్రి ఎక్కడ ఉంది?", lang="TELUGU")
        log_result("Scenario 13: Telugu knowledge query",
                   res["success"] and res["response"] and len(res["response"]) > 5)
    except Exception as e:
        log_result("Scenario 13: Telugu knowledge query", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 14: Malayalam knowledge query
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        # Malayalam: "ആശുപത്രി എവിടെ ആണ്?" (Where is the hospital?)
        res = call_agent(conv_id, "ആശുപത്രി എവിടെ ആണ്?", lang="MALAYALAM")
        log_result("Scenario 14: Malayalam knowledge query",
                   res["success"] and res["response"] and len(res["response"]) > 5)
    except Exception as e:
        log_result("Scenario 14: Malayalam knowledge query", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 15: Kannada knowledge query
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        # Kannada: "ಆಸ್ಪತ್ರೆ ಎಲ್ಲಿದೆ?" (Where is the hospital?)
        res = call_agent(conv_id, "ಆಸ್ಪತ್ರೆ ಎಲ್ಲಿದೆ?", lang="KANNADA")
        log_result("Scenario 15: Kannada knowledge query",
                   res["success"] and res["response"] and len(res["response"]) > 5)
    except Exception as e:
        log_result("Scenario 15: Kannada knowledge query", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 16: Urdu knowledge query
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        # Urdu: "ہسپتال کہاں ہے؟" (Where is the hospital?)
        res = call_agent(conv_id, "ہسپتال کہاں ہے؟", lang="URDU")
        log_result("Scenario 16: Urdu knowledge query",
                   res["success"] and res["response"] and len(res["response"]) > 5)
    except Exception as e:
        log_result("Scenario 16: Urdu knowledge query", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 17: Appointment still uses appointment tool (not RAG)
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        res = call_agent(conv_id, "I want to book an appointment tomorrow", patient_code="P001")
        # Must be BOOK_APPOINTMENT intent, NOT HOSPITAL_INFORMATION
        # tool_called must NOT be search_knowledge
        uses_appointment_flow = (
            res["intent"] == "BOOK_APPOINTMENT" and
            res.get("tool_called") != "search_knowledge"
        )
        log_result("Scenario 17: Appointment still uses appointment tool", uses_appointment_flow)
    except Exception as e:
        log_result("Scenario 17: Appointment still uses appointment tool", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 18: Cancellation still uses cancellation tool
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        res = call_agent(conv_id, "I want to cancel my appointment", patient_code="P001")
        uses_cancel_flow = (
            res["intent"] == "CANCEL_APPOINTMENT" and
            res.get("tool_called") != "search_knowledge"
        )
        log_result("Scenario 18: Cancellation still uses cancellation tool", uses_cancel_flow)
    except Exception as e:
        log_result("Scenario 18: Cancellation still uses cancellation tool", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 19: Reschedule still uses reschedule tool
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        res = call_agent(conv_id, "I want to reschedule my appointment", patient_code="P001")
        uses_reschedule_flow = (
            res["intent"] == "RESCHEDULE_APPOINTMENT" and
            res.get("tool_called") != "search_knowledge"
        )
        log_result("Scenario 19: Reschedule still uses reschedule tool", uses_reschedule_flow)
    except Exception as e:
        log_result("Scenario 19: Reschedule still uses reschedule tool", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 20: Emergency still overrides knowledge flow
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        res = call_agent(conv_id, "I have severe chest pain. What department should I go to?")
        # Emergency must fire BEFORE knowledge retrieval
        emergency_handled = (
            res["intent"] in ["EMERGENCY_GUIDANCE", "SYMPTOM_GUIDANCE"] and
            (
                "emergency" in res["response"].lower() or
                "112" in res["response"] or
                "immediately" in res["response"].lower() or
                "call" in res["response"].lower()
            )
        )
        # Must NOT have a casual "visit Cardiology" answer without emergency warning
        no_casual_answer = "visit cardiology" not in res["response"].lower() or "emergency" in res["response"].lower()
        log_result("Scenario 20: Emergency overrides knowledge flow",
                   emergency_handled and no_casual_answer)
    except Exception as e:
        log_result("Scenario 20: Emergency overrides knowledge flow", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 21: Context switching (info → appointment → info)
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        # Start with an identified patient to bypass the new/existing patient greeting flow
        call_agent(conv_id, "Hi", patient_code="P001")
        # Info question with established patient context
        res_info = call_agent(conv_id, "What departments do you have?")
        info_ok = (
            res_info["response"] and len(res_info["response"]) > 10 and
            (
                res_info["intent"] == "HOSPITAL_INFORMATION" or
                any(d in res_info["response"].lower() for d in
                    ["cardiology", "general medicine", "pediatrics", "neurology", "department"])
            )
        )
        # Switch to booking
        res_book = call_agent(conv_id, "I want Cardiology appointment")
        book_ok = res_book["intent"] == "BOOK_APPOINTMENT"
        # Switch back to info
        res_info2 = call_agent(conv_id, "What are the OPD timings?")
        info2_ok = (
            res_info2["response"] and len(res_info2["response"]) > 10 and
            (
                res_info2["intent"] == "HOSPITAL_INFORMATION" or
                any(w in res_info2["response"].lower() for w in
                    ["opd", "timing", "schedule", "monday", "9:00", "morning", "9:0"])
            )
        )
        log_result("Scenario 21: Context switching (info -> appointment -> info)",
                   info_ok and book_ok and info2_ok)
    except Exception as e:
        log_result("Scenario 21: Context switching (info -> appointment -> info)", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Scenario 22: No hallucinated hospital information
    # ──────────────────────────────────────────────────────────────────────────
    try:
        conv_id = f"TEST_CONV_{uuid.uuid4().hex[:6]}"
        # Ask for the hospital fee — which is NOT in the knowledge base
        res = call_agent(conv_id, "What is the consultation fee?")
        # Must NOT fabricate a fee
        fabrication_terms = ["rs.", "inr", "rupee", "₹", "100", "200", "500"]
        no_fabrication = not any(term in res["response"].lower() for term in fabrication_terms)
        # Key criterion: no invented fee amounts, regardless of intent routing.
        # The agent may redirect to booking, info, or say it doesn't know — all acceptable.
        log_result("Scenario 22: No hallucinated hospital information", no_fabrication)
    except Exception as e:
        log_result("Scenario 22: No hallucinated hospital information", False, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    print("\n=== KNOWLEDGE SUITE SUMMARY ===")
    print(f"Passed: {len(passed_tests)}/22")
    print(f"Failed: {len(failed_tests)}/22")

    if failed_tests:
        print("\nFailed tests:")
        for t in failed_tests:
            print(f"  - {t}")
        return False
    return True


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
    print("\nAll 22 Knowledge Base verifications passed successfully!")
    sys.exit(0)
