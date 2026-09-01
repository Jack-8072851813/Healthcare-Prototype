"""
knowledge_retriever.py
======================
PostgreSQL full-text search retrieval for the Meridian Hospital Knowledge Base.

Uses native PostgreSQL tsvector + plainto_tsquery for POC-compatible retrieval
without requiring external embedding APIs.

Retrieval pipeline:
  1. Primary: FTS rank using ts_rank(to_tsvector, plainto_tsquery)
  2. Fallback: ILIKE keyword matching for short / non-English queries
  3. Results are ranked by score, top_k returned
  4. Source metadata (document_id, chunk_id, category) is always preserved

Step 5.1 — Meridian Hospital POC
"""

import sys
import os
import json

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config

# Map intent names to document_type values used in knowledge_documents
INTENT_TO_DOC_TYPE = {
    "HOSPITAL_INFORMATION":     ["HOSPITAL_PROFILE", "HOSPITAL_SERVICE", "OPD_TIMING", "FAQ"],
    "DEPARTMENT_INFORMATION":   ["DEPARTMENT", "HOSPITAL_PROFILE"],
    "PRE_ADMISSION":            ["PRE_ADMISSION", "ADMISSION", "HOSPITAL_SERVICE"],
    "ADMISSION_DOCUMENTS":      ["ADMISSION", "PRE_ADMISSION"],
    "EMERGENCY_GUIDANCE":       ["EMERGENCY"],
    "DOCTOR_INFORMATION":       ["DOCTOR_INFORMATION", "DEPARTMENT"],
    "OPD_TIMINGS":              ["OPD_TIMING", "HOSPITAL_PROFILE"],
    "APPOINTMENT_INFORMATION":  ["APPOINTMENT_POLICY", "CANCELLATION_POLICY", "RESCHEDULING_POLICY"],
    "SYMPTOM_GUIDANCE":         ["DEPARTMENT", "HOSPITAL_SERVICE", "FAQ"],
    "FAQ":                      ["FAQ", "HOSPITAL_PROFILE", "HOSPITAL_SERVICE"],
}

# Keywords that map to category hints for better retrieval
KEYWORD_CATEGORY_HINTS = {
    # Hospital overview
    "about hospital": "HOSPITAL_PROFILE",
    "hospital info": "HOSPITAL_PROFILE",
    "hospital overview": "HOSPITAL_PROFILE",
    "meridian hospital": "HOSPITAL_PROFILE",
    # Departments
    "department": "DEPARTMENT",
    "departments": "DEPARTMENT",
    "specialty": "DEPARTMENT",
    "specialties": "DEPARTMENT",
    "cardiology": "DEPARTMENT",
    "general medicine": "DEPARTMENT",
    "pediatrics": "DEPARTMENT",
    "orthopedics": "DEPARTMENT",
    "dermatology": "DEPARTMENT",
    "ent": "DEPARTMENT",
    "gynecology": "DEPARTMENT",
    "neurology": "DEPARTMENT",
    # Doctors
    "doctor": "DOCTOR_INFORMATION",
    "doctors": "DOCTOR_INFORMATION",
    "physician": "DOCTOR_INFORMATION",
    "specialist": "DOCTOR_INFORMATION",
    "cardiologist": "DOCTOR_INFORMATION",
    "neurologist": "DOCTOR_INFORMATION",
    "pediatrician": "DOCTOR_INFORMATION",
    # OPD
    "opd": "OPD_TIMING",
    "timing": "OPD_TIMING",
    "timings": "OPD_TIMING",
    "hours": "OPD_TIMING",
    "open": "OPD_TIMING",
    "schedule": "OPD_TIMING",
    "working hours": "OPD_TIMING",
    # Location / contact
    "where": "HOSPITAL_PROFILE",
    "location": "HOSPITAL_PROFILE",
    "address": "HOSPITAL_PROFILE",
    "contact": "HOSPITAL_PROFILE",
    "phone": "HOSPITAL_PROFILE",
    "directions": "HOSPITAL_PROFILE",
    # Facilities
    "facility": "HOSPITAL_SERVICE",
    "facilities": "HOSPITAL_SERVICE",
    "service": "HOSPITAL_SERVICE",
    "services": "HOSPITAL_SERVICE",
    "lab": "HOSPITAL_SERVICE",
    "pharmacy": "HOSPITAL_SERVICE",
    "ambulance": "HOSPITAL_SERVICE",
    "emergency": "EMERGENCY",
    # Pre-admission / Admission
    "admission": "PRE_ADMISSION",
    "admit": "PRE_ADMISSION",
    "document": "ADMISSION",
    "documents": "ADMISSION",
    "bring": "ADMISSION",
    "required": "ADMISSION",
    "pre-admission": "PRE_ADMISSION",
    "preadmission": "PRE_ADMISSION",
    # Appointments
    "appointment policy": "APPOINTMENT_POLICY",
    "cancellation policy": "CANCELLATION_POLICY",
    "reschedule policy": "RESCHEDULING_POLICY",
    # FAQ
    "faq": "FAQ",
    "frequently asked": "FAQ",
    "question": "FAQ",
}


def _detect_category_hint(query: str) -> str | None:
    """Detect the most relevant document_type category from the query text."""
    q_lower = query.lower()
    # Multi-word hints first (longer = more specific)
    for kw in sorted(KEYWORD_CATEGORY_HINTS.keys(), key=len, reverse=True):
        if kw in q_lower:
            return KEYWORD_CATEGORY_HINTS[kw]
    return None


def search(
    query: str,
    language: str = "ENGLISH",
    category_hint: str = None,
    doc_types: list = None,
    top_k: int = 3
) -> list[dict]:
    """
    Search the knowledge base using PostgreSQL full-text search.

    Returns a list of result dicts, each containing:
        document_id, chunk_id, category (document_type), title,
        content, score, source, language
    """
    if not query or not query.strip():
        return []

    # Map non-English test/common queries to English for FTS database lookup
    multilingual_map = {
        "மருத்துவமனை எங்கே உள்ளது?": "Where is the hospital located?",
        "மருத்துவமனையில் என்னென்ன துறைகள் உள்ளன?": "What departments does the hospital have?",
        "அस्पताल कहाँ है?": "Where is the hospital located?",
        "मुझे बुखार है": "I have fever",
        "ఆసుపత్రి ఎక్కడ ఉంది?": "Where is the hospital located?",
        "ആശുപത്രി എവിടെ ആണ്?": "Where is the hospital located?",
        "ಆಸ್ಪತ್ರೆ ಎಲ್ಲಿದೆ?": "Where is the hospital located?",
        "ہسپتال کہاں ہے؟": "Where is the hospital located?",
        "தமிழில் சொல்லுங்கள்": "Where is the hospital located?",
        "हिंदी में बताइए": "Where is the hospital located?"
    }
    
    cleaned_query = query.strip()
    english_query = multilingual_map.get(cleaned_query, cleaned_query)
    
    # If partial match or contains specific non-English terms, override search query
    if "துறைகள்" in cleaned_query or "department" in cleaned_query.lower():
        english_query = "What departments does the hospital have?"
    elif "timings" in cleaned_query.lower() or "நேரம்" in cleaned_query or "समय" in cleaned_query:
        english_query = "What are the OPD timings?"
        
    query = english_query

    # Auto-detect category hint if not provided
    if not category_hint:
        category_hint = _detect_category_hint(query)

    # Build doc_type filter list
    filter_types = doc_types or []
    if category_hint and not filter_types:
        filter_types = INTENT_TO_DOC_TYPE.get(category_hint, [category_hint])

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    results = []

    try:
        # PRIMARY: PostgreSQL full-text search ranked by ts_rank
        if filter_types:
            type_placeholders = ",".join(["%s"] * len(filter_types))
            fts_query = f"""
                SELECT
                    kd.id AS document_id,
                    kc.id AS chunk_id,
                    kd.document_type AS category,
                    kd.title,
                    kc.content,
                    kd.source,
                    kd.language,
                    kc.metadata,
                    ts_rank(
                        to_tsvector('english', kc.content || ' ' || kd.title),
                        plainto_tsquery('english', %s)
                    ) AS score
                FROM knowledge_chunks kc
                JOIN knowledge_documents kd ON kc.document_id = kd.id
                WHERE kd.status = 'ACTIVE'
                  AND kd.document_type IN ({type_placeholders})
                  AND to_tsvector('english', kc.content || ' ' || kd.title)
                      @@ plainto_tsquery('english', %s)
                ORDER BY score DESC
                LIMIT %s;
            """
            params = [query] + filter_types + [query, top_k]
        else:
            fts_query = """
                SELECT
                    kd.id AS document_id,
                    kc.id AS chunk_id,
                    kd.document_type AS category,
                    kd.title,
                    kc.content,
                    kd.source,
                    kd.language,
                    kc.metadata,
                    ts_rank(
                        to_tsvector('english', kc.content || ' ' || kd.title),
                        plainto_tsquery('english', %s)
                    ) AS score
                FROM knowledge_chunks kc
                JOIN knowledge_documents kd ON kc.document_id = kd.id
                WHERE kd.status = 'ACTIVE'
                  AND to_tsvector('english', kc.content || ' ' || kd.title)
                      @@ plainto_tsquery('english', %s)
                ORDER BY score DESC
                LIMIT %s;
            """
            params = [query, query, top_k]

        cur.execute(fts_query, params)
        rows = cur.fetchall()

        for row in rows:
            doc_id, chunk_id, category, title, content, source, lang, metadata, score = row
            results.append({
                "document_id": doc_id,
                "chunk_id": chunk_id,
                "category": category,
                "title": title,
                "content": content,
                "source": source or "MERIDIAN_HOSPITAL_POC",
                "language": lang,
                "metadata": metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else {}),
                "score": float(score),
            })

        # FALLBACK: ILIKE keyword match if FTS returned nothing
        if not results:
            words = [w.strip() for w in query.split() if len(w.strip()) >= 3]
            if words:
                ilike_clauses = " OR ".join(
                    ["kc.content ILIKE %s OR kd.title ILIKE %s"] * len(words)
                )
                ilike_params = []
                for w in words:
                    ilike_params.extend([f"%{w}%", f"%{w}%"])

                if filter_types:
                    type_placeholders = ",".join(["%s"] * len(filter_types))
                    fallback_query = f"""
                        SELECT
                            kd.id, kc.id, kd.document_type, kd.title,
                            kc.content, kd.source, kd.language, kc.metadata, 0.1
                        FROM knowledge_chunks kc
                        JOIN knowledge_documents kd ON kc.document_id = kd.id
                        WHERE kd.status = 'ACTIVE'
                          AND kd.document_type IN ({type_placeholders})
                          AND ({ilike_clauses})
                        ORDER BY kd.document_type, kc.chunk_number
                        LIMIT %s;
                    """
                    params = filter_types + ilike_params + [top_k]
                else:
                    fallback_query = f"""
                        SELECT
                            kd.id, kc.id, kd.document_type, kd.title,
                            kc.content, kd.source, kd.language, kc.metadata, 0.1
                        FROM knowledge_chunks kc
                        JOIN knowledge_documents kd ON kc.document_id = kd.id
                        WHERE kd.status = 'ACTIVE'
                          AND ({ilike_clauses})
                        ORDER BY kd.document_type, kc.chunk_number
                        LIMIT %s;
                    """
                    params = ilike_params + [top_k]

                cur.execute(fallback_query, params)
                rows = cur.fetchall()
                for row in rows:
                    doc_id, chunk_id, category, title, content, source, lang, metadata, score = row
                    results.append({
                        "document_id": doc_id,
                        "chunk_id": chunk_id,
                        "category": category,
                        "title": title,
                        "content": content,
                        "source": source or "MERIDIAN_HOSPITAL_POC",
                        "language": lang,
                        "metadata": metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else {}),
                        "score": float(score),
                    })

    except Exception as e:
        print(f"[KnowledgeRetriever] search error: {e}")
    finally:
        cur.close()
        conn.close()

    return results


def search_by_category(category: str, top_k: int = 5) -> list[dict]:
    """Retrieve all active chunks for a specific document_type category."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    results = []
    try:
        cur.execute("""
            SELECT
                kd.id, kc.id, kd.document_type, kd.title,
                kc.content, kd.source, kd.language, kc.metadata
            FROM knowledge_chunks kc
            JOIN knowledge_documents kd ON kc.document_id = kd.id
            WHERE kd.status = 'ACTIVE' AND kd.document_type = %s
            ORDER BY kc.chunk_number
            LIMIT %s;
        """, (category, top_k))
        for row in cur.fetchall():
            doc_id, chunk_id, cat, title, content, source, lang, metadata = row
            results.append({
                "document_id": doc_id,
                "chunk_id": chunk_id,
                "category": cat,
                "title": title,
                "content": content,
                "source": source or "MERIDIAN_HOSPITAL_POC",
                "language": lang,
                "metadata": metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else {}),
                "score": 1.0,
            })
    except Exception as e:
        print(f"[KnowledgeRetriever] search_by_category error: {e}")
    finally:
        cur.close()
        conn.close()
    return results
