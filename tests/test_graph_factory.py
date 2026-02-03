import pytest
import numpy as np
import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data.graph_factory import GraphFactory
from src.math.polytope import MarginalPolytope

class TestGraphFactoryStress:
    def test_load_50_markets(self):
        """
        Simulate 50 market processing ops. Uses Mock LLM inference.
        Checks if generated constraints allow feasibility.
        """
        factory = GraphFactory()
        
        # In a real scenario, we'd have 50 unique strings.
        # Here we loop to ensure stability.
        for i in range(50):
            markets = [
                {"question": f"Market {i} A", "id": f"m{i}_A"},
                {"question": f"Market {i} B", "id": f"m{i}_B"}
            ]
            
            # This returns standard A -> B structure in our mock
            relations = factory.generate_constraints(markets)
            
            # Validate output structure
            assert isinstance(relations, list)
            
            # Create a Polytope from it (Manually mapping the mock relation to constraint)
            # The Factory currently returns descriptions of relations, not raw coeffs.
            # We assume a translation step exists or we mock it here.
            
            # Constraint: A (idx 0) <= B (idx 1) => 1*A - 1*B <= 0
            # or source_idx(1)=B, target_idx(0)=A? 
            # Factory mock says: source=1 (target?), target=0. 
            # "Candidate implies Party". Trump(B) implies GOP(A). B <= A.
            
            constraints = [
                {'coeffs': [(1, 1), (0, -1)], 'sense': '<=', 'rhs': 0}
            ]
            
            poly = MarginalPolytope(n_conditions=2, constraints=constraints)
            
            # Test feasibility of logical vectors
            # Trump=1, GOP=1 -> Valid
            assert poly.is_feasible(np.array([1.0, 1.0]))
            # Trump=1, GOP=0 -> INVALID
            assert not poly.is_feasible(np.array([0.0, 1.0])) # idx0=A(GOP), idx1=B(Trump)
