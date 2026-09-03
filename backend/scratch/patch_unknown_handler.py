"""
Patches agent_service.py: replaces the simple UNKNOWN else block
with a full LLM-powered intent classification + response fallback.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

target = os.path.join(os.path.dirname(__file__), '..', 'agent', 'agent_service.py')
with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

# Marker strings to find the exact block
START_MARKER = '    else:\n        # For unknown intents, check if the user is asking about features/capabilities'
END_MARKER = '            response_text = language_service.translate_response("UNKNOWN", current_lang)\n'

start_idx = content.find(START_MARKER)
end_idx = content.find(END_MARKER, start_idx)

if start_idx == -1 or end_idx == -1:
    print(f"ERROR: Could not find block. start={start_idx}, end={end_idx}")
    sys.exit(1)

end_idx += len(END_MARKER)
print(f"Found block at chars {start_idx}–{end_idx}")

NEW_BLOCK = '''    else:
        # ── LLM-powered fallback for UNKNOWN / unmatched intents ────────────
        msg_l_feat = message_text.lower().strip()
        is_features_query = any(w in msg_l_feat for w in [
            "feature", "features", "available features", "what can you do",
            "what do you do", "capabilities", "help me", "how can you help",
            "what can i do", "options", "menu"
        ])

        if is_features_query:
            state["interactive_buttons"] = []
            response_text = (
                "Here\'s what I can help you with at Meridian Hospital:\\n\\n"
                "\U0001f4c5 *Book Appointment* \u2014 Schedule a consultation with any doctor\\n"
                "\U0001f468\u200d\u2695\ufe0f *Doctor Availability* \u2014 Check which doctors are on duty\\n"
                "\U0001f3e5 *Hospital Information* \u2014 Location, departments, facilities, timings\\n"
                "\u274c *Cancel Appointment* \u2014 Cancel an existing booking\\n"
                "\U0001f504 *Reschedule Appointment* \u2014 Change your appointment date/time\\n"
                "\U0001f4cb *Appointment Status* \u2014 Check your booking status\\n"
                "\U0001fa7a *Pre-Admission Guidance* \u2014 Documents and steps for hospital admission\\n"
                "\U0001f195 *Register as New Patient* \u2014 Create your patient profile\\n\\n"
                "Just tell me what you need and I\'ll take care of it!"
            )
        elif llm_service.is_llm_active():
            # Load recent conversation history for context
            conv_history = []
            try:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT id FROM conversations WHERE conversation_code = %s;", (conversation_code,))
                    conv_row = cur.fetchone()
                    if conv_row:
                        cur.execute("""
                            SELECT sender_type, message_text FROM messages
                            WHERE conversation_id = %s
                              AND message_type = \'TEXT\'
                              AND sender_type IN (\'PATIENT\', \'AI_AGENT\')
                            ORDER BY id DESC LIMIT 10;
                        """, (conv_row[0],))
                        rows = cur.fetchall()
                        conv_history = [{"sender": r[0], "text": r[1]} for r in reversed(rows)]
                finally:
                    cur.close()
                    conn.close()
            except Exception as hist_err:
                print(f"[LLM Fallback] Could not load history: {hist_err}")

            # Call LLM for intent classification + response
            print(f"[LLM Fallback] Calling LLM for: \'{message_text[:80]}\'")
            llm_result = llm_service.llm_classify_intent_and_respond(
                message_text=message_text,
                current_state=state,
                language=current_lang,
                conversation_history=conv_history
            )

            llm_intent = llm_result.get("intent", "UNKNOWN")
            llm_response = llm_result.get("response")
            llm_route = llm_result.get("route_to_handler", False)
            llm_dept = llm_result.get("detected_department")
            llm_doctor = llm_result.get("detected_doctor")
            llm_date = llm_result.get("detected_date")
            llm_time = llm_result.get("detected_time")

            ROUTABLE_INTENTS = {
                "BOOK_APPOINTMENT", "CANCEL_APPOINTMENT", "RESCHEDULE_APPOINTMENT",
                "DOCTOR_AVAILABILITY", "APPOINTMENT_STATUS", "REGISTER_PATIENT",
                "HOSPITAL_INFORMATION", "PRE_ADMISSION", "SYMPTOM_GUIDANCE",
                "GREETING", "HUMAN_ESCALATION"
            }

            if llm_intent in ROUTABLE_INTENTS:
                # Update state intent so next turn routes correctly
                state["intent"] = llm_intent
                intent = llm_intent

                # Inject any entities the LLM detected
                if llm_dept and not state["entities"].get("department_id"):
                    try:
                        conn = db_config.get_db_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute(
                                "SELECT id FROM departments WHERE LOWER(department_name) = LOWER(%s) AND status=\'ACTIVE\' LIMIT 1;",
                                (llm_dept,)
                            )
                            dept_row = cur.fetchone()
                            if dept_row:
                                state["entities"]["department_id"] = dept_row[0]
                        finally:
                            cur.close()
                            conn.close()
                    except Exception:
                        pass

                if llm_doctor and not state["entities"].get("doctor_id"):
                    try:
                        conn = db_config.get_db_connection()
                        cur = conn.cursor()
                        try:
                            doc_search = llm_doctor.replace("Dr.", "").replace("Dr ", "").strip()
                            cur.execute(
                                "SELECT id FROM doctors WHERE LOWER(display_name) LIKE LOWER(%s) AND status=\'ACTIVE\' LIMIT 1;",
                                (f"%{doc_search}%",)
                            )
                            doc_row = cur.fetchone()
                            if doc_row:
                                state["entities"]["doctor_id"] = doc_row[0]
                        finally:
                            cur.close()
                            conn.close()
                    except Exception:
                        pass

                if llm_date and not state["entities"].get("appointment_date"):
                    from agent import entity_extractor as _ee
                    parsed_date = _ee.parse_natural_date(llm_date.lower())
                    if parsed_date:
                        state["entities"]["appointment_date"] = parsed_date

                if llm_time and not state["entities"].get("appointment_time"):
                    from agent import entity_extractor as _ee
                    parsed_time = _ee.parse_natural_time(llm_time.lower())
                    if parsed_time:
                        state["entities"]["appointment_time"] = parsed_time

                # Use LLM response directly (it handles both routed and informational cases)
                response_text = llm_response or language_service.translate_response("UNKNOWN", current_lang)
            else:
                response_text = llm_response or language_service.translate_response("UNKNOWN", current_lang)
        else:
            # LLM not configured — static fallback
            response_text = language_service.translate_response("UNKNOWN", current_lang)
'''

new_content = content[:start_idx] + NEW_BLOCK + content[end_idx:]

with open(target, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Patched successfully. New file size: {len(new_content)} chars")
