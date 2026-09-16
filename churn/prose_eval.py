"""
prose_eval.py

WHAT : Fact-checks the agent's FREE TEXT, not just its structured evidence.
       verifier.py re-queries the six numbers the agent fills into a schema;
       this reads the `reason` sentence the agent wrote and checks the claims
       inside it - "three refund tickets remain unresolved", "a 1-star review
       reports a stale item", "logins rose from 0 to 12".
WHY  : The structured fields are the easy half. The prose is what a human
       actually reads, and it is the only part of the output nothing was
       checking. An agent can fill the schema correctly and still write a
       sentence about a ticket that does not exist.
FLOW : reason text -> split into clauses -> extract typed claims by pattern ->
       re-query the database for each claim -> PASS/FAIL, plus an explicit
       count of what could NOT be checked.
LOGIC: Claims are extracted by pattern, not by another LLM. Using a model to
       check a model reproduces the problem it is meant to solve: the checker
       would need its own verifier. Patterns only recognise claim types they
       were taught, so coverage is reported alongside fidelity - a sentence
       that yields no claim is counted as unchecked, never as correct.
"""
import re

from .config import PREDICTIONS_PATH, analysis_time, connect_readonly
from .logins import login_counts

# --- claim vocabulary -------------------------------------------------------

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# What a count can be a count OF. A noun that implies its own category
# ("two delivery delays") carries it; a generic one takes the category from
# the words in between ("two refund tickets").
HEAD_NOUNS = {
    "tickets": None, "ticket": None, "complaints": None, "complaint": None,
    "issues": None, "delays": "DELIVERY_DELAY", "delay": "DELIVERY_DELAY",
    "refunds": "REFUND", "refund": "REFUND",
    "payments": "PAYMENT", "payment": "PAYMENT",
}

# A word in the prose -> the ticket category it refers to. Order matters:
# longer phrases are tried first so "delivery delay" is not read as "delivery".
CATEGORY_WORDS = [
    (r"product[\s-]quality", "PRODUCT_QUALITY"),
    (r"delivery[\s-]delay", "DELIVERY_DELAY"),
    (r"order[\s-]issue", "ORDER_ISSUE"),
    (r"app[\s-]issue", "APP_ISSUE"),
    (r"\bdelivery\b", "DELIVERY_DELAY"),
    (r"\bdelayed\b", "DELIVERY_DELAY"),
    (r"\brefunds?\b", "REFUND"),
    (r"\bpayments?\b", "PAYMENT"),
    (r"\bquality\b", "PRODUCT_QUALITY"),
]

# Does the clause say the ticket is still open, or that it is finished?
# \bresolved\b does not match inside "unresolved", so the order is safe.
UNRESOLVED_MARKERS = r"\bunresolved\b|\bremains?\b|\bstill\b|\bopen\b|\bin[\s-]progress\b|\bpending\b|\boutstanding\b|\bwaiting\b"
# "excluded" and "does not qualify" are NOT resolution markers: the agent uses
# them for a ticket that is open but outside the rubric's serious categories.
# Reading one as "closed" produced a false alarm on correct prose.
RESOLVED_MARKERS = r"\bclosed\b|\bresolved\b|\bsettled\b"

# Descriptive claims about what a complaint SAYS. Only content words, so a
# claim cannot pass just by repeating the category it already claimed.
TOPIC_PATTERNS = {
    "stale": ("stale",),
    "expired": ("expired",),
    "leaking": ("leak",),
    "damaged": ("damag",),
    "wrong item": ("wrong item",),
    "missing item": ("missing",),
    "deducted": ("deducted",),
    "not received": ("not received", "received it", "not receive"),
}


def _clauses(text):
    """Split a reason into clauses. Polarity ('unresolved' vs 'closed')
    belongs to a clause, not to the whole sentence."""
    return [c.strip() for c in re.split(r"[.;]", text or "") if c.strip()]


def _flatten(clause):
    """Lowercase and turn hyphens into spaces, so 'product-quality' and
    'missing-items' match the same patterns as the spaced spellings."""
    return re.sub(r"[-–—]", " ", clause.lower())


def _polarity_markers(flat):
    """Every open/closed marker in the clause, with its position. A single
    clause can carry both - 'the resolved refund ticket and open app ticket' -
    so polarity is decided per mention, not per clause."""
    markers = [(m.start(), "unresolved") for m in re.finditer(UNRESOLVED_MARKERS, flat)]
    markers += [(m.start(), "resolved") for m in re.finditer(RESOLVED_MARKERS, flat)]
    return sorted(markers)


def _polarity(clause):
    """Clause-level polarity, used for counts ('three tickets remain open')."""
    markers = _polarity_markers(_flatten(clause))
    return markers[0][1] if markers else None


def _categories(clause):
    found, flat = [], _flatten(clause)
    for pattern, category in CATEGORY_WORDS:
        if re.search(pattern, flat) and category not in found:
            found.append(category)
    return found


def _category_mentions(clause):
    """Category words that refer to a TICKET, each with its own polarity.

    A clause like "the product-quality ticket is closed, and the 3-star review
    mentioning slow delivery does not qualify" contains two category words but
    only one ticket: 'delivery' belongs to the review. The clause is split into
    comma/and segments so each mention is read with its own noun and its own
    open/closed marker.
    """
    # A segment must carry its own evidence that it is about a ticket. Letting
    # later segments inherit the clause's ticket noun looked like free coverage
    # and invented two product-quality tickets out of "1- and 2-star reviews
    # about a wrong item, leakage and quality", because the comma split the
    # descriptors away from the word "review". Missing a claim is cheap here;
    # flagging true prose is not.
    seen, mentions = set(), []
    for segment in re.split(r",|\band\b", clause):
        flat = _flatten(segment)
        markers = _polarity_markers(flat)
        names_ticket = bool(re.search(r"ticket|complaint", flat))
        if re.search(r"review", flat) and not names_ticket:
            continue              # this segment is about a review, not a ticket
        if not names_ticket and not markers:
            continue              # nothing here says a ticket exists at all
        for pattern, category in CATEGORY_WORDS:
            if re.search(pattern, flat) and category not in seen:
                seen.add(category)
                mentions.append((category, markers[0][1] if markers else None))
    return mentions


# --- the facts a claim is checked against -----------------------------------

def user_facts(conn, user_id, as_of=None):
    """Everything the prose could legitimately be talking about, as of the
    analysis time - the same cutoff the agent's tools were given."""
    as_of = as_of or analysis_time(conn)
    cur = conn.cursor()
    tickets = [
        {
            "category": row[0],
            # Same rule as features.py and verifier.py: a ticket resolved after
            # the cutoff was still open at the cutoff.
            "unresolved": row[1] is None or row[1] >= as_of,
            "text": f"{row[2]} {row[3]}".lower(),
            "status": row[4].lower().replace("_", " "),
        }
        for row in cur.execute(
            """SELECT category, resolved_at, subject, description, status
               FROM support_tickets WHERE user_id=? AND created_at < ?""",
            (user_id, as_of),
        )
    ]
    reviews = [
        {"rating": row[0], "text": f"{row[1]} {row[2]}".lower()}
        for row in cur.execute(
            """SELECT rating, review_title, review_text
               FROM reviews WHERE user_id=? AND created_at < ?""",
            (user_id, as_of),
        )
    ]
    prev, recent = login_counts(conn, user_id, as_of)    # same windows as the model
    logins = {"prev": prev, "recent": recent}
    corpus = " ".join(t["text"] for t in tickets) + " " + " ".join(r["text"] for r in reviews)
    return {"tickets": tickets, "reviews": reviews, "logins": logins, "corpus": corpus}


def _count_tickets(facts, categories, polarity):
    rows = [t for t in facts["tickets"] if not categories or t["category"] in categories]
    if polarity == "unresolved":
        rows = [t for t in rows if t["unresolved"]]
    elif polarity == "resolved":
        rows = [t for t in rows if not t["unresolved"]]
    return len(rows)


# --- extraction + checking --------------------------------------------------

def _claim(kind, text, ok, detail, span=None):
    return {"kind": kind, "claim": text, "ok": ok, "detail": detail, "span": span}


def check_clause(clause, facts):
    """Turn one clause into zero or more checked claims."""
    claims, low, flat = [], clause.lower(), _flatten(clause)

    # "logins rose from 0 to 12" - both numbers and the direction.
    move = re.search(
        r"logins?\D{0,30}?(rose|increased|grew|fell|dropped|declined|decreased)"
        r"\s+from\s+(\d+)\s+to\s+(\d+)", low)
    if move:
        direction, said_prev, said_recent = move.group(1), int(move.group(2)), int(move.group(3))
        real_prev, real_recent = facts["logins"]["prev"], facts["logins"]["recent"]
        up = direction in ("rose", "increased", "grew")
        numbers_ok = (said_prev, said_recent) == (real_prev, real_recent)
        direction_ok = up == (said_recent > said_prev)
        claims.append(_claim(
            "login_move", move.group(0),
            numbers_ok and direction_ok,
            f"database says {real_prev} -> {real_recent}"
            + ("" if direction_ok else f"; '{direction}' contradicts the numbers given"),
            move.span()))


    # "there are no reviews", "no unresolved tickets" - a negative claim is
    # still a claim, and an agent inventing an absence is as wrong as one
    # inventing a complaint.
    for match in re.finditer(r"\bno\s+(reviews?|tickets?|complaints?)\b", flat):
        noun = match.group(1)
        real = len(facts["reviews"]) if noun.startswith("review") else len(facts["tickets"])
        claims.append(_claim("absence", match.group(0), real == 0, f"{real} on file"))

    # Normally the clause names a ticket, but "an unreceived refund and delayed
    # delivery remain unresolved" is the same claim without the noun, so a
    # category word plus an open/closed marker also qualifies.
    if re.search(r"\bticket|\bcomplaint", flat) or (
            _categories(clause) and _polarity_markers(flat)):
        polarity = _polarity(clause)
        categories = _categories(clause)
        label = "/".join(categories).lower() if categories else "any"
        qualifier = polarity or "any status"

        # Every count in the clause, each bound to its OWN head noun. "four
        # unresolved tickets covering two delivery delays" is two claims - a
        # total and a breakdown - and pooling the clause's categories into one
        # count would check neither of them.
        counted_spans = []
        for match in re.finditer(
                r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\b([\w\s]{0,40}?)\b(" +
                "|".join(HEAD_NOUNS) + r")\b", flat):
            word, middle, noun = match.group(1), match.group(2), match.group(3)
            said = int(word) if word.isdigit() else NUMBER_WORDS[word]
            if HEAD_NOUNS[noun]:                       # "two delivery delays"
                cats = [HEAD_NOUNS[noun]]
            else:                                      # "two refund tickets"
                cats = _categories(middle)
            real = _count_tickets(facts, cats, polarity)
            counted_spans.append(match.span())
            claims.append(_claim(
                "ticket_count", match.group(0).strip(), said == real,
                f"{real} {qualifier} {'/'.join(cats).lower() or 'any'} ticket(s) "
                f"in the database", match.span()))

        # Existence claims run alongside the counts: "a payment problem and a
        # missing refund" carries no number but still asserts those tickets.
        for category, mention_polarity in _category_mentions(clause) or [(None, polarity)]:
            real = _count_tickets(facts, [category] if category else [], mention_polarity)
            claims.append(_claim(
                "ticket_exists",
                f"{mention_polarity or 'any status'} {(category or 'any').lower()} ticket",
                real > 0, f"{real} in the database"))

        # "two waiting on the customer", "remains in progress"
        for status in ("waiting on the customer", "in progress", "open", "closed"):
            if status in flat:
                key = status.replace(" on the customer", " on customer")
                real = sum(1 for t in facts["tickets"] if t["status"] == key)
                claims.append(_claim(
                    "ticket_status", f"a ticket is '{status}'", real > 0,
                    f"{real} ticket(s) with that status"))

    # Review ratings: a range first ("1-2 stars"), then single ("3-star").
    consumed = []
    for match in re.finditer(r"(\d)\s*[-–—]\s*(\d)\s*[-\s]?stars?", low):
        lo, hi = int(match.group(1)), int(match.group(2))
        real = [r["rating"] for r in facts["reviews"] if lo <= r["rating"] <= hi]
        consumed.append(match.span())
        claims.append(_claim(
            "review_rating_range", match.group(0), bool(real),
            f"ratings on file: {sorted(r['rating'] for r in facts['reviews'])}", match.span()))
    # "1- and 2-star reviews" enumerates two ratings, not a range.
    for match in re.finditer(r"(\d)\s*[-–]?\s*and\s+(\d)\s*[-\s]?stars?", low):
        consumed.append(match.span())
        for rating in (int(match.group(1)), int(match.group(2))):
            claims.append(_claim(
                "review_rating", f"{rating}-star", any(r["rating"] == rating for r in facts["reviews"]),
                f"ratings on file: {sorted(r['rating'] for r in facts['reviews'])}", match.span()))
    for match in re.finditer(r"(\d)\s*[-\s]?stars?", low):
        if any(s <= match.start() < e for s, e in consumed):
            continue
        rating = int(match.group(1))
        real = any(r["rating"] == rating for r in facts["reviews"])
        claims.append(_claim(
            "review_rating", match.group(0), real,
            f"ratings on file: {sorted(r['rating'] for r in facts['reviews'])}", match.span()))

    # "two 2-star reviews" - how MANY reviews of a rating, which the rating
    # check above does not cover: it only asks whether one exists.
    #
    # Two traps, both of which produced false alarms before being closed:
    #   - "a 1-star review" has a number touching "star". That is the rating,
    #     not a count, so the count is refused a digit followed by "star".
    #   - "one positive review" counts reviews matching an adjective this code
    #     cannot evaluate. Counting every review instead turns a true sentence
    #     into a failure, so a count without a rating is not claimed at all -
    #     it goes to the unchecked-numbers report, where it belongs.
    for match in re.finditer(
            r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\b(?!\s*[-\s]?stars?\b)\s+"
            r"(\d)\s*[-\s]?star\s+(?:\w+\s+){0,2}?reviews?\b", flat):
        word, rating = match.group(1), match.group(2)
        said = int(word) if word.isdigit() else NUMBER_WORDS[word]
        real = sum(1 for r in facts["reviews"] if r["rating"] == int(rating))
        claims.append(_claim("review_count", match.group(0).strip(), said == real,
                             f"{real} review(s) rated {rating} on file", match.span()))

    # "logins remained steady at 7" - a claim about BOTH windows at once.
    steady = re.search(r"logins?\D{0,30}?(steady|unchanged|flat|the same)\D{0,10}?(\d+)", low)
    if steady:
        said = int(steady.group(2))
        prev, recent = facts["logins"]["prev"], facts["logins"]["recent"]
        claims.append(_claim(
            "login_steady", steady.group(0), prev == recent == said,
            f"database says {prev} -> {recent}", steady.span()))

    # What the complaint actually says. "damaged, stale, or leaking" is one
    # disjunctive claim - the agent is listing alternatives, not asserting all.
    topics = [t for t in TOPIC_PATTERNS if t in flat or t.rstrip("ing") in flat]
    if topics:
        supported = {t for t in topics if any(n in facts["corpus"] for n in TOPIC_PATTERNS[t])}
        if " or " in flat and len(topics) > 1:
            claims.append(_claim(
                "topic_any", " or ".join(topics), bool(supported),
                f"supported by the text: {sorted(supported) or 'none'}"))
        else:
            for topic in topics:
                claims.append(_claim(
                    "topic", topic, topic in supported,
                    "found in a ticket or review" if topic in supported
                    else "no ticket or review text mentions this"))
    return claims


def check_prose(text, facts):
    """Check one `reason`. Returns claims plus what went unchecked."""
    claims, unchecked_clauses, unchecked_numbers = [], 0, []
    for clause in _clauses(text):
        found = check_clause(clause, facts)
        if not found:
            unchecked_clauses += 1
        claims.extend(found)
        spans = [c["span"] for c in found if c["span"]]
        # Number WORDS count too: "two delivery delays" is a quantity claim,
        # and scanning only for digits hid it from this report entirely.
        for match in re.finditer(r"\d+|\b(?:" + "|".join(NUMBER_WORDS) + r")\b",
                                 _flatten(clause)):
            if not any(s <= match.start() < e for s, e in spans):
                unchecked_numbers.append(f"{match.group(0)} in \"{clause}\"")
    return {
        "claims": claims,
        "unchecked_clauses": unchecked_clauses,
        "unchecked_numbers": unchecked_numbers,
    }


def verify_prose(conn, predictions, as_of=None):
    """Check every prediction's `reason` against the database."""
    as_of = as_of or analysis_time(conn)
    total = passed = clauses = unchecked_clauses = 0
    failures, unchecked_numbers = {}, []

    for p in predictions:
        facts = user_facts(conn, p["user_id"], as_of)
        result = check_prose(p.get("reason", ""), facts)
        clauses += len(_clauses(p.get("reason", "")))
        unchecked_clauses += result["unchecked_clauses"]
        unchecked_numbers += [f"user {p['user_id']}: {n}" for n in result["unchecked_numbers"]]
        bad = [c for c in result["claims"] if not c["ok"]]
        total += len(result["claims"])
        passed += len(result["claims"]) - len(bad)
        if bad:
            failures[p["user_id"]] = bad

    return {
        "total_claims": total,
        "passed_claims": passed,
        "fidelity": passed / total if total else 0.0,
        "failures": failures,
        "clauses": clauses,
        "unchecked_clauses": unchecked_clauses,
        "coverage": (clauses - unchecked_clauses) / clauses if clauses else 0.0,
        "unchecked_numbers": unchecked_numbers,
    }


def main():
    import json

    with open(PREDICTIONS_PATH) as f:
        predictions = json.load(f)
    names = {p["user_id"]: p["full_name"] for p in predictions}

    conn = connect_readonly()
    result = verify_prose(conn, predictions)
    conn.close()

    print("=" * 74)
    print("PROSE VERIFIER  (the agent's sentences, not its schema)")
    print("=" * 74)
    for uid, bad in result["failures"].items():
        print(f"\n[UNSUPPORTED] user {uid} ({names[uid]}):")
        for c in bad:
            print(f"    - {c['kind']}: \"{c['claim']}\" -> {c['detail']}")

    print("\n" + "-" * 74)
    print(f"Customers checked:  {len(predictions)}")
    print(f"Claims extracted:   {result['total_claims']}")
    print(f"Claims supported:   {result['passed_claims']}")
    print(f"Prose fidelity:     {result['fidelity']:.2%}")
    print(f"Clause coverage:    {result['coverage']:.2%} "
          f"({result['clauses'] - result['unchecked_clauses']}/{result['clauses']} clauses "
          f"yielded a checkable claim)")
    if result["unchecked_numbers"]:
        print(f"Numbers not covered by any claim type: {len(result['unchecked_numbers'])}")
        for n in result["unchecked_numbers"][:5]:
            print(f"    - {n}")
    print("=" * 74)
    print("Coverage is reported because a clause nothing recognises is unchecked,")
    print("not correct. Fidelity is the score for what could be checked.")


if __name__ == "__main__":
    main()
