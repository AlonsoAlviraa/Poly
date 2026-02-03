
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

@dataclass
class TraceStep:
    step: str
    status: str # 'PASS', 'FAIL', 'SKIP'
    details: str

@dataclass
class TraceableEvent:
    poly_id: str
    poly_name: str
    category: str = "unknown"
    steps: List[TraceStep] = field(default_factory=list)
    final_status: str = "PENDING"
    rejection_reason: str = ""
    
    def add_step(self, step: str, status: str, details: str):
        self.steps.append(TraceStep(step, status, details))
        if status == "FAIL":
            self.final_status = "REJECTED"
            self.rejection_reason = f"{step}: {details}"

class AuditLogger:
    """
    Suite de Diagnóstico (Mega Debugger)
    Transforms the pipeline into a 'Glass Box' with full traceability.
    """
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.events: Dict[str, TraceableEvent] = {}
        self.start_time = datetime.now()

    def get_event(self, poly_id: str, poly_name: str) -> TraceableEvent:
        if poly_id not in self.events:
            self.events[poly_id] = TraceableEvent(poly_id=poly_id, poly_name=poly_name)
        return self.events[poly_id]

    def generate_html_report(self, output_dir: str = "debug_reports"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        filename = f"debug_session_{self.session_id}.html"
        filepath = os.path.join(output_dir, filename)
        
        try:
            html = self._build_html()
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"🚀 Mega Debugger: HTML Report generated at {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            return None

    def _build_html(self) -> str:
        rows = ""
        # Sort events: PASS first, then by name
        sorted_events = sorted(
            self.events.values(), 
            key=lambda x: (0 if x.final_status == "PASS" else 1, x.poly_name)
        )
        
        for ev in sorted_events:
            status_class = "status-pass" if ev.final_status == "PASS" else "status-fail"
            
            steps_html = "<ul>"
            for s in ev.steps:
                s_class = "step-pass" if s.status == "PASS" else "step-fail" if s.status == "FAIL" else "step-skip"
                steps_html += f"<li class='{s_class}'><b>{s.step}:</b> {s.details}</li>"
            steps_html += "</ul>"
            
            rows += f"""
            <tr>
                <td>{ev.poly_name}</td>
                <td><span class="badge {status_class}">{ev.final_status}</span></td>
                <td>{ev.category}</td>
                <td>{steps_html}</td>
                <td>{ev.rejection_reason}</td>
            </tr>
            """
            
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>APU Mega Debugger - {self.session_id}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a1a; color: #e0e0e0; margin: 20px; }}
                h1 {{ color: #00ff88; }}
                table {{ width: 100%; border-collapse: collapse; background: #2d2d2d; border-radius: 8px; overflow: hidden; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #444; }}
                th {{ background: #3d3d3d; color: #00ff88; }}
                .badge {{ padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em; }}
                .status-pass {{ background: #006400; color: #00ff88; }}
                .status-fail {{ background: #8b0000; color: #ff4d4d; }}
                .step-pass {{ color: #00ff88; }}
                .step-fail {{ color: #ff4d4d; }}
                .step-skip {{ color: #aaaaaa; }}
                ul {{ list-style: none; padding: 0; margin: 0; font-size: 0.9em; }}
                li {{ margin-bottom: 4px; }}
            </style>
        </head>
        <body>
            <h1>🛠️ APU Mega Debugger: Pipeline Trace</h1>
            <p>Session: {self.session_id} | Scanned Markets: {len(self.events)}</p>
            <table>
                <thead>
                    <tr>
                        <th>Polymarket Name</th>
                        <th>Status</th>
                        <th>Category</th>
                        <th>Pipeline Steps</th>
                        <th>Resolution / Rejection Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </body>
        </html>
        """
