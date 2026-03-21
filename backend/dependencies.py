from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_bs_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract and validate the Brightspace Bearer token from the Authorization header."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return credentials.credentials
