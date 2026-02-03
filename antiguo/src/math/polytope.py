import pulp
import numpy as np
from typing import List, Tuple, Optional, Dict

class MarginalPolytope:
    """
    Represents the Marginal Polytope for a set of prediction markets.
    Manages the logical constraints $A^T z >= b$ and provides an 
    Linear Programming Oracle for the Frank-Wolfe algorithm.
    """

    def __init__(self, n_conditions: int, constraints: List[Dict]):
        """
        Initialize the polytope with N conditions and a list of constraints.
        
        Args:
            n_conditions: Total number of outcome conditions (variables in z).
            constraints: List of constraint dicts. Each dict should have:
                         'coeffs': list of (index, value) pairs.
                         'sense': '>=' or '<=' or '='.
                         'rhs': right-hand side value.
        """
        self.n = n_conditions
        self.constraints = constraints
        self.solver = pulp.PULP_CBC_CMD(msg=False) # Silence solver output

    def find_descent_vertex(self, gradient: np.ndarray) -> np.ndarray:
        """
        Solves the Linear Minimization Oracle (LMO) problem:
        $z^* = argmin_{z \in Z} <gradient, z>$
        
        This finds the vertex of the polytope that minimizes the inner product
        with the current gradient (steepest descent direction in linear space).
        """
        # Create a new IP problem
        prob = pulp.LpProblem("FrankWolfe_LMO", pulp.LpMinimize)
        
        # Define binary variables z_i
        # We use a dictionary for variables to match indices
        z_vars = {i: pulp.LpVariable(f"z_{i}", cat=pulp.LpBinary) for i in range(self.n)}
        
        # Set Objective Function: Minimize dot product with gradient
        prob += pulp.lpSum([gradient[i] * z_vars[i] for i in range(self.n)])
        
        # Add Structural Constraints
        for c in self.constraints:
            term = pulp.lpSum([val * z_vars[idx] for idx, val in c['coeffs']])
            rhs = c['rhs']
            sense = c.get('sense', '>=')
            
            if sense == '>=':
                prob += (term >= rhs)
            elif sense == '<=':
                prob += (term <= rhs)
            elif sense == '=':
                prob += (term == rhs)
                
        # Solve
        prob.solve(self.solver)
        
        if pulp.LpStatus[prob.status] != 'Optimal':
            raise ValueError(f"IP Solver failed to find solution. Status: {pulp.LpStatus[prob.status]}")
            
        # Extract solution
        z_star = np.zeros(self.n)
        for i in range(self.n):
            z_star[i] = pulp.value(z_vars[i])
            
        return z_star

    def is_feasible(self, vector: np.ndarray, tolerance: float = 1e-5) -> bool:
        """
        Checks if a given vector satisfies all constraints.
        This is a simple check, not an optimization.
        """
        for c in self.constraints:
            val = sum(vector[idx] * coeff for idx, coeff in c['coeffs'])
            rhs = c['rhs']
            sense = c.get('sense', '>=')
            
            if sense == '>=':
                if val < rhs - tolerance: return False
            elif sense == '<=':
                if val > rhs + tolerance: return False
            elif sense == '=':
                if abs(val - rhs) > tolerance: return False
                
        return True
