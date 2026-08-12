import asyncio
import os
from livekit import api
from dotenv import load_dotenv

load_dotenv("backend/.env.local")

async def main():
    lkapi = api.LiveKitAPI()
    
    sip_trunk_id = os.environ.get("LIVEKIT_SIP_OUTBOUND_TRUNK_ID", "ST_aH2g3V58su5V")
    room_name = "welfare-check-01"
    
    request = api.CreateSIPParticipantRequest(
        sip_trunk_id=sip_trunk_id,
        sip_call_to="raksha_outer",
        room_name=room_name,
        participant_identity="Rahul_Mobile"
    )
    
    print("Initiating call to Linphone...")
    try:
        participant = await lkapi.sip.create_sip_participant(request)
        print("Success! Dialing Linphone:", participant.participant_identity)
        
        # Explicitly dispatch the agent to the room
        dispatch_request = api.CreateAgentDispatchRequest(
            agent_name="my-agent",
            room=room_name
        )
        print("Dispatching agent to room...")
        dispatch = await lkapi.agent_dispatch.create_dispatch(dispatch_request)
        print("Success! Dispatched agent:", dispatch.id)
        
    except Exception as e:
        print("Failed to initiate call or dispatch:", e)
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())