PORTFOLIO_ACCESS_PREDICATE = """
(
  :requester_role = 'admin'
  OR (
    :requester_role IN ('commercial', 'integral', 'investments')
    AND a.executive_email = :requester_email
  )
  OR (
    :requester_role = 'leader'
    AND EXISTS (
      SELECT 1
      FROM gold.commercial_hierarchy h
      WHERE h.leader_email = :requester_email
        AND h.executive_email = a.executive_email
        AND h.is_current = TRUE
    )
  )
)
"""

CUSTOMER_360_SQL = f"""
SELECT
  c.rut,
  a.executive_email,
  c.full_name,
  c.segment,
  COALESCE(SUM(b.balance), 0) AS total_balance,
  COLLECT_SET(p.product_name) AS products
FROM gold.customers c
JOIN gold.assignments a ON a.rut = c.rut AND a.is_current = TRUE
LEFT JOIN gold.balances b ON b.rut = c.rut
LEFT JOIN gold.products p ON p.rut = c.rut AND p.is_active = TRUE
WHERE c.rut = :rut
  AND {PORTFOLIO_ACCESS_PREDICATE}
GROUP BY c.rut, a.executive_email, c.full_name, c.segment
LIMIT 1
"""

LIST_PRIORITIZED_SQL = f"""
SELECT
  s.rut,
  a.executive_email,
  c.full_name,
  s.priority_score,
  s.priority_reason
FROM gold.customer_priority_scores s
JOIN gold.customers c ON c.rut = s.rut
JOIN gold.assignments a ON a.rut = s.rut AND a.is_current = TRUE
WHERE {PORTFOLIO_ACCESS_PREDICATE}
  AND (:executive_email IS NULL OR a.executive_email = :executive_email)
  AND (:segment IS NULL OR c.segment = :segment)
  AND (:min_priority IS NULL OR s.priority_score >= :min_priority)
ORDER BY s.priority_score DESC, s.rut
LIMIT :limit
"""
