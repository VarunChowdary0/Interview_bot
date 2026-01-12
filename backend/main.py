from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routers import health
from services.parser import parse_resume
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from db import get_db

app =FastAPI(title="AI Interview Bot Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=['*'],
    expose_headers=["*"],
)

app.include_router(health.router, prefix="/health")

@app.get("/")
def root():
    return {"message":"AI Interview bot backend is running...."}

@app.get("/parse")
def test():
    # data = parse_resume("C:\\PROGRAMS\\WEB_ALL\\Interview_bot\\backend\\services\\parser\\test-resumes\\Resume_4.pdf")
    data = parse_resume("C:\\PROGRAMS\\WEB_ALL\\Interview_bot\\backend\\services\\parser\\test-resumes\\22nd_nov_2025.pdf")
    # data = parse_resume("C:\\PROGRAMS\\WEB_ALL\\Interview_bot\\backend\\services\\parser\\test-resumes\\2026_jan_4.pdf")
    return data


@app.get("/db-check")
async def db_check(db: AsyncSession = Depends(get_db)):
    res = await db.execute(text("SELECT 1"))
    return {
        "route": "/db-check",
        "data": {
            "db": "Connected",
            "result": res.scalar()
        }
    }