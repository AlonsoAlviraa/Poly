import numpy as np
from src.math.polytope import MarginalPolytope

def kullback_leibler_divergence(mu: np.ndarray, theta: np.ndarray, eps=1e-12) -> float:
    """
    Calculates KL Divergence D(mu || theta).
    D(mu || theta) = sum(mu_i * ln(mu_i / theta_i))
    """
    # Clip to avoid log(0)
    mu_s = np.clip(mu, eps, 1.0)
    theta_s = np.clip(theta, eps, 1.0)
    return np.sum(mu_s * np.log(mu_s / theta_s))

def frank_wolfe_projection(
    theta: np.ndarray, 
    polytope: MarginalPolytope, 
    max_iter: int = 100, 
    tol: float = 1e-6,
    debug: bool = False
) -> np.ndarray:
    """
    Projects the current prices 'theta' onto the Marginal Polytope defined by 'polytope'.
    Minimizes KL Divergence D(mu || theta) using the Frank-Wolfe algorithm.
    
    Args:
        theta: Current market prices (probability vector).
        polytope: The constraint set oracle.
        max_iter: Maximum iterations.
        tol: Convergence tolerance (duality gap).
        
    Returns:
        mu_star: The arbitrage-free price vector.
    """
    n = len(theta)
    
    # 1. Initialization
    # We need a starting feasible point mu_0. 
    # We can try to find one by calling LMO with a random direction or just 0 direction
    # Use uniform direction to likely get a valid vertex
    z0 = polytope.find_descent_vertex(np.zeros(n)) 
    mu = z0.copy()
    
    # Track discrete active set (vertices) if needed, but for simple FW we just track the aggregate mu
    
    for t in range(max_iter):
        # 2. Gradient Calculation
        # Gradient of KL(mu || theta) wrt mu is: ln(mu) - ln(theta) + 1
        # We can ignore the +1 as it's a constant shift for the linear minimization
        # Clip mu to avoid log(0)
        mu_safe = np.clip(mu, 1e-9, 1.0)
        theta_safe = np.clip(theta, 1e-9, 1.0)
        
        gradient = np.log(mu_safe) - np.log(theta_safe)
        
        # 3. Linear Minimization Oracle (LMO)
        # Find vertex s that minimizes <gradient, s>
        s = polytope.find_descent_vertex(gradient)
        
        # 4. Compute Duality Gap
        # Gap = <gradient, mu - s>
        gap = np.dot(gradient, mu - s)
        
        if debug:
            print(f"Iter {t}: Gap={gap:.6f}, KL={kullback_leibler_divergence(mu, theta):.6f}")
            
        if gap <= tol:
            if debug: print("Converged.")
            break
            
        # 5. Step Size
        # Standard step size for FW is 2 / (t + 2)
        # For strictly convex function, Line Search is better, but 2/(t+2) guarantees convergence rate O(1/t)
        gamma = 2.0 / (t + 2.0)
        
        # 6. Update
        mu = (1 - gamma) * mu + gamma * s
        
    return mu
