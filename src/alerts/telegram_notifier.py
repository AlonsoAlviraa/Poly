"""
Real-Time Alert System for Arbitrage Opportunities.
Supports Telegram notifications and webhook integrations.

Features:
1. Telegram bot integration for instant alerts
2. Configurable thresholds and filters
3. Rate limiting to avoid spam
4. Alert history and deduplication
"""

import logging
import time
import threading
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Callable
from queue import Queue
import os

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Represents an alert to be sent."""
    alert_type: str  # 'arb_opportunity', 'error', 'info', 'warning'
    title: str
    message: str
    data: Dict
    priority: int  # 1=low, 2=medium, 3=high
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


class TelegramNotifier:
    """
    Sends alerts via Telegram Bot API.
    
    Setup:
    1. Create bot with @BotFather
    2. Get bot token
    3. Get chat ID (message /start to bot, then check getUpdates)
    """
    
    API_URL = "https://api.telegram.org/bot{token}/{method}"
    
    def __init__(self, 
                 bot_token: Optional[str] = None,
                 chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self._enabled = bool(self.bot_token and self.chat_id)
        
        if not self._enabled:
            logger.warning("Telegram notifier disabled - missing BOT_TOKEN or CHAT_ID")
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a text message to configured chat."""
        if not self._enabled:
            logger.debug(f"[TELEGRAM DISABLED] Would send: {text[:100]}...")
            return False
            
        try:
            from src.utils.http_client import get_httpx_client
            
            url = self.API_URL.format(token=self.bot_token, method='sendMessage')
            
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            with get_httpx_client(timeout=10, http2=True) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                
            logger.debug("Telegram message sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False
    
    def format_arb_alert(self, alert: Alert) -> str:
        """Format an arbitrage opportunity alert."""
        data = alert.data
        
        emoji = "🚀" if alert.priority >= 3 else "💰" if alert.priority >= 2 else "📊"
        
        text = f"""
{emoji} <b>ARBITRAGE DETECTED</b> {emoji}

<b>Event:</b> {data.get('event_title', 'Unknown')[:40]}
<b>Strategy:</b> {data.get('strategy', 'Unknown')}
<b>Edge:</b> {data.get('edge_pct', 0):.2f}%
<b>Cost:</b> ${data.get('total_cost', 0):.4f}
<b>Payout:</b> ${data.get('guaranteed_payout', 0):.2f}
<b>Liquidity:</b> {'✅ OK' if data.get('liquidity_ok') else '⚠️ Low'}
<b>Confidence:</b> {data.get('confidence', 0)*100:.0f}%

<i>Time: {alert.timestamp}</i>
"""
        return text.strip()
    
    def format_error_alert(self, alert: Alert) -> str:
        """Format an error alert."""
        return f"""
🚨 <b>ERROR ALERT</b> 🚨

<b>{alert.title}</b>

{alert.message}

<i>Time: {alert.timestamp}</i>
"""
    
    def format_generic_alert(self, alert: Alert) -> str:
        """Format a generic alert."""
        emoji_map = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'arb_opportunity': '💰',
            'error': '🚨'
        }
        emoji = emoji_map.get(alert.alert_type, '📢')
        
        return f"""
{emoji} <b>{alert.title}</b>

{alert.message}

<i>Time: {alert.timestamp}</i>
"""


class AlertManager:
    """
    Manages alert dispatching with rate limiting and deduplication.
    """
    
    def __init__(self,
                 telegram_token: Optional[str] = None,
                 telegram_chat_id: Optional[str] = None,
                 min_alert_interval: int = 60,
                 min_edge_alert: float = 1.0):
        """
        Args:
            telegram_token: Bot token for Telegram
            telegram_chat_id: Chat ID to send messages
            min_alert_interval: Minimum seconds between same-type alerts
            min_edge_alert: Minimum edge % to trigger arb alert
        """
        self.telegram = TelegramNotifier(telegram_token, telegram_chat_id)
        self.min_interval = min_alert_interval
        self.min_edge = min_edge_alert
        
        self._queue: Queue = Queue()
        self._last_alerts: Dict[str, datetime] = {}  # type -> last time
        self._alert_history: List[Alert] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def start(self):
        """Start the alert processing thread."""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        logger.info("Alert manager started")
        
    def stop(self):
        """Stop the alert processing thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            
    def send_alert(self, alert: Alert):
        """Queue an alert for processing."""
        self._queue.put(alert)
        
    def send_arb_opportunity(self,
                             event_title: str,
                             strategy: str,
                             edge_pct: float,
                             total_cost: float,
                             guaranteed_payout: float,
                             liquidity_ok: bool,
                             confidence: float = 1.0):
        """Convenience method to send arbitrage alert."""
        if edge_pct < self.min_edge:
            return  # Below threshold
            
        priority = 3 if edge_pct >= 2.0 else 2 if edge_pct >= 1.0 else 1
        
        alert = Alert(
            alert_type='arb_opportunity',
            title=f"Arb: {edge_pct:.2f}% Edge",
            message=f"{strategy} opportunity in {event_title[:30]}",
            data={
                'event_title': event_title,
                'strategy': strategy,
                'edge_pct': edge_pct,
                'total_cost': total_cost,
                'guaranteed_payout': guaranteed_payout,
                'liquidity_ok': liquidity_ok,
                'confidence': confidence
            },
            priority=priority
        )
        self.send_alert(alert)
        
    def send_error(self, title: str, message: str, critical: bool = False):
        """Convenience method to send error alert."""
        alert = Alert(
            alert_type='error',
            title=title,
            message=message,
            data={},
            priority=3 if critical else 2
        )
        self.send_alert(alert)
        
    def send_info(self, title: str, message: str):
        """Convenience method to send info alert."""
        alert = Alert(
            alert_type='info',
            title=title,
            message=message,
            data={},
            priority=1
        )
        self.send_alert(alert)
        
    def _process_loop(self):
        """Main alert processing loop."""
        while self._running:
            try:
                # Get alert with timeout
                try:
                    alert = self._queue.get(timeout=1)
                except:
                    continue
                    
                # Check rate limiting
                if self._is_rate_limited(alert):
                    logger.debug(f"Alert rate limited: {alert.alert_type}")
                    continue
                    
                # Dispatch
                self._dispatch_alert(alert)
                
                # Update history
                self._last_alerts[alert.alert_type] = datetime.utcnow()
                self._alert_history.append(alert)
                
                # Trim history
                if len(self._alert_history) > 1000:
                    self._alert_history = self._alert_history[-500:]
                    
            except Exception as e:
                logger.error(f"Alert processing error: {e}")
                
    def _is_rate_limited(self, alert: Alert) -> bool:
        """Check if alert type is rate limited."""
        last = self._last_alerts.get(alert.alert_type)
        if not last:
            return False
            
        elapsed = (datetime.utcnow() - last).total_seconds()
        return elapsed < self.min_interval
        
    def _dispatch_alert(self, alert: Alert):
        """Dispatch alert to all channels."""
        # Format message
        if alert.alert_type == 'arb_opportunity':
            message = self.telegram.format_arb_alert(alert)
        elif alert.alert_type == 'error':
            message = self.telegram.format_error_alert(alert)
        else:
            message = self.telegram.format_generic_alert(alert)
            
        # Send via Telegram
        self.telegram.send_message(message)
        
        # Log
        logger.info(f"Alert sent: [{alert.alert_type}] {alert.title}")
        
    def get_recent_alerts(self, n: int = 10) -> List[Alert]:
        """Get most recent alerts."""
        return self._alert_history[-n:]


class ArbitrageAlertIntegration:
    """
    Integrates the alert system with the arbitrage scanner.
    """
    
    def __init__(self, scanner, alert_manager: AlertManager):
        self.scanner = scanner
        self.alerts = alert_manager
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def start_monitoring(self, scan_interval: int = 30):
        """
        Start continuous monitoring for arbitrage opportunities.
        
        Args:
            scan_interval: Seconds between scans
        """
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(
            target=self._monitoring_loop,
            args=(scan_interval,),
            daemon=True
        )
        self._thread.start()
        logger.info(f"Arbitrage monitoring started (interval: {scan_interval}s)")
        
    def stop_monitoring(self):
        """Stop the monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            
    def _monitoring_loop(self, interval: int):
        """Main monitoring loop."""
        while self._running:
            try:
                # Run scan
                opportunities = self.scanner.scan_all()
                
                # Alert on opportunities
                for opp in opportunities:
                    if opp.liquidity_ok and opp.edge_pct >= self.alerts.min_edge:
                        self.alerts.send_arb_opportunity(
                            event_title=opp.event_title,
                            strategy=opp.strategy,
                            edge_pct=opp.edge_pct,
                            total_cost=opp.total_cost,
                            guaranteed_payout=opp.guaranteed_payout,
                            liquidity_ok=opp.liquidity_ok,
                            confidence=opp.confidence
                        )
                        
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                self.alerts.send_error("Monitoring Error", str(e))
                
            time.sleep(interval)


def demo():
    """Demo the alert system."""
    print("=" * 70)
    print("ALERT SYSTEM DEMO")
    print("=" * 70)
    
    # Check for Telegram config
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("""
    ⚠️ Telegram not configured!
    
    To enable Telegram alerts:
    1. Create a bot with @BotFather on Telegram
    2. Copy the bot token
    3. Send /start to your bot
    4. Get your chat ID from: https://api.telegram.org/bot<TOKEN>/getUpdates
    5. Add to .env:
       TELEGRAM_BOT_TOKEN=your_token
       TELEGRAM_CHAT_ID=your_chat_id
""")
    
    # Create manager
    manager = AlertManager(
        min_alert_interval=30,
        min_edge_alert=0.5
    )
    manager.start()
    
    # Send test alerts
    print("\n    Sending test alerts...")
    
    manager.send_info(
        "System Started",
        "Polymarket Arbitrage Bot is now running."
    )
    
    manager.send_arb_opportunity(
        event_title="US Presidential Election 2024",
        strategy="sum_to_one",
        edge_pct=1.5,
        total_cost=0.97,
        guaranteed_payout=1.0,
        liquidity_ok=True,
        confidence=0.95
    )
    
    time.sleep(2)
    
    recent = manager.get_recent_alerts()
    print(f"\n    Recent alerts: {len(recent)}")
    
    for a in recent:
        print(f"      [{a.alert_type}] {a.title}")
    
    manager.stop()
    print("\n" + "=" * 70)


if __name__ == '__main__':
    demo()
