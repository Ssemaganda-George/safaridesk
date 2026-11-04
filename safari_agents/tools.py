"""Mock tools for the safari enquiry-to-booking demo.

ALL DATA HERE IS DEMO DATA. Verify real permit prices and availability before
presenting them as fact. Swap each function for your real API when ready.
"""
import json
import pathlib
import uuid

from google.adk.tools import ToolContext

KB = [
    {"source": "kb/bwindi.md",
     "text": "Bwindi Impenetrable National Park is the main gorilla trekking destination in Uganda. "
             "Permits are issued by Uganda Wildlife Authority (UWA) and must be booked in advance. "
             "Minimum trekking age is 15. Allow a full day per trek."},
    {"source": "kb/murchison.md",
     "text": "Murchison Falls National Park: boat cruise to the base of the falls, game drives north of the Nile, "
             "and a ferry crossing at Paraa. Plan 2 nights minimum."},
    {"source": "kb/qenp.md",
     "text": "Queen Elizabeth National Park: Kazinga Channel launch cruise, and tree-climbing lions in the Ishasha sector."},
    {"source": "kb/jinja.md",
     "text": "Jinja: source of the Nile, white-water rafting near Bujagali, bungee, and cultural tours. Rafting is weather dependent."},
    {"source": "kb/seasons.md",
     "text": "Drier seasons are June to August and December to February. March to May and September to November are wetter, "
             "so trails and roads can be harder."},
]

# (park, month) -> permits remaining. Missing key = we cannot verify.
PERMITS = {("bwindi", "june"): 6, ("bwindi", "july"): 0, ("bwindi", "august"): 2}

TIER_RATE_USD_PP_NIGHT = {"budget": 90, "mid": 180, "luxury": 400}
GORILLA_PERMIT_USD = 800        # demo value, verify with UWA
VEHICLE_PER_DAY_USD = 150
FX = {"USD": 1.0, "UGX": 3700.0, "EUR": 0.92}

APPROVALS_FILE = pathlib.Path("approvals.json")


def search_knowledge_base(query: str) -> dict:
    """Search the verified tourism knowledge base. Only state facts returned here.

    Args:
        query: Plain-language question or keywords, e.g. "gorilla trekking Bwindi".
    """
    words = {w.lower().strip(".,?") for w in query.split() if len(w) > 2}
    scored = []
    for doc in KB:
        hits = sum(1 for w in words if w in doc["text"].lower())
        if hits:
            scored.append((hits, doc))
    scored.sort(key=lambda x: -x[0])
    results = [d for _, d in scored[:3]]
    return {"results": results} if results else {"results": [], "note": "No verified source found."}


def check_permit_availability(park: str, month: str, permits_needed: int) -> dict:
    """Check gorilla permit availability. Never assume availability if status is unverified.

    Args:
        park: Park name, e.g. "bwindi".
        month: Month name, e.g. "june".
        permits_needed: Number of permits required.
    """
    key = (park.lower().strip(), month.lower().strip())
    if key not in PERMITS:
        return {"status": "unverified", "available": None,
                "note": "Cannot verify. Do not promise a permit."}
    remaining = PERMITS[key]
    return {"status": "verified", "available": remaining >= permits_needed, "remaining": remaining}


def get_quote(adults: int, nights: int, tier: str, gorilla_permits: int,
              tool_context: ToolContext) -> dict:
    """Build a price quote in USD.

    Args:
        adults: Number of adult travellers.
        nights: Number of nights.
        tier: One of "budget", "mid", "luxury".
        gorilla_permits: Number of gorilla permits to include (0 if none or unavailable).
    """
    tier = tier.lower()
    if tier not in TIER_RATE_USD_PP_NIGHT:
        return {"status": "error", "message": "tier must be budget, mid or luxury"}
    lines = {
        "accommodation": adults * nights * TIER_RATE_USD_PP_NIGHT[tier],
        "vehicle_and_guide": (nights + 1) * VEHICLE_PER_DAY_USD,
        "gorilla_permits": gorilla_permits * GORILLA_PERMIT_USD,
    }
    quote = {"quote_id": f"Q-{uuid.uuid4().hex[:6].upper()}", "lines_usd": lines,
             "total_usd": sum(lines.values()), "discount_pct": 0}
    tool_context.state["quote"] = quote
    return quote


def apply_discount(percent: float, reason: str, tool_context: ToolContext) -> dict:
    """Apply a discount to the current quote. Policy limits are enforced outside the model.

    Args:
        percent: Discount percentage, e.g. 5.
        reason: Why the discount is being applied.
    """
    quote = tool_context.state.get("quote")
    if not quote:
        return {"status": "error", "message": "No quote yet."}
    quote["discount_pct"] = percent
    quote["total_usd"] = round(sum(quote["lines_usd"].values()) * (1 - percent / 100), 2)
    tool_context.state["quote"] = quote
    return {"status": "applied", "quote": quote, "reason": reason}


def convert_currency(amount_usd: float, to: str) -> dict:
    """Convert a USD amount to UGX or EUR.

    Args:
        amount_usd: Amount in USD.
        to: Target currency code (UGX, EUR, USD).
    """
    rate = FX.get(to.upper())
    if rate is None:
        return {"status": "error", "message": "Unsupported currency"}
    return {"amount": round(amount_usd * rate, 2), "currency": to.upper(), "note": "indicative rate"}


def submit_for_approval(summary: str, tool_context: ToolContext) -> dict:
    """Queue the quote for a human to approve. The agent can NOT confirm bookings itself.

    Args:
        summary: One-paragraph summary of the quote for the human reviewer.
    """
    quote = tool_context.state.get("quote", {})
    queue = json.loads(APPROVALS_FILE.read_text()) if APPROVALS_FILE.exists() else []
    ticket = {"ticket": f"T-{uuid.uuid4().hex[:5].upper()}", "quote": quote,
              "summary": summary, "status": "pending"}
    queue.append(ticket)
    APPROVALS_FILE.write_text(json.dumps(queue, indent=2))
    return {"status": "pending_human_approval", "ticket": ticket["ticket"]}
