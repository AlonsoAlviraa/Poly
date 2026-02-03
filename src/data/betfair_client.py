"""
Betfair Exchange API Client.
Handles authentication with SSL certificates and API operations.

Features:
- SSL Certificate authentication (non-interactive login)
- Session token management with auto-renewal (12h)
- Market listing and price fetching
- 15-minute delay support for free tier
"""

import os
import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
load_dotenv()


class BetfairEndpoint(Enum):
    """Betfair API endpoints."""
    # Spain/Italy use different endpoints (.es, .it)
    GLOBAL = "https://api.betfair.com"
    SPAIN = "https://api.betfair.es"
    ITALY = "https://api.betfair.it"
    
    IDENTITY_GLOBAL = "https://identitysso-cert.betfair.com/api/certlogin"
    IDENTITY_SPAIN = "https://identitysso.betfair.es/api/certlogin"
    IDENTITY_SPAIN_INTERACTIVE = "https://identitysso.betfair.es/api/login"
    
    # API Operations
    LOGOUT = "/exchange/betting/rest/v1/logout"
    KEEP_ALIVE = "/exchange/betting/rest/v1/keepAlive"
    
    # Betting API
    BETTING = "/exchange/betting/rest/v1"


@dataclass
class BetfairSession:
    """Active Betfair session data."""
    ssoid: str  # Session token
    created_at: datetime
    expires_at: datetime
    is_valid: bool = True
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    @property
    def time_remaining(self) -> timedelta:
        return self.expires_at - datetime.now()


@dataclass
class BetfairMarket:
    """Betfair market representation."""
    market_id: str
    market_name: str
    event_id: str
    event_name: str
    competition: str
    market_start_time: datetime
    total_matched: float
    status: str
    runners: List[Dict] = field(default_factory=list)


@dataclass
class BetfairPrice:
    """Price data from Betfair exchange."""
    market_id: str
    selection_id: int
    runner_name: str
    back_price: float  # Price to buy (bet for)
    lay_price: float   # Price to sell (bet against)
    back_size: float   # Available volume at best price
    lay_size: float
    back_liquidity_top3: float = 0.0  # Sum of volume in top 3 levels
    lay_liquidity_top3: float = 0.0
    last_traded: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BetfairClient:
    """
    Betfair Exchange API Client.
    
    Uses certificate-based authentication for non-interactive login.
    Supports 15-minute delayed data (free tier) or real-time (paid).
    """
    
    # Session validity: 12 hours, renew at 11 hours
    SESSION_VALIDITY_HOURS = 12
    SESSION_RENEW_HOURS = 11
    
    # Betfair commission rate (2% standard, can be lower with promotions)
    COMMISSION_RATE = 0.02
    
    def __init__(self,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 app_key: Optional[str] = None,
                 cert_path: Optional[str] = None,
                 key_path: Optional[str] = None,
                 endpoint: BetfairEndpoint = BetfairEndpoint.SPAIN,
                 use_delay: bool = True):
        """
        Initialize Betfair client.
        
        Args:
            username: Betfair account username (or BETFAIR_USERNAME env)
            password: Betfair account password (or BETFAIR_PASSWORD env)
            app_key: Betfair API app key (or BETFAIR_APP_KEY_DELAY/LIVE env)
            cert_path: Path to SSL certificate .crt file (or BETFAIR_CERT_PATH env)
            key_path: Path to SSL key .key file (or BETFAIR_KEY_PATH env)
            endpoint: API endpoint (GLOBAL, SPAIN, ITALY)
            use_delay: Use 15-minute delayed data (free tier)
        """
        # Load credentials from env - try multiple variations
        self.username = username or os.getenv('BETFAIR_USERNAME') or os.getenv('BETFAIR_USER')
        self.password = password or os.getenv('BETFAIR_PASSWORD') or os.getenv('BETFAIR_PASS')
        
        # Use delay key by default, live key if use_delay=False
        if use_delay:
            self.app_key = app_key or os.getenv('BETFAIR_APP_KEY_DELAY') or os.getenv('BETFAIR_APP_KEY')
        else:
            self.app_key = app_key or os.getenv('BETFAIR_APP_KEY_LIVE') or os.getenv('BETFAIR_APP_KEY')
        
        # Certificate paths
        self.cert_path = cert_path or os.getenv('BETFAIR_CERT_PATH') or os.getenv('BETFAIR_CERT') or './certs/client-2048.crt'
        self.key_path = key_path or os.getenv('BETFAIR_KEY_PATH') or os.getenv('BETFAIR_KEY') or './certs/client-2048.key'
        
        self.endpoint = endpoint
        self.use_delay = use_delay
        
        self._session: Optional[BetfairSession] = None
        self._client: Optional[httpx.AsyncClient] = None
        
        # Stats
        self.stats = {
            'api_calls': 0,
            'login_attempts': 0,
            'successful_logins': 0,
            'markets_fetched': 0,
            'prices_fetched': 0
        }
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate required configuration."""
        missing = []
        if not self.username:
            missing.append('BETFAIR_USERNAME')
        if not self.password:
            missing.append('BETFAIR_PASSWORD')
        if not self.app_key:
            missing.append('BETFAIR_APP_KEY_DELAY')
        
        if missing:
            logger.warning(f"[Betfair] Missing env vars: {missing}")
            logger.info("[Betfair] Set these in .env to enable Betfair integration")
    
    @property
    def base_url(self) -> str:
        """Get base URL for current endpoint."""
        return self.endpoint.value
    
    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid session."""
        if not self._session:
            return False
        if self._session.is_expired:
            return False
        return self._session.is_valid
    
    async def _init_client(self):
        """Initialize httpx client with SSL certificates and force HTTP/1.1."""
        if self._client is None:
            cert_exists = os.path.exists(self.cert_path) if self.cert_path else False
            key_exists = os.path.exists(self.key_path) if self.key_path else False
            
            if cert_exists and key_exists:
                # Use SSL certificate authentication. Force HTTP/1.1 as some WAFs (Spain) 
                # struggle with HTTP/2 + Certs.
                self._client = httpx.AsyncClient(
                    cert=(self.cert_path, self.key_path),
                    timeout=30.0,
                    http1=True,
                    http2=False
                )
                logger.info(f"[Betfair] SSL client initialized (HTTP/1.1 Forced)")
            else:
                self._client = httpx.AsyncClient(timeout=30.0)
                logger.warning("[Betfair] No SSL certs found, running in simulation mode")
    
    async def login(self) -> bool:
        """Authenticate using certificate-based login."""
        await self._init_client()
        self.stats['login_attempts'] += 1
        
        if not self.username or not self.password or not self.app_key:
            logger.error("[Betfair] Missing credentials for login")
            return False
        
        if self.endpoint == BetfairEndpoint.SPAIN:
            login_url = BetfairEndpoint.IDENTITY_SPAIN.value
            interactive_url = BetfairEndpoint.IDENTITY_SPAIN_INTERACTIVE.value
        else:
            login_url = BetfairEndpoint.IDENTITY_GLOBAL.value
            interactive_url = None
        
        headers = {
            'X-Application': self.app_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'User-Agent': 'QuantArbBot/2.0'
        }
        
        data = {
            'username': self.username,
            'password': self.password
        }
        
        try:
            logger.info(f"[Betfair] Attempting cert login via {login_url}...")
            response = await self._client.post(
                login_url,
                headers=headers,
                data=data
            )
            
            # Interactive Login Fallback (No Certs)
            if (response.status_code == 403 or (response.status_code == 200 and response.json().get('loginStatus') != 'SUCCESS')) and interactive_url:
                 logger.warning("[Betfair] Cert login failed. Trying Interactive Login (No Certs)...")
                 # New clean client for interactive (no certs attached)
                 async with httpx.AsyncClient() as interactive_client:
                     response = await interactive_client.post(
                        interactive_url,
                        headers=headers,
                        data=data
                     )
            
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                result = response.json()
                
                # Check different success keys
                status = result.get('loginStatus') or result.get('status')
                if status == 'SUCCESS':
                    ssoid = result.get('sessionToken') or result.get('token')
                    
                    self._session = BetfairSession(
                        ssoid=ssoid,
                        created_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(hours=self.SESSION_VALIDITY_HOURS),
                        is_valid=True
                    )
                    
                    self.stats['successful_logins'] += 1
                    logger.info(f"[Betfair] Login SUCCESS (Jurisdiction: {self.endpoint.name})")
                    return True
                else:
                    logger.error(f"[Betfair] Login REJECTED: {status}")
                    return False
            else:
                logger.error(f"[Betfair] Login HTTP ERROR {response.status_code}: {response.text[:100]}")
                return False
                
        except Exception as e:
            logger.error(f"[Betfair] Login EXCEPTION: {e}")
            return False
    
    async def keep_alive(self) -> bool:
        """
        Extend session validity.
        Should be called periodically (every 11 hours).
        """
        if not self.is_authenticated:
            return await self.login()
        
        await self._init_client()
        
        keep_alive_url = f"{self.base_url}{BetfairEndpoint.KEEP_ALIVE.value}"
        
        headers = {
            'X-Application': self.app_key,
            'X-Authentication': self._session.ssoid
        }
        
        try:
            response = await self._client.post(keep_alive_url, headers=headers)
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'SUCCESS':
                    # Extend session
                    self._session.expires_at = datetime.now() + timedelta(hours=self.SESSION_VALIDITY_HOURS)
                    logger.info("[Betfair] Session extended")
                    return True
            
            # Session expired, need to re-login
            return await self.login()
            
        except Exception as e:
            logger.error(f"[Betfair] Keep alive failed: {e}")
            return await self.login()
    
    async def logout(self) -> bool:
        """End current session."""
        if not self._session:
            return True
        
        await self._init_client()
        
        logout_url = f"{self.base_url}{BetfairEndpoint.LOGOUT.value}"
        
        headers = {
            'X-Application': self.app_key,
            'X-Authentication': self._session.ssoid
        }
        
        try:
            response = await self._client.post(logout_url, headers=headers)
            self._session = None
            return response.status_code == 200
        except:
            self._session = None
            return False
    
    async def _api_request(self, 
                           method: str, 
                           params: Dict = None) -> Optional[Dict]:
        """
        Make authenticated API request to Betfair Betting API.
        
        Args:
            method: API method name (e.g., 'listEventTypes')
            params: Request parameters
            
        Returns:
            API response or None on error
        """
        if not self.is_authenticated:
            if not await self.login():
                return None
        
        await self._init_client()
        
        url = f"{self.base_url}{BetfairEndpoint.BETTING.value}/{method}/"
        
        headers = {
            'X-Application': self.app_key,
            'X-Authentication': self._session.ssoid,
            'Content-Type': 'application/json'
        }
        
        try:
            response = await self._client.post(
                url,
                headers=headers,
                json=params or {}
            )
            
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"[Betfair] API error {method}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[Betfair] API exception {method}: {e}")
            return None
    
    async def list_event_types(self) -> List[Dict]:
        """
        Get all event types (sports categories).
        
        Returns:
            List of event types with IDs and names
        """
        result = await self._api_request('listEventTypes', {
            'filter': {}
        })
        
        if result:
            return [
                {
                    'id': et['eventType']['id'],
                    'name': et['eventType']['name'],
                    'market_count': et.get('marketCount', 0)
                }
                for et in result
            ]
        return []
    
    async def list_events(self, 
                          event_type_ids: List[str] = None,
                          competition_ids: List[str] = None,
                          from_date: datetime = None,
                          to_date: datetime = None) -> List[Dict]:
        """
        Get events (matches/games) for given criteria.
        
        Args:
            event_type_ids: Sport IDs (e.g., ['1'] for Soccer)
            competition_ids: Competition IDs (e.g., La Liga)
            from_date: Start date filter
            to_date: End date filter
        """
        filter_params = {}
        
        if event_type_ids:
            filter_params['eventTypeIds'] = event_type_ids
        if competition_ids:
            filter_params['competitionIds'] = competition_ids
        if from_date:
            filter_params['marketStartTime'] = {
                'from': from_date.isoformat()
            }
            if to_date:
                filter_params['marketStartTime']['to'] = to_date.isoformat()
        
        result = await self._api_request('listEvents', {
            'filter': filter_params
        })
        
        if result:
            self.stats['markets_fetched'] += len(result)
            return [
                {
                    'id': e['event']['id'],
                    'name': e['event']['name'],
                    'country_code': e['event'].get('countryCode'),
                    'timezone': e['event'].get('timezone'),
                    'venue': e['event'].get('venue'),
                    'open_date': e['event'].get('openDate'),
                    'market_count': e.get('marketCount', 0)
                }
                for e in result
            ]
        return []
    
    async def list_markets(self,
                           event_ids: List[str] = None,
                           market_types: List[str] = None,
                           max_results: int = 100) -> List[BetfairMarket]:
        """
        Get markets for events.
        
        Args:
            event_ids: Event IDs to fetch markets for
            market_types: Filter by market type (MATCH_ODDS, OVER_UNDER, etc.)
            max_results: Maximum results to return
        """
        filter_params = {}
        
        if event_ids:
            filter_params['eventIds'] = event_ids
        if market_types:
            filter_params['marketTypeCodes'] = market_types
        
        result = await self._api_request('listMarketCatalogue', {
            'filter': filter_params,
            'maxResults': max_results,
            'marketProjection': [
                'COMPETITION',
                'EVENT',
                'MARKET_START_TIME',
                'RUNNER_DESCRIPTION'
            ]
        })
        
        markets = []
        if result:
            for m in result:
                market = BetfairMarket(
                    market_id=m['marketId'],
                    market_name=m.get('marketName', ''),
                    event_id=m.get('event', {}).get('id', ''),
                    event_name=m.get('event', {}).get('name', ''),
                    competition=m.get('competition', {}).get('name', ''),
                    market_start_time=datetime.fromisoformat(m['marketStartTime'].replace('Z', '+00:00')) if m.get('marketStartTime') else datetime.now(),
                    total_matched=m.get('totalMatched', 0),
                    status='OPEN',
                    runners=[
                        {
                            'selection_id': r['selectionId'],
                            'runner_name': r.get('runnerName', ''),
                            'sort_priority': r.get('sortPriority', 0)
                        }
                        for r in m.get('runners', [])
                    ]
                )
                markets.append(market)
        
        return markets
    
    async def get_prices(self, 
                         market_ids: List[str],
                         price_projection: str = 'BEST') -> List[BetfairPrice]:
        """
        Get current prices for markets.
        
        Note: On free tier, prices are 15 minutes delayed.
        
        Args:
            market_ids: List of market IDs
            price_projection: 'BEST' for best available, 'ALL' for full ladder
        """
        result = await self._api_request('listMarketBook', {
            'marketIds': market_ids,
            'priceProjection': {
                'priceData': ['EX_BEST_OFFERS'],
                'exBestOffersOverrides': {
                    'bestPricesDepth': 3,
                    'rollupLimit': 3
                },
                'virtualise': True
            }
        })
        
        prices = []
        timestamp = datetime.now()
        
        # Apply 15-minute delay notice for free tier
        if self.use_delay:
            timestamp -= timedelta(minutes=15)
        
        if result:
            for market in result:
                market_id = market['marketId']
                
                for runner in market.get('runners', []):
                    selection_id = runner['selectionId']
                    
                    # Get best back (buy) price
                    back_prices = runner.get('ex', {}).get('availableToBack', [])
                    best_back = back_prices[0] if back_prices else {'price': 0, 'size': 0}
                    
                    # Get best lay (sell) price  
                    lay_prices = runner.get('ex', {}).get('availableToLay', [])
                    best_lay = lay_prices[0] if lay_prices else {'price': 0, 'size': 0}
                    
                    # Calculate top 3 liquidity
                    back_liq_top3 = sum(p.get('size', 0) for p in back_prices[:3])
                    lay_liq_top3 = sum(p.get('size', 0) for p in lay_prices[:3])
                    
                    price = BetfairPrice(
                        market_id=market_id,
                        selection_id=selection_id,
                        runner_name=runner.get('lastPriceTraded', 0),
                        back_price=best_back.get('price', 0),
                        lay_price=best_lay.get('price', 0),
                        back_size=best_back.get('size', 0),
                        lay_size=best_lay.get('size', 0),
                        back_liquidity_top3=back_liq_top3,
                        lay_liquidity_top3=lay_liq_top3,
                        last_traded=runner.get('lastPriceTraded', 0),
                        timestamp=timestamp
                    )
                    prices.append(price)
                    
            self.stats['prices_fetched'] += len(prices)
        
        return prices
    
    def calculate_implied_prob(self, decimal_odds: float) -> float:
        """
        Convert Betfair decimal odds to implied probability.
        
        Formula: probability = 1 / odds
        """
        if decimal_odds <= 0:
            return 0.0
        return 1.0 / decimal_odds
    
    def calculate_ev_net(self,
                         poly_prob: float,
                         betfair_odds: float,
                         stake: float = 10.0,
                         gas_cost: float = 0.10) -> Tuple[float, bool]:
        """
        Calculate net expected value for arbitrage.
        
        Formula: EV_net = (Precio_Poly - Precio_Betfair) - Gas - Comm_Betfair(2%)
        
        Args:
            poly_prob: Polymarket implied probability (0-1)
            betfair_odds: Betfair decimal odds
            stake: Bet size
            gas_cost: Estimated gas cost in USD
            
        Returns:
            (ev_net in USD, is_profitable)
        """
        # Convert Betfair odds to probability
        betfair_prob = self.calculate_implied_prob(betfair_odds)
        
        # Price difference (favorable if poly > betfair in prob terms)
        price_diff = poly_prob - betfair_prob
        
        # Commission and gas
        commission = stake * self.COMMISSION_RATE
        
        # EV calculation
        ev_gross = price_diff * stake
        ev_net = ev_gross - gas_cost - commission
        
        return ev_net, ev_net > 0
    
    def get_session_info(self) -> Dict:
        """Get current session information."""
        if not self._session:
            return {'status': 'NOT_LOGGED_IN', 'valid': False}
        
        return {
            'status': 'LOGGED_IN',
            'valid': self._session.is_valid and not self._session.is_expired,
            'created_at': self._session.created_at.isoformat(),
            'expires_at': self._session.expires_at.isoformat(),
            'time_remaining': str(self._session.time_remaining) if not self._session.is_expired else 'EXPIRED'
        }
    
    def get_stats(self) -> Dict:
        """Get client statistics."""
        return {
            **self.stats,
            'session': self.get_session_info(),
            'endpoint': self.endpoint.name,
            'using_delay': self.use_delay,
            'commission_rate': f"{self.COMMISSION_RATE:.0%}"
        }


# ============== SIMULATION MODE FOR TESTING ==============

class BetfairSimulator(BetfairClient):
    """
    Simulated Betfair client for testing without real API.
    Returns realistic mock data.
    """
    
    async def login(self) -> bool:
        """Simulate successful login."""
        self._session = BetfairSession(
            ssoid='SIMULATED_SESSION_TOKEN',
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=12),
            is_valid=True
        )
        logger.info("[Betfair SIM] Simulated login successful")
        return True
    
    async def list_event_types(self) -> List[Dict]:
        """Return simulated event types including Politics/Specials."""
        return [
            {'id': '2378961', 'name': 'Politics', 'market_count': 150},
            {'id': '10', 'name': 'Special Bets', 'market_count': 80},
            {'id': '6231', 'name': 'Financial Bets', 'market_count': 45},
            {'id': '1', 'name': 'Soccer', 'market_count': 1500},
            {'id': '2', 'name': 'Tennis', 'market_count': 800},
            {'id': '7', 'name': 'Horse Racing', 'market_count': 500},
        ]
    
    async def list_events(self, event_type_ids: List[str] = None, **kwargs) -> List[Dict]:
        """Return simulated events based on requested event types."""
        
        # Political/Financial events (for Polymarket matching)
        political_events = [
            {
                'id': 'pol_trump2028',
                'name': '2028 US Presidential Election - Trump',
                'country_code': 'US',
                'timezone': 'America/New_York',
                'venue': None,
                'open_date': (datetime.now() + timedelta(days=365)).isoformat(),
                'market_count': 25
            },
            {
                'id': 'pol_btc150k',
                'name': 'Bitcoin to exceed $150,000',
                'country_code': 'INTL',
                'timezone': 'UTC',
                'venue': None,
                'open_date': (datetime.now() + timedelta(days=180)).isoformat(),
                'market_count': 10
            },
            {
                'id': 'pol_fedrate',
                'name': 'Fed Interest Rate Decision - March 2026',
                'country_code': 'US',
                'timezone': 'America/New_York',
                'venue': None,
                'open_date': (datetime.now() + timedelta(days=30)).isoformat(),
                'market_count': 8
            },
            {
                'id': 'pol_ukpm',
                'name': 'Next UK Prime Minister',
                'country_code': 'GB',
                'timezone': 'Europe/London',
                'venue': None,
                'open_date': (datetime.now() + timedelta(days=200)).isoformat(),
                'market_count': 15
            }
        ]
        
        # Sports events
        sports_events = [
            {
                'id': '12345678',
                'name': 'Real Madrid vs Barcelona',
                'country_code': 'ES',
                'timezone': 'Europe/Madrid',
                'venue': 'Santiago Bernabeu',
                'open_date': (datetime.now() + timedelta(days=2)).isoformat(),
                'market_count': 50
            },
            {
                'id': '87654321',
                'name': 'Manchester United vs Liverpool',
                'country_code': 'GB',
                'timezone': 'Europe/London',
                'venue': 'Old Trafford',
                'open_date': (datetime.now() + timedelta(days=3)).isoformat(),
                'market_count': 45
            }
        ]
        
        # Filter based on requested event types
        if event_type_ids:
            # Polymarket-compatible types
            if any(eid in ['2378961', '10', '6231', '3988'] for eid in event_type_ids):
                return political_events
            # Sports types
            elif any(eid in ['1', '2', '4', '7', '7522'] for eid in event_type_ids):
                return sports_events
        
        # Default: return all
        return political_events + sports_events
    
    async def get_prices(self, market_ids: List[str], **kwargs) -> List[BetfairPrice]:
        """Return simulated prices with 15-min delay notation."""
        import random
        
        prices = []
        timestamp = datetime.now() - timedelta(minutes=15)  # Simulated delay
        
        for market_id in market_ids:
            # Simulate multiple runners
            for i in range(3):
                back_odds = 1.5 + random.random() * 3  # 1.5 to 4.5
                
                prices.append(BetfairPrice(
                    market_id=market_id,
                    selection_id=100 + i,
                    runner_name=f"Runner {i+1}",
                    back_price=round(back_odds, 2),
                    lay_price=round(back_odds + 0.02, 2),
                    back_size=round(random.random() * 1000, 2),
                    lay_size=round(random.random() * 800, 2),
                    last_traded=round(back_odds - 0.01, 2),
                    timestamp=timestamp
                ))
        
        return prices


# ============== DEMO ==============

async def demo():
    """Demo Betfair client functionality."""
    print("=" * 60)
    print("BETFAIR CLIENT DEMO")
    print("=" * 60)
    
    # Use simulator for demo
    client = BetfairSimulator(use_delay=True)
    
    # Login
    print("\n[1] Login...")
    success = await client.login()
    print(f"    Status: {'✅ Success' if success else '❌ Failed'}")
    print(f"    Session: {client.get_session_info()}")
    
    # List event types
    print("\n[2] Event Types (Sports)...")
    event_types = await client.list_event_types()
    for et in event_types[:3]:
        print(f"    {et['id']}: {et['name']} ({et['market_count']} markets)")
    
    # List events
    print("\n[3] Upcoming Events...")
    events = await client.list_events(event_type_ids=['1'])
    for e in events[:2]:
        print(f"    {e['id']}: {e['name']}")
    
    # Get prices
    print("\n[4] Market Prices (15-min delayed)...")
    prices = await client.get_prices(['1.123456789'])
    for p in prices[:3]:
        print(f"    Selection {p.selection_id}: Back={p.back_price}, Lay={p.lay_price}")
        print(f"      Timestamp: {p.timestamp} (DELAYED)")
    
    # Calculate EV
    print("\n[5] EV Calculation...")
    # Scenario: Polymarket YES at 0.65, Betfair odds 1.4 (= 0.71 prob)
    ev_net, is_profitable = client.calculate_ev_net(
        poly_prob=0.65,
        betfair_odds=1.4,
        stake=10.0,
        gas_cost=0.10
    )
    print(f"    Poly prob: 65%, Betfair odds: 1.4 (71.4% implied)")
    print(f"    EV Net: €{ev_net:.2f}")
    print(f"    Profitable: {'✅ YES' if is_profitable else '❌ NO'}")
    
    # Stats
    print("\n[6] Client Stats...")
    stats = client.get_stats()
    print(f"    {stats}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
