"""
test_tools.py
WHAT : a quick check that runs the three tools by hand, with no AI agent.
WHY  : we must know the SQL gives the right data before an agent uses it.
       If a tool is wrong, we want to find it now, not during an agent run.
FLOW : call each tool -> print what it returns -> we read it with our eyes.
NOTE : tools are wrapped with @tool, so we call them with .invoke({...}),
       not like a normal function.
"""
from tools import get_inactive_users, get_user_tickets, get_user_reviews

print("=" * 60)
print("TOOL 1: get_inactive_users (no order in 14 days, top 10)")
print("=" * 60)
print(get_inactive_users.invoke({"days": 14, "top_n": 10}))

# pick one inactive user id from the list above to test tools 2 and 3.
# change this number to any user_id you saw in tool 1's output.
sample_user = 17

print("\n" + "=" * 60)
print(f"TOOL 2: get_user_tickets for user {sample_user}")
print("=" * 60)
print(get_user_tickets.invoke({"user_id": sample_user}))

print("\n" + "=" * 60)
print(f"TOOL 3: get_user_reviews for user {sample_user}")
print("=" * 60)
print(get_user_reviews.invoke({"user_id": sample_user}))