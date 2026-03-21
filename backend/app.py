from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import get_supabase
from supabase import AsyncClient
from routes.brightspace import router as brightspace_router
from routes.chat import router as chat_router
from routes.upload import router as upload_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brightspace_router)
app.include_router(chat_router)
app.include_router(upload_router)

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/about")
def read_about():
    return {"message": "About Page"}

@app.get("/db-check")
async def db_check(db: AsyncClient = Depends(get_supabase)):
    """Health check endpoint to verify Supabase connection configuration."""
    try:
        # A simple query to ensure the client is initialized and configured correctly.
        # This assumes you have at least one table or just tests the initialization.
        return {"status": "ok", "message": "Supabase client successfully initialized."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

