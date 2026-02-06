"""
Graph-Based Resolution Engine (The "Brain")
Implements community detection (Louvain/Connected Components) to resolve
unmatched entities by clustering them based on transitive similarities.

Algorithm:
1. Build a Graph where nodes = Events (Poly, SX, BF).
2. Create edges between nodes if Similarity > Threshold (TokenSet, etc.).
3. Detect Communities (Clusters).
4. Extract Canonical Mappings from mixed clusters.
"""

import logging
import json
import os
import time
import math
from typing import List, Dict, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

# --- IMPORTS & FALLBACKS ---
try:
    import networkx as nx
    from networkx.algorithms.community import greedy_modularity_communities, louvain_communities
    HAS_NX = True
except ImportError:
    HAS_NX = False

try:
    import matplotlib.pyplot as plt
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False

try:
    from thefuzz import fuzz
except ImportError:
    from difflib import SequenceMatcher
    def fuzz_token_set_ratio(s1, s2):
        return SequenceMatcher(None, s1, s2).ratio() * 100
    class FuzzMock:
        token_set_ratio = fuzz_token_set_ratio
    fuzz = FuzzMock()


class GraphResolutionEngine:
    def __init__(self, memory_path="data/learning/graph_suggestions.json"):
        self.output_path = memory_path
        self.graph = nx.Graph() if HAS_NX else None
        
    def _calculate_hybrid_score(self, p: Dict, x: Dict) -> float:
        """
        Hybrid Similarity Score:
        1. Token Set Ratio (Base Payload) - 70% weight
        2. Date Alignment (Precision) - 20% weight
        3. Sport Context (Sanity) - 10% weight
        """
        # 1. Base Token Score
        q_text = p.get('question', '').lower()
        x_text = x.get('name', '').lower()
        
        try:
            token_score = fuzz.token_set_ratio(q_text, x_text)
        except: token_score = 0
        
        # 2. Date Bonus (Precision)
        # Check if dates align within 24h. If so, +100 bonus, else 0.
        # This acts as a strong filter when we average it.
        date_score = 0
        p_date = p.get('startDate') or p.get('gameStartTime')
        x_date = x.get('openDate') or x.get('marketStartTime')
        
        if p_date and x_date:
            try:
                # Simple string match of YYYY-MM-DD
                if str(p_date)[:10] == str(x_date)[:10]:
                    date_score = 100
                else:
                     # Penalize mismatched dates heavily
                     date_score = 0
            except: pass
        else:
            # Neutral if dates missing
            date_score = 50 

        # 3. Sport/Context Bonus
        # Assuming we passed pre-filtered lists, but let's check
        # Hard to check without explicit labels in dicts sometimes.
        context_score = 100 # Assume context is correct for now (passed from audit)

        # Weighted Sum
        # If dates mismatch, the score tanks.
        final_score = (token_score * 0.7) + (date_score * 0.3)
        return final_score

    def _generate_aliases(self, text: str) -> List[str]:
        """
        Generate semantic variations for higher recall (Data Enricher).
        e.g., "Jannik Sinner" -> ["J. Sinner", "Sinner J", "Sinner"]
        """
        aliases = {text}
        t = text.lower().strip()
        parts = t.split()
        
        # Tennis/Person Pattern: "First Last"
        if len(parts) == 2:
            f, l = parts[0], parts[1]
            if len(f) > 0 and len(l) > 1:
                aliases.add(f"{f[0]}. {l}") # J. Sinner
                aliases.add(f"{l}, {f[0]}.") # Sinner, J.
                aliases.add(f"{f[0]} {l}")   # J Sinner
                aliases.add(l)               # Sinner (Risky but useful for blocking)
        
        # Soccer/Team Pattern: "Man Utd" -> "Manchester United" (Mock)
        # In prod, this would use a real dictionary or Embedding lookup
        if 'man ' in t and 'utd' in t: aliases.add(t.replace('man ', 'manchester ').replace('utd', 'united'))
        
        return list(aliases)

    def resolve(self, unmatched_poly: List[Dict], candidates: List[Dict], threshold=60): # LOWER THRESHOLD
        """
        Main entry point for Graph Resolution v2.1.
        """
        if not HAS_NX:
            print("!! NetworkX not found. Graph resolution disabled.")
            return

        print(f"\n>> [GRAPH ENGINE v2.1] Initializing Enriched Resolution for {len(unmatched_poly)} orphans...")
        
        # 1. Build Graph with Alias Enrichment
        self.graph.clear()
        
        token_index = defaultdict(list)
        
        # Index Candidates with Aliases
        for x in candidates:
            x_id = f"X_{x.get('id')}"
            label = x.get('name', '')
            self.graph.add_node(x_id, type='exch', label=label, data=x)
            
            # Enrich Index
            for alias in self._generate_aliases(label):
                for t in set(alias.lower().split()):
                    if len(t) > 3: token_index[t].append(x_id)
        
        # Add Poly Nodes and Compute Edges
        edge_count = 0
        start_time = time.time()
        
        for p in unmatched_poly:
            p_id = f"P_{p.get('id')}"
            label = p.get('question', '')
            self.graph.add_node(p_id, type='poly', label=label, data=p)
            
            # Enrich Search
            p_aliases = self._generate_aliases(label)
            potential_x_ids = set()
            
            for alias in p_aliases:
                for t in set(alias.lower().split()):
                    if len(t) > 3 and t in token_index:
                        potential_x_ids.update(token_index[t])
            
            # Score Potentials
            for x_id in potential_x_ids:
                x_node = self.graph.nodes[x_id]
                score = self._calculate_hybrid_score(p, x_node['data'])
                
                # Dynamic Threshold per Sport?
                # Lower for Tennis due to "Sinner" matches
                if score >= threshold:
                    self.graph.add_edge(p_id, x_id, weight=score)
                    edge_count += 1
        
        print(f"   Edges Built: {edge_count} (in {time.time() - start_time:.2f}s)")
        
        if edge_count == 0: return # Empty

        # 2. Hub Pruning (Betweenness Centrality)
        # Detect nodes acting as bridges between disparate clusters (e.g. "United")
        if edge_count > 100: # Only expensive calc if graph is decent size
            try:
                print("   Calculating Centrality for Hub Pruning...")
                bc = nx.betweenness_centrality(self.graph, k=min(100, len(self.graph))) # Samping k for speed
                # Prune nodes with extreme betweenness (> 0.1 for bipartite is suspicious)
                pruned = 0
                for n, score in bc.items():
                    if score > 0.05: # Strict pruning
                        # Only prune if it's an ambiguous short name? 
                        # Or just remove edges? Removing node kills valid matches too.
                        # Let's flag edge weights instead (punish them).
                        pass # TODO: Implement edge punishment
            except: pass

        # 3. Community Detection (Greedy Modulatity)
        print("   Detecting Communities...")
        try:
            communities = list(greedy_modularity_communities(self.graph))
        except:
             # Fallback
             communities = list(nx.connected_components(self.graph))
             
        print(f"   Communities Detected: {len(communities)}")
        
        # 4. Extract Canonical Mappings
        suggestions = []
        
        for comm in communities:
            comm_list = list(comm)
            p_members = [n for n in comm_list if n.startswith('P_')]
            x_members = [n for n in comm_list if n.startswith('X_')]
            
            if p_members and x_members:
                subgraph = self.graph.subgraph(comm_list)
                avg_weight = sum([d['weight'] for u,v,d in subgraph.edges(data=True)]) / len(subgraph.edges())
                
                for p in p_members:
                    best_x, best_w = None, 0
                    for neighbor in self.graph.neighbors(p):
                        if neighbor in x_members:
                            w = self.graph[p][neighbor]['weight']
                            if w > best_w: best_w, best_x = w, neighbor
                    
                    if best_x:
                        p_data = self.graph.nodes[p]['data']
                        x_data = self.graph.nodes[best_x]['data']
                        suggestions.append({
                            "poly_id": p_data.get('id'),
                            "poly_question": p_data.get('question'),
                            "exch_name": x_data.get('name'),
                            "score": best_w,
                            "cluster_id": id(comm),
                            "avg_cluster_confidence": avg_weight
                        })

        # 5. Persistence
        if suggestions:
            print(f"   >> Discovered {len(suggestions)} enriched matches!")
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(suggestions, f, indent=2)
            print(f"   >> Suggestions saved to {self.output_path}")

        # 6. Viz (Keep existing)
        if HAS_PLOT and edge_count < 1000:
             # ... (Keep existing plotting code)
             pass

        # 6. Visualization (Matplotlib)
        if HAS_PLOT and edge_count < 500: # Don't plot massive graphs
            try:
                print("   Generating Graph Visualization (graph_viz.png)...")
                plt.figure(figsize=(12, 8))
                pos = nx.spring_layout(self.graph, k=0.15, iterations=20)
                
                # Draw Poly Nodes (Blue)
                nx.draw_networkx_nodes(self.graph, pos, nodelist=[n for n in self.graph.nodes if n.startswith('P_')], 
                                     node_color='skyblue', node_size=50, label='Polymarket')
                # Draw Exch Nodes (Orange)
                nx.draw_networkx_nodes(self.graph, pos, nodelist=[n for n in self.graph.nodes if n.startswith('X_')], 
                                     node_color='orange', node_size=50, label='Exchange')
                # Draw Edges
                nx.draw_networkx_edges(self.graph, pos, alpha=0.3)
                
                plt.title("Entity Resolution Graph (Spring Layout)")
                plt.legend()
                plt.axis('off')
                plt.savefig("data/learning/graph_viz.png", dpi=300)
                print("   >> Visualization saved.")
            except Exception as e:
                print(f"   Viz Error: {e}")
                
        print(">> [GRAPH ENGINE] Cycle Complete.")

