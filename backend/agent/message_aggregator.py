"""
message_aggregator.py
=====================
Debounce-based message aggregator for the WhatsApp AI Patient Desk.

Problem: WhatsApp users often send related content as multiple rapid messages
(e.g. "5" then "PM", or "I want to book" then "for tomorrow morning").
Without aggregation each fragment is processed independently, causing the bot
to miss context and ask repeated questions.

Solution: Per-phone-number debounce window.  When a new message arrives while
a window is still open for the same sender, the text is appended to the pending
buffer.  When the window expires (or flush is called explicitly), the aggregated
text is returned as a single logical turn.

Thread safety: Uses threading.Lock so it is safe under uvicorn's threaded mode.
For multi-worker deployments, replace _BUFFER with a shared store (Redis etc.)

Usage (in webhook handler):
    aggregator = MessageAggregator(window_seconds=3)
    ...
    merged = aggregator.add(from_number, text_body)
    if merged is None:
        # window still open – 200 OK immediately, wait for flush
        return {"status": "buffering"}
    # merged is ready – pass to agent
    agent_result = agent_service.process_agent_message(...)
"""

import threading
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Structured log helper
# ---------------------------------------------------------------------------
def _log(msg: str) -> None:
    print(f"[MSG_AGG] {msg}")


# ---------------------------------------------------------------------------
# Core Aggregator
# ---------------------------------------------------------------------------
class MessageAggregator:
    """
    Debounce-window message aggregator keyed by sender phone number.

    Parameters
    ----------
    window_seconds : float
        How long (seconds) to wait for more messages from the same sender
        before flushing.  Default 3 s is long enough to capture most split
        sends while keeping bot latency acceptable.
    max_buffer_size : int
        Hard limit on concatenated message length (guards against abuse).
    """

    def __init__(self, window_seconds: float = 3.0, max_buffer_size: int = 2000):
        self._window = window_seconds
        self._max_len = max_buffer_size
        self._lock = threading.Lock()
        # phone_number -> {"text": str, "expires_at": float, "timer": Timer|None}
        self._buffer: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, phone_number: str, text: str) -> Optional[str]:
        """
        Add a message fragment.  Returns:
        - None  : window is open, more fragments expected (caller returns 200 quickly)
        - str   : aggregated text ready for agent processing (window just started OR
                  this is a standalone message with no pending window)

        Caller pattern
        --------------
        merged = aggregator.add(phone, msg)
        if merged is None:
            return {"status": "buffering"}   # tell Meta we received it
        # Process merged text through agent
        """
        with self._lock:
            now = time.monotonic()
            entry = self._buffer.get(phone_number)

            if entry:
                # Existing window -- concatenate
                separator = self._choose_separator(entry["text"], text)
                new_text = entry["text"] + separator + text
                if len(new_text) > self._max_len:
                    new_text = new_text[: self._max_len]

                # Cancel old timer and reset window
                self._cancel_timer(phone_number)
                entry["text"] = new_text
                entry["expires_at"] = now + self._window
                _log(
                    f"[{phone_number}] Appended fragment. Buffer: \"{new_text[:120]}\""
                )
                # Restart timer
                self._start_timer(phone_number)
                return None  # still buffering
            else:
                # No existing window -- open one and immediately start timer
                self._buffer[phone_number] = {
                    "text": text,
                    "expires_at": now + self._window,
                    "timer": None,
                }
                _log(
                    f"[{phone_number}] Opened window. Initial text: \"{text[:120]}\""
                )
                self._start_timer(phone_number)
                return None  # buffering -- flush will deliver after window

    def flush(self, phone_number: str) -> Optional[str]:
        """
        Manually flush and return the buffered text for this phone number.
        Returns None if no buffer exists.
        Called automatically by the internal timer; can also be called on
        webhook shutdown or for testing.
        """
        with self._lock:
            entry = self._buffer.pop(phone_number, None)
            if entry:
                self._cancel_timer(phone_number, entry=entry)
                _log(f"[{phone_number}] Flushed: \"{entry['text'][:120]}\"")
                return entry["text"]
            return None

    def flush_immediate(self, phone_number: str, text: str) -> str:
        """
        Add text and immediately return the aggregated result without starting
        a window.  Used when window_seconds=0 or in tests.
        """
        with self._lock:
            entry = self._buffer.pop(phone_number, None)
            if entry:
                self._cancel_timer(phone_number, entry=entry)
                separator = self._choose_separator(entry["text"], text)
                merged = entry["text"] + separator + text
                _log(
                    f"[{phone_number}] Immediate flush+append: \"{merged[:120]}\""
                )
                return merged
            return text

    def pending_count(self) -> int:
        """Returns number of phone numbers currently buffering."""
        with self._lock:
            return len(self._buffer)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_timer(self, phone_number: str) -> None:
        """Start (or restart) the flush timer for a phone number. Lock must be held."""
        entry = self._buffer.get(phone_number)
        if not entry:
            return
        t = threading.Timer(self._window, self._on_timer_fire, args=(phone_number,))
        t.daemon = True
        entry["timer"] = t
        t.start()

    def _cancel_timer(self, phone_number: str, entry: dict = None) -> None:
        """Cancel any running timer. Lock must be held."""
        e = entry or self._buffer.get(phone_number)
        if e and e.get("timer"):
            e["timer"].cancel()
            e["timer"] = None

    def _on_timer_fire(self, phone_number: str) -> None:
        """
        Called from a daemon thread when the window expires.
        Flushes the buffer and dispatches the aggregated text to the registered
        callback (set via set_flush_callback).
        """
        text = self.flush(phone_number)
        if text and self._flush_callback:
            try:
                self._flush_callback(phone_number, text)
            except Exception as exc:
                _log(f"[{phone_number}] flush callback error: {exc}")

    @staticmethod
    def _choose_separator(existing: str, new_fragment: str) -> str:
        """
        Pick an appropriate separator when concatenating two message fragments.
        - Numeric fragments (e.g. "5") joined with a space -> "5 PM"
        - Otherwise newline for readability
        """
        existing = existing.strip()
        new_fragment = new_fragment.strip()

        # If existing ends with a digit or new starts with a unit/time word,
        # use a space so "5" + "PM" -> "5 PM"
        TIME_UNITS = {"am", "pm", "morning", "afternoon", "evening", "night",
                      "am.", "pm.", "o'clock"}
        if existing and existing[-1].isdigit():
            return " "
        if new_fragment.lower() in TIME_UNITS:
            return " "
        # Default: space (readable but not adding extra newlines)
        return " "

    def set_flush_callback(self, callback) -> None:
        """
        Register a callback: callback(phone_number: str, aggregated_text: str)
        Called automatically when the debounce window expires.
        """
        self._flush_callback = callback

    def __init__(self, window_seconds: float = 3.0, max_buffer_size: int = 2000):
        self._window = window_seconds
        self._max_len = max_buffer_size
        self._lock = threading.Lock()
        self._buffer: dict = {}
        self._flush_callback = None


# ---------------------------------------------------------------------------
# Module-level singleton (used by webhook handler)
# ---------------------------------------------------------------------------
_default_aggregator: Optional[MessageAggregator] = None


def get_aggregator(window_seconds: float = 3.0) -> MessageAggregator:
    """
    Returns the module-level singleton MessageAggregator.
    Creates it on first call with the given window.
    """
    global _default_aggregator
    if _default_aggregator is None:
        _default_aggregator = MessageAggregator(window_seconds=window_seconds)
        _log(f"Singleton aggregator created (window={window_seconds}s)")
    return _default_aggregator
