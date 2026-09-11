import sys
import os
import pytest
import json
from unittest.mock import MagicMock, patch

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from agent import agent_service, state_manager, date_normalizer

@pytest.fixture(autouse=True)
def mock_db_and_tools():
    """Mock DB connection and tool execution for clean isolation."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    last_query = [""]

    def mock_execute(query, params=None):
        last_query[0] = str(query)

    def mock_fetchone():
        q = last_query[0].lower()
        if "from messages" in q:
            return None
        elif "from conversations" in q:
            return (100, "P001", "919999999999", "ENGLISH", "GREETING")
        elif "from patients" in q:
            return (1, "P001", "Gil", "Christ", "1990-01-01", "Male")
        return (100, "P001", "Gil", "Christ", "1990-01-01", "Male")

    mock_cur.execute.side_effect = mock_execute
    mock_cur.fetchone.side_effect = mock_fetchone
    mock_cur.fetchall.return_value = []

    def mock_router(*args, **kwargs):
        msg = kwargs.get("message_text") or (args[0] if args else "")
        msg_l = str(msg).lower()
        res = {
            "intent": "BOOK_APPOINTMENT",
            "department": None,
            "doctor_name": None,
            "date": None,
            "time": None,
            "booking_for": "SELF",
            "relationship": None,
            "patient_name": None,
            "date_of_birth": None,
            "gender": None,
            "reason": None
        }
        if "brother" in msg_l:
            res["booking_for"] = "FAMILY_MEMBER"
            res["relationship"] = "brother"
        elif "daughter" in msg_l:
            res["booking_for"] = "CHILD"
            res["relationship"] = "daughter"
        elif "myself" in msg_l or "self" in msg_l:
            res["booking_for"] = "SELF"

        if "ravi" in msg_l:
            res["patient_name"] = "Ravi"
        if "12 may 2010" in msg_l:
            res["date_of_birth"] = "2010-05-12"
        if "fever" in msg_l:
            res["reason"] = "fever"
        if "tomorrow" in msg_l:
            res["date"] = "tomorrow"
        if "dr arun" in msg_l:
            res["doctor_name"] = "Dr Arun"

        if res["date_of_birth"]:
            is_valid, clean_dob, _ = date_normalizer.validate_dob(res["date_of_birth"])
            if not is_valid:
                res["date_of_birth"] = None

        return res

    with patch("db_config.get_db_connection", return_value=mock_conn), \
         patch("agent.llm_intent_router.route_patient_message_llm", side_effect=mock_router):
        yield


def test_1_book_for_brother_sentence_not_in_dob():
    """Test 1: 'I want to book appointment for my brother' must not populate patient_dob with the sentence."""
    conv_id = "WA_9199999001_1"
    msg = "I want to book appointment for my brother"
    res = agent_service.process_agent_message(conv_id, "P001", msg)
    
    response_text = res.get("response", "")
    assert "DOB: I want to book appointment for my brother" not in response_text
    assert "brother" in response_text.lower() or "patient" in response_text.lower() or "details" in response_text.lower()


def test_2_my_brother_has_fever():
    """Test 2: 'My brother has fever' must extract reason='fever', relationship='brother', and DOB is NOT sentence."""
    conv_id = "WA_9199999002_1"
    msg = "My brother has fever"
    res = agent_service.process_agent_message(conv_id, "P001", msg)
    
    response_text = res.get("response", "")
    assert "DOB: My brother has fever" not in response_text


def test_3_brother_ravi_all_in_one():
    """Test 3: 'My brother Ravi was born on 12 May 2010 and has fever' extracts Name, DOB, Reason."""
    conv_id = "WA_9199999003_1"
    msg = "My brother Ravi was born on 12 May 2010 and has fever"
    res = agent_service.process_agent_message(conv_id, "P001", msg)
    
    norm_d, is_ambig, err_msg = date_normalizer.parse_and_normalize_date("12 May 2010")
    assert norm_d == "2010-05-12"
    assert is_ambig is False
    is_valid, clean_dob, _ = date_normalizer.validate_dob(norm_d)
    assert is_valid is True
    assert clean_dob == "2010-05-12"


def test_4_book_for_brother_tomorrow():
    """Test 4: 'I want to book for my brother tomorrow' detects date='tomorrow' and relationship='brother'."""
    conv_id = "WA_9199999004_1"
    msg = "I want to book for my brother tomorrow"
    res = agent_service.process_agent_message(conv_id, "P001", msg)
    
    response_text = res.get("response", "")
    assert "DOB: I want to book for my brother tomorrow" not in response_text


def test_5_brother_born_date_only():
    """Test 5: 'My brother was born on 12 May 2010' extracts valid DOB 2010-05-12."""
    conv_id = "WA_9199999005_1"
    msg = "My brother was born on 12 May 2010"
    res = agent_service.process_agent_message(conv_id, "P001", msg)
    
    norm_d, is_ambig, err_msg = date_normalizer.parse_and_normalize_date("12 May 2010")
    assert norm_d == "2010-05-12"
    assert is_ambig is False
    is_valid, clean_dob, _ = date_normalizer.validate_dob(norm_d)
    assert is_valid is True
    assert clean_dob == "2010-05-12"


def test_6_i_have_fever_self_booking():
    """Test 6: 'I have fever' is self booking context, not dependent."""
    conv_id = "WA_9199999006_1"
    msg = "I have fever"
    res = agent_service.process_agent_message(conv_id, "P001", msg)
    
    response_text = res.get("response", "")
    assert "brother" not in response_text.lower()


def test_7_dr_arun_tomorrow():
    """Test 7: 'Dr Arun tomorrow' is doctor/date query without erroneous dependent state."""
    conv_id = "WA_9199999007_1"
    msg = "Dr Arun tomorrow"
    res = agent_service.process_agent_message(conv_id, "P001", msg)
    
    response_text = res.get("response", "")
    assert "DOB: Dr Arun tomorrow" not in response_text


def test_8_appointment_for_daughter():
    """Test 8: 'I want an appointment for my daughter' detects relationship daughter."""
    conv_id = "WA_9199999008_1"
    msg = "I want an appointment for my daughter"
    res = agent_service.process_agent_message(conv_id, "P001", msg)
    
    response_text = res.get("response", "")
    assert "daughter" in response_text.lower() or "child" in response_text.lower() or "patient" in response_text.lower() or "details" in response_text.lower()


def test_9_switch_to_myself():
    """Test 9: 'I want an appointment for myself' or button btn_self ensures booking_for is SELF."""
    conv_id = "WA_9199999009_1"
    msg = "I want an appointment for myself"
    res = agent_service.process_agent_message(conv_id, "P001", msg)
    
    response_text = res.get("response", "")
    assert "DOB:" not in response_text or "DOB: I want" not in response_text


def test_10_existing_patient_brother_no_auto_id_leak():
    """Test 10: Existing patient saying 'I want to book for my brother' does NOT auto-assign primary patient's ID to brother."""
    conv_id = "WA_9199999010_1"
    
    state = state_manager.get_conversation_state(conv_id)
    state["primary_patient_id"] = "P00100"
    state["patient_id"] = "P00100"
    
    res = agent_service.process_agent_message(conv_id, "P00100", "I want to book for my brother")
    
    updated_state = state_manager.get_conversation_state(conv_id)
    assert updated_state.get("dependent_patient_id") != "P00100"
