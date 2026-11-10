"""Voice quick-add agent for Temple CRM.

Runs on LiveKit Cloud (see README.md in this folder). The volunteer's browser joins a room,
this agent listens and talks, and once the volunteer confirms out loud it asks the browser
to save the people (RPC "save_newcomers"). The agent has no database access.
"""
import json
import logging

from livekit import rtc
from pydantic import BaseModel
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, cli, function_tool, get_job_context
from livekit.plugins import silero

logger = logging.getLogger("temple-voice-agent")

INSTRUCTIONS = """\
You are the voice assistant for a temple's volunteer welcome desk. A volunteer talks to you to
add newcomers they just met. For each person you need a full name and a phone number.

How to behave:
- Be brief and warm. Greet with one short sentence and ask who they met.
- The volunteer may ramble, give several people at once, or correct themselves mid-sentence
  ("it's Arjun, sorry, Arjun Nair"). Always use the latest correction. Keep a running list.
- If a name or phone number is missing for someone, ask for just that.
- Before saving, read EVERYTHING back: each full name, and each phone number digit by digit in
  groups (e.g. "five one two, five five five, zero one four two"). Then ask: "Should I save these?"
- Only call save_newcomers after the volunteer clearly says yes. If they correct anything,
  update your list, read it back again, and ask again. Never save on your own.
- After saving, tell them briefly what was saved (and anything skipped or already existing),
  then ask if there is anyone else.
- Phone numbers are US 10-digit numbers. If you hear a different digit count, ask them to repeat it.
- You only add newcomers. Politely decline anything else.
"""


class Newcomer(BaseModel):
    full_name: str
    phone_number: str


class QuickAddAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=INSTRUCTIONS)

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Greet the volunteer in one short sentence and ask who they met."
        )

    @function_tool
    async def save_newcomers(self, context: RunContext, people: list[Newcomer]) -> str:
        """Save newcomers after the volunteer has confirmed the read-back out loud.

        Args:
            people: Everyone to save, each with a full name and a phone number.
        """
        room = get_job_context().room
        volunteer = next(iter(room.remote_participants.values()), None)
        if volunteer is None:
            return "The volunteer is no longer connected; nothing was saved."

        payload = json.dumps({"people": [p.model_dump() for p in people]})
        try:
            response = await room.local_participant.perform_rpc(
                destination_identity=volunteer.identity,
                method="save_newcomers",
                payload=payload,
                response_timeout=15.0,
            )
        except rtc.RpcError as err:
            logger.warning("save_newcomers RPC failed: %s", err)
            return "Saving failed. Tell the volunteer it did not save and to try the form instead."
        return response


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-3",
        vad=silero.VAD.load(),
    )
    await session.start(agent=QuickAddAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
