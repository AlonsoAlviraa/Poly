# Brainstorming (retrospectiva de sprint con stakeholders)

> Nota: la skill **brainstorming-pro** no está disponible en este entorno. Se aplica el formato exigido como fallback.

## Preguntas rápidas
- No aplican (se aportaron objetivo, contexto y restricciones).

## Ideas

### A) 10 ideas rápidas (qué haremos en los próximos sprints para subir matches y corregir fallos)
1. **Normalización unificada por deporte con alias overrides versionados** para reducir misses (aprovechar `mapping_cache/alias_overrides.json`).
2. **Resolvers por tipo de mercado y deporte** para evitar que O/U, spread, BTTS y winner caigan en lógica genérica (consolidar en `CrossPlatformMapper`).
3. **Re‑matching incremental con caché de tokens** para acelerar el matching masivo y evitar recomputar todo cada run.
4. **Scorecards por fuente y mercado** usando métricas ya expuestas en audit/logs para priorizar donde hay más misses.
5. **Enrichment multi‑deporte fuera de fútbol** con backfill dirigido (equipos y ligas minoritarias) y dedupe estricto.
6. **Validación “doble‑lado” obligatoria** en A vs B para reducir falsos positivos en soccer/tennis.
7. **Fuzzy matching solo en cola de baja confianza** para incrementar recall sin contaminar precision.
8. **Fallback de precios SX por selection resuelta** para evitar “No liquid prices” cuando el market sí tiene órdenes.
9. **Reglas de liga/competición como filtro duro** cuando el market lo trae (Betfair competition + Poly metadata).
10. **Tests sintéticos de mercados** (O/U, spreads, BTTS, winner) para regresiones rápidas.

### B) 5 ideas “diferentes” (ángulos menos obvios basados en el código actual)
1. **Fingerprinting de mercado**: hash del mercado por (tipo, línea, periodo) para unir eventos aun con texto distinto.
2. **Grafo temporal de eventos**: persistir matches y near‑misses para re‑usar aprendizaje entre runs.
3. **“Prompted reconcilers”**: LLM solo para casos limítrofes (cuando resolvers discrepan) y con caching.
4. **Negative dictionaries por deporte** (p. ej., “city”, “united”, homónimos) para evitar colisiones recurrentes.
5. **Batch‑merging cross‑exchange** por ventanas de tiempo y zona geográfica para reducir ambigüedad.

### C) 5 ideas “low effort” (quick wins en 1–2 sprints)
1. **Trazas de error top‑N por mercado** (ranking de fallos) para priorizar fixes.
2. **Alias overrides administrables por analistas** (JSON) con lint/validador simple.
3. **Cache de nombres normalizados** para evitar recomputación por iteración.
4. **Umbrales dinámicos por deporte** (elevar soccer, bajar tennis) con config simple.
5. **Alertas cuando sube el ratio de “No liquid prices”** para detectar fallos SX rápidamente.

### D) 3 ideas “high impact” (3–6 sprints)
1. **Motor híbrido reglas + ML** entrenado con histórico de matches correctos/incorrectos.
2. **Capa de datos exchange‑agnostic** con contratos estándar y adaptadores por fuente.
3. **Pipeline agresivo de scraping multi‑fuente** con reconciliación por confianza y dedupe.

## TOP 5 recomendado (plan de siguientes sprints)

1. **Consolidar resolvers por tipo de mercado + validación doble‑lado**  
   - **Por qué funciona:** reduce falsos positivos y mejora la selección de runner; sube calidad sin bajar cobertura.  
   - **Primer paso:** inventariar mercados actuales y alinear tests sintéticos por tipo.  
   - **Puntuación:** Impacto 5, Claridad 4, Novedad 3, Esfuerzo 3, Viabilidad 4.

2. **Normalización multi‑deporte con alias overrides y dedupe estricto**  
   - **Por qué funciona:** eleva recall en deportes fuera de fútbol y evita duplicados; es tangible para stakeholders.  
   - **Primer paso:** ampliar overrides por tennis/basketball/baseball y revisar entidades con colisiones.  
   - **Puntuación:** Impacto 4, Claridad 4, Novedad 3, Esfuerzo 2, Viabilidad 5.

3. **Fingerprinting de mercado**  
   - **Por qué funciona:** reduce dependencia del texto y aumenta matches multi‑deporte con bajo ruido.  
   - **Primer paso:** definir fingerprint para O/U, spreads y totals (línea + periodo + tipo).  
   - **Puntuación:** Impacto 4, Claridad 4, Novedad 4, Esfuerzo 3, Viabilidad 4.

4. **Grafo temporal de eventos + near‑misses**  
   - **Por qué funciona:** el sistema aprende entre runs y no “olvida” matches; mejora coverage incrementalmente.  
   - **Primer paso:** persistir matches y sugerencias con timestamps y score de confianza.  
   - **Puntuación:** Impacto 4, Claridad 3, Novedad 4, Esfuerzo 3, Viabilidad 4.

5. **Motor híbrido reglas + ML en cola de baja confianza**  
   - **Por qué funciona:** incrementa coverage con coste controlado y mantiene precision; ideal para inversores.  
   - **Primer paso:** dataset mínimo de pares match/no‑match y baseline de clasificación.  
   - **Puntuación:** Impacto 5, Claridad 3, Novedad 4, Esfuerzo 4, Viabilidad 3.
