"""
explore_db.py
WHAT : one-off inspection script - who looks dormant, and what does their
       login trend look like?
WHY  : before building agent tools, we verify the churn signal actually
       exists in the data. This query IS the prototype of Sub-agent 1.
FLOW : connect -> find customers with no orders in 14 days -> for each,
       compare logins in the 0-30 day window vs the 30-60 day window.
"""
import sqlite3

conn = sqlite3.connect("qcommerce.db")
cur = conn.cursor()

# --- 1. The dormant list: customers with no orders in the last 14 days ---
dormant = cur.execute("""
    SELECT u.user_id, u.full_name, u.city, MAX(o.placed_at) AS last_order
    FROM users u
    LEFT JOIN orders o ON o.user_id = u.user_id
    WHERE u.user_type = 'CUSTOMER'
    GROUP BY u.user_id
    HAVING last_order IS NULL OR last_order < datetime('now', '-14 days')
    ORDER BY last_order
""").fetchall()

print(f"--- {len(dormant)} dormant customers (no order in 14 days) ---")
for user_id, name, city, last_order in dormant:
    print(f"  [{user_id:>2}] {name:<18} {city:<10} last order: {last_order}")

# --- 2. The core churn signal: login trend, recent window vs previous window ---
print("\n--- login trend for dormant customers (30-60 days ago vs last 30 days) ---")
for user_id, name, city, last_order in dormant:
    prev = cur.execute("""
        SELECT COUNT(*) FROM auth_audit_log
        WHERE user_id = ? AND event_type = 'LOGIN'
          AND event_timestamp BETWEEN datetime('now','-60 days')
                                  AND datetime('now','-30 days')
    """, (user_id,)).fetchone()[0]
    recent = cur.execute("""
        SELECT COUNT(*) FROM auth_audit_log
        WHERE user_id = ? AND event_type = 'LOGIN'
          AND event_timestamp >= datetime('now','-30 days')
    """, (user_id,)).fetchone()[0]
    print(f"  [{user_id:>2}] {name:<18} logins 30-60d ago: {prev:>3}   last 30d: {recent:>3}")

conn.close()