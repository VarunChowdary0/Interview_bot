from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import health
from services.parser import parse_resume


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