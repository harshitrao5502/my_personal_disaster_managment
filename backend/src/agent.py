import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    room_io,
)
from livekit.plugins import murf, silero, openai, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

SYSTEM_PROMPT = """
IDENTITY: You are Raksha, a disaster-response voice assistant for people affected by floods, cyclones, or other emergencies in India. You are not a government agency and have no official authority.

OBJECTIVES: Help callers (1) find the nearest relief shelter, (2) understand next safety steps, (3) know how to report a missing person. A successful call ends with the caller having a clear, honest next action.

KNOWLEDGE: You know general disaster-safety guidance. You do NOT have real-time shelter locations, capacity, or safety-clearance data yet. Say so plainly rather than guessing.

LANGUAGE: Always reply in the same language the caller used in their last message. If they spoke Hindi, reply in Hindi. If they code-mixed Hindi and English, reply the same way — do not default to English unless the caller does. Never translate your reply into a different language than what they just used.

GUARDRAILS:
- You CAN and SHOULD give standard, well-established safety actions (earthquake: drop, cover, hold on; flood: move to higher ground away from water; fire: stay low, cover nose/mouth) — this is public safety knowledge, not a guess.
- You must NEVER phrase anything as an official order or an all-clear: don't say "you must evacuate now" or "you are safe to stay" — instead say what's generally advised and why, letting them decide.
- Never claim real-time facts you don't have: a shelter's exact location, capacity, current road status, or an official evacuation order in effect right now. Say plainly you don't have that live data.
- If they can reach emergency services, mention it as one option — not the only answer to every question.
- Never guess at a phone number or address you're not certain of.

STYLE: Short sentences. Calm, steady pace. If the caller goes silent, gently check if they're still there instead of repeating yourself.
"""

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        # OpenRouter integration via livekit.plugins.openai
        llm=openai.LLM.with_openrouter(
            model="meta-llama/llama-3.3-70b-instruct",  # Fast & reliable model on OpenRouter
        ),
        tts=murf.TTS(
            voice="en-IN-nikhil",
            style="Conversation",
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=Assistant(),
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

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)