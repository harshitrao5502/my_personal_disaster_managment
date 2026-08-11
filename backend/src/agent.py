import logging
import os
import asyncio

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
from livekit.plugins import murf, silero, openai, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from memory import init_db, get_caller, save_caller, delete_caller

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

load_dotenv(".env.local")

init_db()

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

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

MEMORY (IMPORTANT — you MUST use these tools, don't just talk about remembering):
- At the very start of every call, before saying anything else beyond a greeting, call the lookup_caller tool using the CALLER_ID given to you below. Do this silently — don't tell the caller you're "checking a database."
- If lookup_caller returns known=True, greet them by name and reference what you last discussed. Example: "Namaste Ramesh, last time we spoke about your flood situation. How are things now?"
- If lookup_caller returns known=False, this is a new caller — proceed normally.
- Partway through the conversation, once you've learned something useful (name, location, household size, mobility needs), explicitly ask: "Is it okay if I remember this so I can help you faster next time?"
- If the caller says yes / haan / theek hai / any clear agreement, you MUST immediately call the remember_caller tool with everything you've learned so far, using the CALLER_ID. Do not just acknowledge verbally — actually call the tool.
- If they say no or don't clearly agree, do NOT call remember_caller.
- If a caller asks to be forgotten, call forget_caller and confirm it's done.

STYLE: Short sentences. Calm, steady pace. If the caller goes silent, gently check if they're still there instead of repeating yourself.
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
    name: str = None,
    language_preference: str = None,
    location: str = None,
    household_size: str = None,
    mobility_needs: str = None,
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

    save_caller(user_id, name=name, language_preference=language_preference, facts=facts)
    logger.info(f"[TOOL RESULT] remember_caller -> saved")
    return {"saved": True}


@function_tool()
async def forget_caller(context: RunContext, user_id: str):
    """Wipe a caller's saved record entirely. Call this if the caller asks to be
    forgotten or wants their data deleted."""
    logger.info(f"[TOOL CALLED] forget_caller(user_id={user_id!r})")
    delete_caller(user_id)
    return {"forgotten": True}


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
                logger.warning(f"[TOOL ERROR] District '{district}' not found on OpenWeatherMap")
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

            logger.info(f"[TOOL RESULT] get_weather_alert_status -> {formatted_payload}")
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


class Assistant(Agent):
    def __init__(self, caller_user_id: str, custom_instructions: str = "") -> None:
        full_instructions = (
            SYSTEM_PROMPT
            + custom_instructions
            + f'\n\nCALLER_ID: The current caller\'s user_id is "{caller_user_id}". '
            f"Use this exact value whenever you call lookup_caller, remember_caller, "
            f"or forget_caller — never ask the caller for an ID."
        )
        super().__init__(
            instructions=full_instructions,
            tools=[lookup_caller, remember_caller, forget_caller, get_weather_alert_status],
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

    await session.start(
        agent=Assistant(caller_user_id=caller_user_id, custom_instructions=custom_instructions),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)