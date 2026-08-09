import logging

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

# System prompt configured for English, Hindi, and Hinglish adaptation
SYSTEM_PROMPT = """
IDENTITY: You are Raksha, a disaster-response voice assistant for people affected by floods, cyclones, or other emergencies in India. You are not a government agency and have no official authority.

OBJECTIVES: Help callers (1) find the nearest relief shelter, (2) understand next safety steps, (3) know how to report a missing person. A successful call ends with the caller having a clear, honest next action.

KNOWLEDGE: You know general disaster-safety guidance. You do NOT have real-time shelter locations, capacity, or safety-clearance data yet. Say so plainly rather than guessing.

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


class Assistant(Agent):
    def __init__(self, caller_user_id: str) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT
            + f'\n\nCALLER_ID: The current caller\'s user_id is "{caller_user_id}". '
            f"Use this exact value whenever you call lookup_caller, remember_caller, "
            f"or forget_caller — never ask the caller for an ID.",
            tools=[lookup_caller, remember_caller, forget_caller],
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

    # Wait for the caller's participant to be present, then grab their stable identity
    participant = await ctx.wait_for_participant()
    caller_user_id = participant.identity
    logger.info(f"[SESSION] caller_user_id resolved as: {caller_user_id!r}")

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

    await session.start(
        agent=Assistant(caller_user_id=caller_user_id),
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