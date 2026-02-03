#!/usr/bin/env python3
"""View all sports markets from Polymarket."""

from src.data.gamma_client import GammaAPIClient, MarketFilters

def show_sports():
    client = GammaAPIClient()
    
    # Keywords deportivos ampliados
    SPORTS_KEYWORDS = [
        'nba', 'nfl', 'mlb', 'nhl', 'mls',
        'premier league', 'la liga', 'bundesliga', 'serie a', 'ligue 1',
        'champions league', 'world cup', 'euro 2024', 'euro 2028',
        'super bowl', 'playoffs', 'finals',
        'tennis', 'wimbledon', 'us open', 'french open', 'australian open',
        'golf', 'pga', 'masters',
        'f1', 'formula 1', 'formula one',
        'ufc', 'boxing', 'fight',
        'olympics', 'olympic',
        'soccer', 'football', 'basketball', 'baseball', 'hockey',
        'mvp', 'rookie', 'coach', 'player',
        'win', 'champion', 'title', 'beat',
        'messi', 'ronaldo', 'lebron', 'curry', 'mahomes',
        'lakers', 'celtics', 'warriors', 'chiefs', 'eagles', '49ers', 'cowboys',
        'real madrid', 'barcelona', 'manchester', 'liverpool', 'bayern', 'psg',
        'brazil', 'argentina', 'germany', 'france', 'england', 'spain',
        'game', 'match', 'score', 'point', 'goal',
        'season', 'league', 'cup', 'tournament',
        'winter', 'summer'
    ]
    
    # Obtener TODOS los mercados (sin filtro de liquidez)
    filters = MarketFilters(
        min_volume_24h=0,
        min_liquidity=0,
        max_spread_pct=100
    )
    
    all_markets = client.get_filtered_markets(filters, limit=600)
    print(f'Total mercados Polymarket: {len(all_markets)}')
    
    # Filtrar deportivos
    sports = []
    for m in all_markets:
        q = m.get('question', '').lower()
        for kw in SPORTS_KEYWORDS:
            if kw in q:
                sports.append(m)
                break
    
    print(f'\nMercados deportivos encontrados: {len(sports)}')
    print('=' * 80)
    
    for i, m in enumerate(sports[:60]):
        q = m.get('question', '')
        tokens = m.get('tokens', [])
        yes_price = float(tokens[0].get('price', 0)) if tokens else 0
        volume = m.get('volume', 0)
        liquidity = m.get('liquidity', 0)
        
        print(f'{i+1:2}. {q[:75]}')
        print(f'    YES: {yes_price:.1%} | Vol: ${float(volume):,.0f} | Liq: ${float(liquidity):,.0f}')
        print()
    
    # Mostrar los que tienen mejor liquidez
    print('\n' + '=' * 80)
    print('TOP 10 POR LIQUIDEZ:')
    print('=' * 80)
    
    sports_sorted = sorted(sports, key=lambda x: float(x.get('liquidity', 0)), reverse=True)
    for i, m in enumerate(sports_sorted[:10]):
        q = m.get('question', '')
        tokens = m.get('tokens', [])
        yes_price = float(tokens[0].get('price', 0)) if tokens else 0
        liquidity = m.get('liquidity', 0)
        
        print(f'{i+1}. {q[:70]}')
        print(f'   YES: {yes_price:.1%} | Liq: ${float(liquidity):,.0f}')
        print()

if __name__ == "__main__":
    show_sports()
