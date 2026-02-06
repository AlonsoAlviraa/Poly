
import logging
import os
import pickle
import numpy as np
import time
import gc
from typing import List, Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)

class VectorMatcher:
    """
    Advanced Semantic Matcher using 'Chinese GitHub' Strategy.
    Stack:
    1. Retrieval: shibing624/text2vec-base-multilingual (CoSENT) -> Optimized for short text similarity.
    2. Re-Ranking: cross-encoder/ms-marco-MiniLM-L-6-v2 -> Precision filtering.
    3. Storage: Numpy (In-Memory + Pickle Persistence) - Replaces ChromaDB for lightweight compatibility.
    """
    
    def __init__(self, use_gpu: bool = False, persistence_path: str = "./data/vector_store.pkl"):
        self.use_gpu = use_gpu
        self.db_path = persistence_path
        self._retriever = None
        self._ranker = None
        
        # In-Memory Storage
        self.embeddings: Optional[np.ndarray] = None
        self.metadata: List[Dict] = []
        
        # Lazy load models to save startup time if not needed
        self._models_loaded = False

    def _load_models(self):
        """Load NLP models (heavy operation)."""
        if self._models_loaded:
            return

        try:
            from sentence_transformers import SentenceTransformer, CrossEncoder
        except ImportError:
            logger.error("Missing AI dependencies. Install: pip install sentence-transformers numpy")
            return

        logger.info("🧠 [Vector] Loading 'East Strategy' Models (Numpy Engine)...")
        
        # 1. Retrieval Model (CoSENT)
        try:
            self._retriever = SentenceTransformer('shibing624/text2vec-base-multilingual')
            logger.info("   -> Retriever: text2vec-base-multilingual (Loaded)")
        except Exception as e:
            logger.warning(f"   -> Failed to load text2vec: {e}. Fallback to all-MiniLM-L6-v2")
            self._retriever = SentenceTransformer('all-MiniLM-L6-v2')

        # 2. Re-Ranker (Cross-Encoder)
        try:
            self._ranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            logger.info("   -> Ranker: ms-marco-MiniLM-L-6-v2 (Loaded)")
        except Exception as e:
            logger.error(f"   -> Failed to load Ranker: {e}")
            
        # 3. Load Persistence if exists
        self._load_from_disk()
            
        self._models_loaded = True
        
    def _load_from_disk(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'rb') as f:
                    data = pickle.load(f)
                    self.embeddings = data['embeddings']
                    self.metadata = data['metadata']
                logger.info(f"   -> Loaded {len(self.metadata)} cached vectors.")
            except Exception as e:
                logger.warning(f"   -> Failed to load vector cache: {e}")

    def _save_to_disk(self):
        if not self.embeddings is None:
            try:
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                with open(self.db_path, 'wb') as f:
                    pickle.dump({
                        'embeddings': self.embeddings,
                        'metadata': self.metadata
                    }, f)
            except Exception as e:
                logger.warning(f"   -> Failed to save vector cache: {e}")

    def index_events(self, events: List[Dict]):
        """
        Index Betfair events into Numpy memory.
        Args:
            events: List of dicts with 'id', 'name', 'event_name'
        """
        self._load_models()
        if not self._retriever:
            return

        # Filter new items? For simplicty, simple rebuild or append.
        # Given the "Shadow Bot" nature, full rebuild of active events is safer and fast (<1sec).
        
        ids = []
        documents = []
        metadatas = []
        
        for ev in events:
            ev_id = str(ev.get('id') or ev.get('event_id'))
            name = ev.get('name') or ev.get('event_name')
            if not ev_id or not name:
                continue
                
            ids.append(ev_id)
            documents.append(name)
            metadatas.append({"id": ev_id, "name": name})
            
        if not documents:
            return

        # Embed batch
        logger.info(f"🧠 [Vector] Embedding {len(documents)} events...")
        new_embeddings = self._retriever.encode(documents, normalize_embeddings=True, show_progress_bar=False)
        
        # Replace current index (Fresh State)
        self.embeddings = new_embeddings
        self.metadata = metadatas
        self._save_to_disk()
        
        # OOM Protection
        gc.collect()
        
        logger.info(f"🧠 [Vector] Indexed {len(documents)} events (Numpy).")

    def find_matches(self, query: str, top_k: int = 10) -> Tuple[List[Tuple[Dict, float]], Dict]:
        """
        Two-Stage Search:
        1. Retrieve Top-K via Dot Product (Cosine Similarity).
        2. Re-Rank candidates.
        """
        self._load_models()
        stats = {'t_vector': 0.0, 't_rerank': 0.0, 'candidates_n': 0}
        
        if self.embeddings is None or not self._retriever or not self._ranker:
            return [], stats

        # Stage 1: Retrieval
        t0 = time.perf_counter()
        query_vec = self._retriever.encode([query], normalize_embeddings=True, show_progress_bar=False) # Shape (1, D)
        
        # Cosine Similarity (Normalized vectors . Normalized vectors = Cosine)
        # Shape: (N, D) @ (D, 1) -> (N, 1)
        sim_scores = self.embeddings @ query_vec.T
        sim_scores = sim_scores.flatten()
        
        # Get Top-K indices
        # argpartition is faster than sort
        k = min(top_k, len(self.metadata))
        if k == 0:
            return [], stats
            
        top_indices = np.argpartition(sim_scores, -k)[-k:]
        # Sort these top k strictly
        top_indices = top_indices[np.argsort(sim_scores[top_indices])[::-1]]
        
        candidates = []
        candidate_docs = []
        
        for idx in top_indices:
            candidates.append(self.metadata[idx])
            candidate_docs.append(self.metadata[idx]['name'])
            
        stats['t_vector'] = time.perf_counter() - t0
        stats['candidates_n'] = len(candidates)
        
        # Stage 2: Re-Ranking
        t1 = time.perf_counter()
        if candidate_docs:
            sentence_pairs = [[query, doc] for doc in candidate_docs]
            cross_scores = self._ranker.predict(sentence_pairs)
            
            scored_candidates = []
            for i, score in enumerate(cross_scores):
                # Apply Sigmoid to normalize logits (approx -10 to +10) to 0-1 probability
                prob = 1 / (1 + np.exp(-score))
                scored_candidates.append((candidates[i], float(prob)))
                
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            stats['t_rerank'] = time.perf_counter() - t1
            
            return scored_candidates, stats
            
        return [], stats

