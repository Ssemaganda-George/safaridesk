"""Safari enquiry-to-booking: a deterministic pipeline of specialist agents.

Intake -> Planner (grounded) -> Pricing -> Reply (human approval).
The workflow skeleton is code; the LLM only does the thinking inside each step.
"""
import os

from google.adk.agents import Agent, SequentialAgent
from google.adk.tools.agent_tool import AgentTool

from .guardrails import input_guard, tool_audit, tool_policy
from .tools import (apply_discount, check_permit_availability, convert_currency,
                    get_quote, search_knowledge_base, submit_for_approval)

MODEL = os.getenv("MODEL", "gemini-2.5-flash")


def _grounding_tools():
    """Local KB by default (works offline on stage). Set VERTEX_DATASTORE_ID for Vertex AI Search."""
    datastore = os.getenv("VERTEX_DATASTORE_ID")
    if not datastore:
        return [search_knowledge_base]
    from google.adk.tools import VertexAiSearchTool
    search_agent = Agent(
        name="vertex_search_agent", model=MODEL,
        instruction="Answer only from the search results and name the source of each fact.",
        tools=[VertexAiSearchTool(data_store_id=datastore)])
    return [AgentTool(agent=search_agent)]


COMMON = dict(model=MODEL, before_tool_callback=tool_policy, after_tool_callback=tool_audit)

intake_agent = Agent(
    name="intake_agent",
    description="Extracts structured trip details from a tourist message.",
    instruction=(
        "You are the intake agent for a Uganda safari operator. Read the tourist message and output a compact "
        "JSON object with these keys: intent (enquiry or other), destinations, month, nights, adults, "
        "budget_tier (budget, mid or luxury), wants_gorillas (true or false), missing_info (list). "
        "Output JSON only. Never invent values: use null and list them in missing_info."),
    output_key="trip_request", **COMMON)

planner_agent = Agent(
    name="planner_agent",
    description="Builds a day-by-day itinerary grounded in verified sources.",
    instruction=(
        "You are the itinerary planner. Trip request: {trip_request}\n"
        "Rules: use ONLY places and facts returned by the knowledge search tool, and name the source of each. "
        "If gorillas are wanted, call check_permit_availability. If status is unverified or not available, say "
        "so plainly and suggest alternatives. Never promise a permit that was not verified. "
        "Output a short day-by-day plan."),
    tools=_grounding_tools() + [check_permit_availability],
    output_key="itinerary", **COMMON)

pricing_agent = Agent(
    name="pricing_agent",
    description="Prices the itinerary using the rates tools.",
    instruction=(
        "You are the pricing agent. Trip request: {trip_request}\nItinerary: {itinerary}\n"
        "Call get_quote with the right numbers (use 0 gorilla permits if they are not available). "
        "Offer a discount only if the tourist asked for one, and never invent discount reasons. "
        "If the tourist wants another currency, call convert_currency. Summarise the quote."),
    tools=[get_quote, apply_discount, convert_currency],
    output_key="quote_summary", **COMMON)

reply_agent = Agent(
    name="reply_agent",
    description="Drafts the customer reply and queues it for human approval.",
    instruction=(
        "You are the reply agent. Itinerary: {itinerary}\nQuote: {quote_summary}\n"
        "Write a warm, concise email reply to the tourist with the itinerary, price, and any caveats. "
        "You cannot confirm bookings. Call submit_for_approval with a short summary, then tell the tourist a "
        "team member will confirm availability and next steps."),
    tools=[submit_for_approval],
    output_key="final_reply", **COMMON)

root_agent = SequentialAgent(
    name="safari_desk",
    description="Turns a tourist enquiry into a grounded, priced, human-approved reply.",
    sub_agents=[intake_agent, planner_agent, pricing_agent, reply_agent],
    before_agent_callback=input_guard)
