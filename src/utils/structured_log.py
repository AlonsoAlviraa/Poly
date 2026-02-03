import logging
import json
import datetime
import traceback
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

    def info(self, event_type: str, **kwargs):
        print(self._format_event("INFO", event_type, kwargs))

    def error(self, event_type: str, error: Exception = None, **kwargs):
        if error:
            kwargs['error_msg'] = str(error)
            kwargs['traceback'] = traceback.format_exc()
        print(self._format_event("ERROR", event_type, kwargs))
        
    def warning(self, event_type: str, **kwargs):
        print(self._format_event("WARNING", event_type, kwargs))
        
    def debug(self, event_type: str, **kwargs):
        # Could toggle print based on env var
        print(self._format_event("DEBUG", event_type, kwargs))

# Global Instance
audit_logger = StructuredLogger()
