import logging
import json
import datetime
import traceback
import os
from typing import Any, Dict

class StructuredLogger:
    """
    JSON-based logger for high-fidelity auditing.
    """
    
    @staticmethod
    def _format_event(level: str, event_type: str, data: Dict[str, Any]) -> str:
        entry = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": level,
            "event_type": event_type,
            "data": data
        }
        return json.dumps(entry)

    def _persist(self, payload: str):
        sink = os.getenv("LOG_SINK_FILE", "logs/structured.jsonl")
        os.makedirs(os.path.dirname(sink), exist_ok=True)
        try:
            with open(sink, "a", encoding="utf-8") as handle:
                handle.write(payload + "\n")
        except OSError:
            pass

    def info(self, event_type: str, **kwargs):
        payload = self._format_event("INFO", event_type, kwargs)
        print(payload)
        if not os.getenv("LOG_DB_TOKEN"):
            self._persist(payload)

    def error(self, event_type: str, error: Exception = None, **kwargs):
        if error:
            kwargs['error_msg'] = str(error)
            kwargs['traceback'] = traceback.format_exc()
        payload = self._format_event("ERROR", event_type, kwargs)
        print(payload)
        if not os.getenv("LOG_DB_TOKEN"):
            self._persist(payload)
        
    def warning(self, event_type: str, **kwargs):
        payload = self._format_event("WARNING", event_type, kwargs)
        print(payload)
        if not os.getenv("LOG_DB_TOKEN"):
            self._persist(payload)
        
    def debug(self, event_type: str, **kwargs):
        # Could toggle print based on env var
        payload = self._format_event("DEBUG", event_type, kwargs)
        print(payload)
        if not os.getenv("LOG_DB_TOKEN"):
            self._persist(payload)

# Global Instance
audit_logger = StructuredLogger()
