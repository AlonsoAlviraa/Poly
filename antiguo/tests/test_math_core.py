import pytest
import numpy as np
from src.math.polytope import MarginalPolytope
from src.math.bregman import frank_wolfe_projection, kullback_leibler_divergence

class TestMathCore:
    def test_simple_polytope_constraints(self):
        """
        Test a simple market with 2 outcomes (A, B) where A + B = 1.
        Constraint: z_0 + z_1 == 1
        """
        constraints = [
            {'coeffs': [(0, 1), (1, 1)], 'sense': '=', 'rhs': 1}
        ]
        poly = MarginalPolytope(n_conditions=2, constraints=constraints)
        
        # Test Feasibility
        assert poly.is_feasible(np.array([0.5, 0.5]))
        assert not poly.is_feasible(np.array([0.8, 0.8]))
        
        # Test Oracle (Gradient Descent Vertex)
        # Gradient = [-1, 0] -> should pick [1, 0] to minimize <g, z> => -1
        # Gradient = [0, -1] -> should pick [0, 1] => -1
        vertex = poly.find_descent_vertex(np.array([-1.0, 0.0]))
        np.testing.assert_array_equal(vertex, np.array([1.0, 0.0]))
        
        vertex = poly.find_descent_vertex(np.array([0.0, -1.0]))
        np.testing.assert_array_equal(vertex, np.array([0.0, 1.0]))

    def test_frank_wolfe_projection_simple(self):
        """
        Test projection of arbitrage prices [0.2, 0.2] onto A+B=1 line.
        Should project to [0.5, 0.5] if entropy is minimized relative to uniform?
        
        Actually, we minimize KL D(mu || theta).
        Theta = [0.2, 0.2].
        Constraint: mu_0 + mu_1 = 1.
        Min sum mu_i ln(mu_i / 0.2).
        Lagrangian: mu ln(mu) - mu ln(0.2) + lambda(sum mu - 1).
        ln(mu) + 1 - ln(0.2) + lambda = 0
        mu = 0.2 * exp(-1 - lambda).
        So mu_0 and mu_1 should be proportional to theta_0 and theta_1.
        Since theta_0 = theta_1, mu_0 = mu_1.
        So mu = [0.5, 0.5].
        """
        constraints = [
            {'coeffs': [(0, 1), (1, 1)], 'sense': '=', 'rhs': 1}
        ]
        poly = MarginalPolytope(n_conditions=2, constraints=constraints)
        
        theta = np.array([0.2, 0.2])
        mu_star = frank_wolfe_projection(theta, poly, max_iter=50)
        
        print(f"Projected: {mu_star}")
        np.testing.assert_allclose(mu_star, np.array([0.5, 0.5]), atol=1e-2)

    def test_frank_wolfe_dependent(self):
        """
        Test A implies B. (A <= B)
        Outcomes:
        (0,0) - valid
        (0,1) - valid (B happens, A doesn't)
        (1,1) - valid (A happens, B must happen)
        (1,0) - INVALID (A happens, B doesn't)
        
        Constraint: z_0 - z_1 <= 0
        """
        constraints = [
            {'coeffs': [(0, 1), (1, -1)], 'sense': '<=', 'rhs': 0}
        ]
        poly = MarginalPolytope(n_conditions=2, constraints=constraints)
        
        # Price A=0.8, B=0.1. A > B. Arbitrage!
        # Should project to A <= B.
        theta = np.array([0.8, 0.1])
        mu_star = frank_wolfe_projection(theta, poly, max_iter=100)
        
        print(f"Projected Dependent: {mu_star}")
        assert mu_star[0] <= mu_star[1] + 1e-2
