"""POST /api/add-event — Create a Google Calendar event using Clerk tokens."""

import os
import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import jwt

router = APIRouter(prefix="/api")

class EventRequest(BaseModel):
    summary: str
    description: str
    start_time: str
    end_time: str

@router.post("/add-event")
async def add_event(body: EventRequest, x_clerk_auth: str = Header(None)):
    """Add an event to the personal Google Calendar of the logged-in user."""
    
    if not x_clerk_auth or not x_clerk_auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid X-Clerk-Auth header")
    
    token = x_clerk_auth.split(" ")[1]
    
    # 1. Validate the Clerk Session Token.
    # For a hackathon, parsing the unverified JWT to get the user ID (sub) is usually acceptable.
    # In a true production app, verify the signature against your Clerk JWKS.
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        user_id = decoded.get("sub")
        if not user_id:
            raise ValueError("No user ID found in session token.")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid session token: {str(e)}")

    # 2. Retrieve Google OAuth Access Token from Clerk's Backend API
    clerk_secret = os.getenv("CLERK_SECRET_KEY")
    if not clerk_secret:
        raise HTTPException(status_code=500, detail="Missing CLERK_SECRET_KEY in environment.")

    # We use httpx to fetch the specific provider token since clerk-backend-api SDK 
    # token retrieval can be restrictive with asynchronous calls.
    clerk_api_url = f"https://api.clerk.com/v1/users/{user_id}/oauth_access_tokens/oauth_google"
    
    async with httpx.AsyncClient() as client:
        res = await client.get(
            clerk_api_url,
            headers={"Authorization": f"Bearer {clerk_secret}"}
        )
        if res.status_code != 200:
            print("Clerk API Response:", res.text)
            raise HTTPException(status_code=400, detail="Failed to fetch Google OAuth token from Clerk. Have you linked a Google account with the Calendar scope?")
        
        data = res.json()
        if not data:
            raise HTTPException(status_code=400, detail="No Google OAuth tokens found for this user. Make sure they signed in with Google.")
            
        google_token = data[0].get("token")
        if not google_token:
            raise HTTPException(status_code=400, detail="Google token is empty.")

    # 3. Create Google Calendar Event
    try:
        # Construct google credentials from the access token
        creds = Credentials(token=google_token)
        service = build("calendar", "v3", credentials=creds)

        event_body = {
            "summary": body.summary,
            "description": body.description,
            "start": {
                "dateTime": body.start_time,
                "timeZone": "UTC", # Uses UTC or follows the ISO 8601 offset
            },
            "end": {
                "dateTime": body.end_time,
                "timeZone": "UTC",
            }
        }

        # Insert the event into their primary calendar
        event = service.events().insert(calendarId="primary", body=event_body).execute()
        
        return {
            "status": "success", 
            "message": "Event added successfully",
            "event_link": event.get("htmlLink")
        }

    except Exception as e:
        print(f"Error creating Google Calendar event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create Google Calendar event: {str(e)}")
