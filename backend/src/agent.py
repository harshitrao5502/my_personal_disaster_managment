import asyncio
import json
import logging
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

import httpx
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    room_io,
    tokenize,
)
from livekit.plugins import deepgram, murf, noise_cancellation, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from memory import (
    delete_caller,
    get_call_stats,
    get_caller,
    init_db,
    mark_call_outcome,
    save_caller,
    start_call_record,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

load_dotenv(".env.local")

init_db()

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
DISCORD_ESCALATION_WEBHOOK_URL = os.environ.get("DISCORD_ESCALATION_WEBHOOK_URL")

# System prompt configured for English, Hindi, and Hinglish adaptation
SYSTEM_PROMPT = """
IDENTITY: You are Raksha (रक्षा in Hindi), a disaster-response voice assistant for people affected by floods, cyclones, or other emergencies in India. You are not a government agency and have no official authority. Always spell your name as रक्षा in Hindi, never राखा.

OBJECTIVES: Help callers (1) find the nearest relief shelter, (2) understand next safety steps, (3) know how to report a missing person. A successful call ends with the caller having a clear, honest next action.

KNOWLEDGE: You know general disaster-safety guidance. You do NOT have real-time shelter locations, capacity, or safety-clearance data yet. Say so plainly rather than guessing.
- You now have access to get_weather_alert_status, which fetches real current weather
  conditions for a named district/city using OpenWeatherMap. When a caller asks about weather, rain, flood
  risk, or current safety conditions somewhere, call this tool rather than guessing.
  Narrate the result naturally (temperature, rainfall, conditions) — never read out
  raw numbers/JSON structure. Always mention this is current weather data, not an
  official government evacuation order or alert. If the tool returns an error, say so
  honestly and suggest an alternative (IMD's site, local news, emergency services) —
  never invent a plausible-sounding answer.

LANGUAGE & SCRIPT:
- Always reply in the exact language style the caller used in their last message.
- If they speak English, reply in plain English.
- If they speak Hindi, reply in natural Hindi, always in Devanagari script (नमस्ते), never romanized (never "namaste").
- If they code-mix English and Hindi (Hinglish), reply in Hinglish — do not default to pure English unless the caller does.
- Never translate your reply into a different language than what they just used.

GUARDRAILS:
- You CAN and SHOULD give standard, well-established safety actions (earthquake: drop, cover, hold on; flood: move to higher ground away from water; fire: stay low, cover nose/mouth) — this is public safety knowledge, not a guess.
- You must NEVER phrase anything as an official order or an all-clear: don't say "you must evacuate now" or "you are safe to stay" — instead say what's generally advised and why, letting them decide.
- Never claim real-time facts you don't have: a shelter's exact location, capacity, current road status, or an official evacuation order in effect right now. Say plainly you don't have that live data.
- If they can reach emergency services, mention it as one option — not the only answer to every question.
- Never guess at a phone number or address you're not certain of.
- Do NOT trigger create_escalation for general, educational, or hypothetical safety questions. ONLY ask for permission to escalate if the caller explicitly states that they or someone with them is currently in active, real-time danger. You MUST wait for their explicit verbal consent before executing the create_escalation tool.

MEMORY (IMPORTANT — you MUST use these tools, don't just talk about remembering):
- At the very start of every call, before saying anything else beyond a greeting, call the lookup_caller tool using the CALLER_ID given to you below. Do this silently — don't tell the caller you're "checking a database."
- If lookup_caller returns known=True, greet them by name and reference what you last discussed. Example: "Namaste Ramesh, last time we spoke about your flood situation. How are things now?"
- If lookup_caller returns known=False, this is a new caller — proceed normally.
- Partway through the conversation, once you've learned something useful (name, location, household size, mobility needs), explicitly ask: "Is it okay if I remember this so I can help you faster next time?"
- If the caller says yes / haan / theek hai / any clear agreement, you MUST immediately call the remember_caller tool with everything you've learned so far, using the CALLER_ID. Do not just acknowledge verbally — actually call the tool.
- If they say no or don't clearly agree, do NOT call remember_caller.
- If a caller asks to be forgotten, call forget_caller and confirm it's done.

ESCALATION (CRITICAL — you MUST follow these instructions when escalation is needed):
- You MUST recognize two specific escalation triggers:
  1. The caller is trapped, injured, or in immediate physical danger where standard safety advice is not sufficient and they need urgent local help.
  2. The caller is reporting a missing person.
- When either trigger is met, do NOT try to solve it alone. Recognize this needs human or authority involvement.
- BEFORE calling the create_escalation tool, you MUST explicitly explain to the caller what information you want to send to a human responder and ask for their consent.
  - You MUST verbally say a concrete phrase: "I want to send your name, that you are [trapped/injured/missing], and your follow-up preferences to a human responder — is that okay?" (or equivalent in Hindi/Hinglish depending on user language).
  - You MUST wait for their response. Do NOT call the create_escalation tool until they have given clear consent in the immediately preceding turn.
- If the caller says yes / haan / please do / any clear agreement, you MUST immediately call the create_escalation tool with the summarized details.
- If the caller says no or does not clearly agree, do NOT call create_escalation.
- You MUST NOT invent, guess, or assume follow-up preferences (e.g. do not assume "phone call" unless stated).
  - You MUST ask the caller: "How should the responders follow up with you (e.g. call back, text)?" or check their known preferences.
  - If they do not specify, you MUST pass "not specified" to the tool — never invent a preference.
- Never include sensitive private information (passwords, OTPs, PINs, account numbers) in the escalation summary, even if the caller mentioned them.
- Once you call the tool, provide the caller with the reference_id returned by the tool (e.g., "A human responder has been notified with reference ID <id>. They'll follow up as soon as possible.") and explain next steps honestly without overpromising immediate response unless it's guaranteed.
- If the conversation is normal (e.g. asking general safety questions) and does not meet the two triggers, do NOT call create_escalation.

HANDOFF (IMPORTANT — you MUST use this tool when shelter logistics are requested):
- If the caller asks specific, logistical questions about relief shelters (e.g. what to bring, what to expect, check-in/registration procedures, accessibility for disabled/infants, or duration of stay), you MUST transfer them to the specialist.
- BEFORE calling the transfer_to_shelter_specialist tool, you MUST verbally announce to the caller: "I'll connect you to our shelter information specialist." and then immediately call the tool.
- Do NOT try to answer shelter logistics questions yourself if they are detailed or specific.

STYLE: Short sentences. Calm, steady pace. If the caller goes silent, gently check if they're still there instead of repeating yourself.
"""

SHELTER_SPECIALIST_PROMPT = """
IDENTITY: You are the Shelter Information Specialist for Raksha (रक्षा in Hindi). You are a separate assistant focused ONLY on relief shelters. Always spell your name as रक्षा in Hindi, never राखा.

OBJECTIVES: Help callers understand relief shelters:
1. What to expect at a shelter (facilities, food, sanitation, safety).
2. What to bring (medicine, IDs, essentials).
3. How registration and check-in works.
4. Accessibility for the elderly, disabled, and infants.
5. How long people typically need to stay.

LANGUAGE & SCRIPT:
- Always reply in the exact language style the caller used in their last message (English, Hindi in Devanagari script, or Hinglish).

HANDOFF (IMPORTANT — you MUST use this tool to return to the main assistant):
- If the caller asks about general weather alerts, general safety guidance (e.g. earthquake safety steps, flood safety precautions), or emergency escalation, you MUST hand them back to the main assistant.
- BEFORE calling the transfer_to_main_agent tool, you MUST verbally announce to the caller: "I'll connect you back to our main assistant for that." and then immediately call the tool.

STYLE: Short sentences. Calm, steady, informative tone. Start the conversation with your identity introduction: "Hi, I'm the shelter information specialist — I can help with what to expect and how to prepare."
"""


@function_tool()
async def lookup_caller(context: RunContext, user_id: str):
    """Look up a returning caller by their user_id to check if we already know them
    and what we previously learned. Call this at the very start of the call, before
    greeting the caller in detail."""
    logger.info(f"[TOOL CALLED] lookup_caller(user_id={user_id!r})")
    caller = get_caller(user_id)
    logger.info(f"[TOOL RESULT] lookup_caller -> {caller}")
    if caller is None:
        return {"known": False}
    return {"known": True, **caller}


@function_tool()
async def remember_caller(
    context: RunContext,
    user_id: str,
    name: Optional[str] = None,
    language_preference: Optional[str] = None,
    location: Optional[str] = None,
    household_size: Optional[str] = None,
    mobility_needs: Optional[str] = None,
):
    """Save or update what you've learned about this caller. ONLY call this AFTER
    the caller has explicitly agreed to let you remember this information."""
    logger.info(
        f"[TOOL CALLED] remember_caller(user_id={user_id!r}, name={name!r}, "
        f"location={location!r}, household_size={household_size!r}, mobility_needs={mobility_needs!r})"
    )
    facts = {}
    if location:
        facts["location"] = location
    if household_size:
        facts["household_size"] = household_size
    if mobility_needs:
        facts["mobility_needs"] = mobility_needs

    save_caller(
        user_id, name=name, language_preference=language_preference, facts=facts
    )
    logger.info("[TOOL RESULT] remember_caller -> saved")
    return {"saved": True}


@function_tool()
async def forget_caller(context: RunContext, user_id: str):
    """Wipe a caller's saved record entirely. Call this if the caller asks to be
    forgotten or wants their data deleted."""
    logger.info(f"[TOOL CALLED] forget_caller(user_id={user_id!r})")
    delete_caller(user_id)
    return {"forgotten": True}


@function_tool()
async def create_escalation(
    context: RunContext,
    user_id: str,
    who: str,
    what_happened: str,
    what_advised: str,
    urgency: str = "medium",
    language_preference: str = "English",
    follow_up_method: str = "not specified",
):
    """Create a human responder escalation request.

    STRICT GUARDRAIL: You must NEVER call this tool automatically just because an emergency or disaster scenario is mentioned.
    If the caller is asking hypothetical, general, or educational safety questions, DO NOT call this tool.
    You MUST first verbally ask the caller: 'May I share your details with a human responder?'
    ONLY call this tool AFTER the caller explicitly says 'yes', 'haan', 'theek hai', or gives clear verbal consent.
    """
    logger.info(
        f"[TOOL CALLED] create_escalation(user_id={user_id!r}, who={who!r}, what_happened={what_happened!r}, "
        f"what_advised={what_advised!r}, urgency={urgency!r}, language={language_preference!r}, follow_up={follow_up_method!r})"
    )

    ref_id = str(uuid.uuid4())[:8]

    if not DISCORD_ESCALATION_WEBHOOK_URL:
        logger.warning(
            "[TOOL ERROR] DISCORD_ESCALATION_WEBHOOK_URL is not set in environment"
        )
        return {
            "error": "Human responder system is currently offline. Tell the caller honestly that you "
            "cannot connect to the escalation system right now, and suggest they call emergency services immediately.",
            "reference_id": ref_id,
            "success": False,
        }

    payload = {
        "embeds": [
            {
                "title": "🚨 Raksha Emergency Escalation",
                "color": 15548997
                if urgency.lower() in ["emergency", "high"]
                else 16753920,
                "fields": [
                    {"name": "Reference ID", "value": f"`{ref_id}`", "inline": True},
                    {"name": "User ID / Caller ID", "value": user_id, "inline": True},
                    {"name": "Urgency", "value": urgency.upper(), "inline": True},
                    {"name": "Who needs help", "value": who, "inline": True},
                    {
                        "name": "Follow-up Method",
                        "value": follow_up_method,
                        "inline": True,
                    },
                    {
                        "name": "Language Preference",
                        "value": language_preference,
                        "inline": True,
                    },
                    {"name": "What Happened", "value": what_happened, "inline": False},
                    {
                        "name": "Safety Guidance Already Advised",
                        "value": what_advised,
                        "inline": False,
                    },
                ],
                "footer": {"text": "Raksha Disaster Response Assistant"},
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(DISCORD_ESCALATION_WEBHOOK_URL, json=payload)
            resp.raise_for_status()
            context.userdata["call_successful"] = True
            logger.info(f"[TOOL RESULT] create_escalation -> success (ref_id={ref_id})")
            return {"success": True, "reference_id": ref_id}
    except Exception as e:
        logger.error(f"[TOOL ERROR] Failed to send Discord webhook: {e}")
        return {
            "error": f"Failed to deliver escalation notification: {e}. Suggest calling emergency services directly.",
            "reference_id": ref_id,
            "success": False,
        }


@function_tool()
async def get_weather_alert_status(context: RunContext, district: str):
    """Check current weather conditions for an Indian district or city to assess
    disaster risk — heavy rainfall, flood risk, heatwave, etc. Call this whenever
    the caller asks about current weather, flood risk, or safety conditions in a
    specific place. Always tell the caller this is current data and mention it's
    not an official government alert."""
    logger.info(f"[TOOL CALLED] get_weather_alert_status(district={district!r})")

    if not OPENWEATHER_API_KEY:
        logger.warning("[TOOL ERROR] OPENWEATHER_API_KEY not set in .env.local")
        return {
            "error": "Weather data service is not configured right now. Tell the caller you "
            "can't check live conditions at the moment and suggest they check IMD's "
            "official site or local news for weather alerts."
        }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "q": f"{district},IN",
                    "appid": OPENWEATHER_API_KEY,
                    "units": "metric",
                },
            )

            if resp.status_code == 404:
                logger.warning(
                    f"[TOOL ERROR] District '{district}' not found on OpenWeatherMap"
                )
                return {
                    "error": f"Could not find a weather station matching '{district}'. "
                    "Tell the caller you don't have data for that exact place and ask "
                    "if there's a nearby bigger town or city you could check instead."
                }

            resp.raise_for_status()
            data = resp.json()

            city_name = data.get("name", district)
            temp = data.get("main", {}).get("temp")
            humidity = data.get("main", {}).get("humidity")
            weather_desc = data.get("weather", [{}])[0].get("description", "clear")
            wind_speed = data.get("wind", {}).get("speed")

            formatted_payload = {
                "source": "OpenWeatherMap API — live atmospheric data, not an official government evacuation alert",
                "city": city_name,
                "temperature_celsius": temp,
                "humidity_percent": humidity,
                "condition": weather_desc,
                "wind_speed_mps": wind_speed,
            }

            logger.info(
                f"[TOOL RESULT] get_weather_alert_status -> {formatted_payload}"
            )
            context.userdata["call_successful"] = True
            return formatted_payload

    except httpx.TimeoutException:
        logger.warning("[TOOL ERROR] OpenWeatherMap API timed out")
        return {
            "error": "The weather service timed out. Tell the caller honestly that "
            "you couldn't reach live weather data right now, and suggest checking "
            "IMD's official site, local news, or calling local authorities for "
            "current conditions. Do not guess or make up numbers."
        }
    except Exception as e:
        logger.warning(f"[TOOL ERROR] OpenWeatherMap API failed: {e}")
        return {
            "error": "The weather service is unavailable right now. Tell the caller "
            "honestly that live data isn't reachable and suggest an alternative "
            "source. Do not guess or make up numbers."
        }


@function_tool()
async def transfer_to_shelter_specialist(context: RunContext, user_id: str):
    """Transfer the call to the Shelter Information Specialist.
    Call this tool ONLY when the caller asks specific questions about relief shelters:
    what to bring, what to expect, check-in/registration procedures,
    accessibility for elderly/disabled/infants, or how long to stay.
    Do NOT call this for weather, general safety, or emergency escalation queries."""
    logger.info(f"[TOOL CALLED] transfer_to_shelter_specialist(user_id={user_id!r})")
    specialist = ShelterSpecialist(caller_user_id=user_id)
    context.session.update_agent(specialist)
    logger.info(
        "[TOOL RESULT] transfer_to_shelter_specialist -> Switched active agent to ShelterSpecialist"
    )
    return {"status": "handoff_initiated", "agent": "ShelterSpecialist"}


@function_tool()
async def transfer_to_main_agent(context: RunContext, user_id: str):
    """Transfer the call back to the main Raksha Assistant.
    Call this tool when the user changes the topic to general weather alerts, general safety guidance,
    emergency escalation, or asks a question outside relief shelter logistics."""
    logger.info(f"[TOOL CALLED] transfer_to_main_agent(user_id={user_id!r})")
    main_agent = Assistant(caller_user_id=user_id)
    context.session.update_agent(main_agent)
    logger.info(
        "[TOOL RESULT] transfer_to_main_agent -> Switched active agent back to Assistant"
    )
    return {"status": "handoff_initiated", "agent": "Assistant"}


class ShelterSpecialist(Agent):
    def __init__(self, caller_user_id: str) -> None:
        full_instructions = (
            SHELTER_SPECIALIST_PROMPT
            + f'\n\nCALLER_ID: The current caller\'s user_id is "{caller_user_id}". '
            f"Use this exact value whenever you call transfer_to_main_agent — never ask the caller for an ID."
        )
        super().__init__(
            instructions=full_instructions,
            tools=[transfer_to_main_agent],
        )


class Assistant(Agent):
    def __init__(self, caller_user_id: str, custom_instructions: str = "") -> None:
        full_instructions = (
            SYSTEM_PROMPT
            + custom_instructions
            + f'\n\nCALLER_ID: The current caller\'s user_id is "{caller_user_id}". '
            f"Use this exact value whenever you call lookup_caller, remember_caller, "
            f"forget_caller, create_escalation, or transfer_to_shelter_specialist — never ask the caller for an ID."
        )
        super().__init__(
            instructions=full_instructions,
            tools=[
                lookup_caller,
                remember_caller,
                forget_caller,
                get_weather_alert_status,
                create_escalation,
                transfer_to_shelter_specialist,
            ],
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    await ctx.connect()

    participant = await ctx.wait_for_participant()
    caller_user_id = participant.identity
    logger.info(f"[SESSION] caller_user_id resolved as: {caller_user_id!r}")

    # Detect if this connection originates from a SIP/telephony call
    is_sip_call = participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP

    custom_instructions = ""
    if is_sip_call:
        custom_instructions = """
        \n\nOUTBOUND CALL INSTRUCTIONS: You are placing an automated proactive safety welfare check call.
        If the user says "stop", "disconnect", or requests not to be called again, immediately say
        "Understood, ending the call now. Stay safe." and wrap up the conversation.
        """

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=openai.LLM.with_openrouter(
            model="meta-llama/llama-3.3-70b-instruct",
        ),
        tts=murf.TTS(
            voice="Anisha",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    session.userdata = {"call_successful": False}

    @session.on("close")
    def _on_session_close(event):
        outcome = (
            "success" if session.userdata.get("call_successful", False) else "failed"
        )
        logger.info(f"[SESSION CLOSE] Call {ctx.job.id} ended. Outcome: {outcome}")
        mark_call_outcome(ctx.job.id, outcome)

    # Trigger proactive greeting AFTER giving the SIP media stream a moment to establish
    @session.on("agent_started")
    def _on_agent_started():
        if is_sip_call:

            async def send_delayed_greeting():
                # Wait 1.5 seconds for the Linphone RTP audio socket to fully open
                await asyncio.sleep(1.5)
                opening_message = (
                    "Namaste Rahul, this is Raksha, an automated safety check-in assistant. "
                    "I am calling because our records show you have a disabled grandfather and a pet dog in a flood-risk zone, and I want to ensure you are safe. "
                    "Say 'stop' at any time to end this call and opt out. Are you both okay right now?"
                )
                logger.info("[SIP] Sending outbound welfare check greeting...")
                await session.say(opening_message)

            ctx.create_task(send_delayed_greeting())

    start_call_record(
        call_id=ctx.job.id,
        user_id=caller_user_id,
        channel="sip" if is_sip_call else "browser",
    )

    await session.start(
        agent=Assistant(
            caller_user_id=caller_user_id, custom_instructions=custom_instructions
        ),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


class DashboardHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format_str, *args):
        # Prevent console logging spam
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/dashboard/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                stats = get_call_stats()
                self.wfile.write(json.dumps(stats).encode("utf-8"))
            except Exception as e:
                logger.error(f"[DASHBOARD API ERROR] {e}")
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def start_dashboard_server():
    try:
        server_address = ("0.0.0.0", 8000)
        httpd = HTTPServer(server_address, DashboardHTTPHandler)
        logger.info("[DASHBOARD] Started stats API server on port 8000")
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
    except Exception as e:
        logger.error(f"[DASHBOARD] Failed to start dashboard server: {e}")


if __name__ == "__main__":
    start_dashboard_server()
    cli.run_app(server)
