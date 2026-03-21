import os
from dotenv import load_dotenv
from supabase import acreate_client, AsyncClient

load_dotenv()

async def get_supabase() -> AsyncClient:
    url: str = os.getenv("SUPABASE_URL")
    key: str = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError("Supabase environment variables (SUPABASE_URL, SUPABASE_KEY) are missing.")
        
    return await acreate_client(url, key)
