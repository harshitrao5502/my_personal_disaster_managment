import asyncio
from livekit import api
from dotenv import load_dotenv

load_dotenv("backend/.env.local")

async def main():
    lkapi = api.LiveKitAPI()
    
    request = api.CreateSIPParticipantRequest(
        sip_trunk_id="ST_aH2g3V58su5V",  # Your new trunk ID
        sip_call_to="sip:happy_creates",
        room_name="welfare-check-01",
        participant_identity="Rahul_Mobile"
    )
    
    print("Initiating call to Linphone...")
    try:
        participant = await lkapi.sip.create_sip_participant(request)
        print("Success! Dialing Linphone:", participant.participant_identity)
    except Exception as e:
        print("Failed to initiate call:", e)
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())