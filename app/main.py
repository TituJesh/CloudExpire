
from fastapi import FastAPI

app = FastAPI(
    title="CloudExpire",
    description="Automated temporary AWS resource lifecycle manager",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "CloudExpire",
    }
