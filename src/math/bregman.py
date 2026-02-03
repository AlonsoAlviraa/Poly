import numpy as np
import logging
from src.math.polytope import MarginalPolytope

logger = logging.getLogger(__name__)

def kullback_leibler_divergence(mu: np.ndarray, theta: np.ndarray, eps=1e-12) -> float:
    """
    Calculates KL Divergence D(mu || theta).
    D(mu || theta) = sum(mu_i * ln(mu_i / theta_i))
    LMSR Cost Function metric.
    """
    mu_s = np.clip(mu, eps, 1.0)
    theta_s = np.clip(theta, eps, 1.0)
    return np.sum(mu_s * np.log(mu_s / theta_s))

def log_barrier(mu: np.ndarray, eps=1e-12) -> float:
    """
    Logarithmic barrier function to keep mu away from boundaries [0, 1].
    B(mu) = -sum(log(mu) + log(1-mu))
    """
    mu_safe = np.clip(mu, eps, 1.0 - eps)
    return -np.sum(np.log(mu_safe) + np.log(1.0 - mu_safe))

def barrier_frank_wolfe_projection(
    theta: np.ndarray, 
    polytope: MarginalPolytope, 
    max_iter: int = 200, 
    tol: float = 1e-6,
    initial_epsilon: float = 0.1,
    volatility_mode: bool = False,
    debug: bool = False
) -> np.ndarray:
    """
    Projects prices 'theta' onto the Marginal Polytope using Barrier Frank-Wolfe.
    Handles the 'gradient explosion' problem of LMSR (log) near 0 by optimizing 
    over a contracted polytope M' = (1-eps)M + eps*u.
    
    Args:
        theta: Current market prices.
        polytope: Constraint oracle.
        max_iter: Max iterations.
        tol: Convergence tolerance.
        initial_epsilon: Starting contraction parameter (0 < eps < 1).
        volatility_mode: If True, use aggressive epsilon decay for speed.
    
    Returns:
        mu_star: Arbitrage-free price vector.
    """
    n = len(theta)
    
    # 1. Initialization
    u = np.ones(n) / n  # Barrier point (uniform)
    
    try:
        z0 = polytope.find_descent_vertex(np.zeros(n))
        mu = (1 - initial_epsilon) * z0 + initial_epsilon * u
    except Exception as e:
        logger.error(f"BFW Init failed: {e}")
        raise

    epsilon = initial_epsilon
    barrier_weight = 0.01  # Weight for log barrier in gradient
    
    # Volatility mode: faster decay, fewer iterations
    if volatility_mode:
        max_iter = min(max_iter, 50)
        epsilon = initial_epsilon * 0.5
    
    prev_gap = float('inf')
    stall_count = 0
    
    for t in range(max_iter):
        # 2. Gradient of D(mu || theta) + barrier
        mu_safe = np.clip(mu, 1e-12, 1.0 - 1e-12)
        theta_safe = np.clip(theta, 1e-12, 1.0)
        
        # KL gradient
        kl_gradient = np.log(mu_safe) - np.log(theta_safe)
        
        # Barrier gradient: -1/mu + 1/(1-mu)
        barrier_gradient = -1.0 / mu_safe + 1.0 / (1.0 - mu_safe)
        
        # Combined gradient
        gradient = kl_gradient + barrier_weight * barrier_gradient
        
        # 3. LMO on Original Polytope
        s = polytope.find_descent_vertex(gradient)
        
        # 4. Contracted Vertex
        s_bar = (1 - epsilon) * s + epsilon * u
        
        # 5. Duality Gap
        contracted_gap = np.dot(gradient, mu - s_bar)
        
        if debug:
            logger.debug(f"Iter {t}: Gap={contracted_gap:.6e}, Eps={epsilon:.4e}")
            
        if contracted_gap <= tol:
            if debug: 
                logger.info(f"BFW Converged at iter {t}")
            break
        
        # Stall detection
        if abs(prev_gap - contracted_gap) < tol * 0.1:
            stall_count += 1
            if stall_count > 5:
                if debug:
                    logger.warning(f"BFW Stalled at iter {t}")
                break
        else:
            stall_count = 0
        prev_gap = contracted_gap
            
        # 6. Adaptive Epsilon Decay
        if volatility_mode:
            epsilon = max(1e-8, epsilon * 0.8)
        elif contracted_gap < 10 * epsilon:
            epsilon = max(1e-6, epsilon * 0.9)
              
        # 7. Step Size
        gamma = 2.0 / (t + 2.0)
        
        # 8. Update
        mu = (1 - gamma) * mu + gamma * s_bar
        
        # Project back to valid range (safety)
        mu = np.clip(mu, 1e-12, 1.0 - 1e-12)
        
    return mu
