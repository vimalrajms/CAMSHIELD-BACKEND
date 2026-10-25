import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "camshield.db"


def init_db():
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS camera_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                device_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="CAMSHIELD API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class CameraEvent(BaseModel):
    event_type: Literal[
    "website_camera_started",
    "website_camera_stopped",
    "android_camera_event",
    "windows_camera_event",
]
    device_name: str = Field(default="Web browser", max_length=100)


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "service": "CAMSHIELD API",
    }


@app.post("/api/events", status_code=201)
def create_event(event: CameraEvent):
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        with sqlite3.connect(DB_PATH) as connection:
            cursor = connection.execute(
                """
                INSERT INTO camera_events
                (event_type, device_name, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    event.event_type,
                    event.device_name,
                    created_at,
                ),
            )
            event_id = cursor.lastrowid

        return {
            "id": event_id,
            "event_type": event.event_type,
            "device_name": event.device_name,
            "created_at": created_at,
        }
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not save the event.",
        ) from exc


@app.get("/api/events")
def get_events(limit: int = 50):
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100.",
        )

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, event_type, device_name, created_at
            FROM camera_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return {"events": [dict(row) for row in rows]}