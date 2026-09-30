from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .ai import ai_enabled, nutrition_tip, revise_plan, workout_plan
from .config import STATIC_DIR, TEMPLATES_DIR
from .database import get_db, init_db
from .models import Plan, User


# ============================================================
# INPUT MODELS
# ============================================================

class UserInput(BaseModel):
    username: str = Field(min_length=2, max_length=120)
    user_id: str = Field(min_length=2, max_length=80)
    age: int = Field(ge=13, le=100)
    weight: float = Field(gt=20, le=500)
    goal: str = Field(
        pattern="^(weight loss|muscle gain|general wellness|flexibility)$"
    )
    intensity: str = Field(
        pattern="^(low|medium|high)$"
    )


class FeedbackInput(BaseModel):
    user_id: str = Field(min_length=2, max_length=80)
    feedback: str = Field(min_length=3, max_length=2000)


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="FitBuddy - AI Fitness Plan Generator",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# STATIC FILES & TEMPLATES
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


# ============================================================
# DATABASE HELPER
# ============================================================

def save_plan(db: Session, user: User, workout: str, tip: str):
    """
    Save or update a user's workout plan.
    """

    if user.plan is None:
        user.plan = Plan(
            original_plan=workout,
            nutrition_tip=tip,
        )

    else:
        user.plan.original_plan = workout
        user.plan.nutrition_tip = tip

        # Clear previous feedback/update
        user.plan.updated_plan = None
        user.plan.updated_tip = None
        user.plan.feedback = None
        user.plan.updated_at = None

    db.add(user)
    db.commit()
    db.refresh(user)


# ============================================================
# HOME PAGE
# ============================================================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request
        },
    )


# ============================================================
# GENERATE WORKOUT - WEB FORM
# ============================================================

@app.post("/generate-workout", response_class=HTMLResponse)
def generate_workout(
    request: Request,
    username: str = Form(...),
    user_id: str = Form(...),
    age: int = Form(...),
    weight: float = Form(...),
    goal: str = Form(...),
    intensity: str = Form(...),
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    try:
        data = UserInput(
            username=username.strip(),
            user_id=user_id.strip(),
            age=age,
            weight=weight,
            goal=goal,
            intensity=intensity,
        )

    except Exception as exc:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "error": str(exc),
            },
            status_code=422,
        )

    # --------------------------------------------------------
    # Find existing user
    # --------------------------------------------------------

    user = db.scalar(
        select(User).where(
            User.user_id == data.user_id
        )
    )

    # --------------------------------------------------------
    # Create or update user
    # --------------------------------------------------------

    if user is None:

        user = User(
            **data.model_dump()
        )

        db.add(user)
        db.flush()

    else:

        for key, value in data.model_dump().items():
            setattr(user, key, value)

    # --------------------------------------------------------
    # Generate AI / fallback workout
    # --------------------------------------------------------

    plan = workout_plan(
        data.username,
        data.age,
        data.weight,
        data.goal,
        data.intensity,
    )

    # --------------------------------------------------------
    # Generate nutrition tip
    # --------------------------------------------------------

    tip = nutrition_tip(
        data.goal
    )

    # --------------------------------------------------------
    # Save plan
    # --------------------------------------------------------

    save_plan(
        db,
        user,
        plan,
        tip,
    )

    # --------------------------------------------------------
    # Show result page
    # --------------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "request": request,
            "user": user,
            "plan": user.plan,
            "ai_enabled": ai_enabled(),
            "message": "Your 7-day plan has been generated.",
        },
    )


# ============================================================
# SUBMIT FEEDBACK - WEB FORM
# ============================================================

@app.post("/submit-feedback", response_class=HTMLResponse)
def submit_feedback(
    request: Request,
    user_id: str = Form(...),
    feedback: str = Form(...),
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Find user and plan
    # --------------------------------------------------------

    user = db.scalar(
        select(User)
        .options(joinedload(User.plan))
        .where(User.user_id == user_id.strip())
    )

    if not user or not user.plan:
        raise HTTPException(
            status_code=404,
            detail="User or plan not found",
        )

    # --------------------------------------------------------
    # Validate feedback
    # --------------------------------------------------------

    feedback = feedback.strip()

    if len(feedback) < 3:
        raise HTTPException(
            status_code=422,
            detail="Feedback is too short",
        )

    # --------------------------------------------------------
    # Revise workout plan
    # --------------------------------------------------------

    user.plan.updated_plan = revise_plan(
        user.plan.original_plan,
        feedback,
    )

    # --------------------------------------------------------
    # Update nutrition tip
    # --------------------------------------------------------

    user.plan.updated_tip = nutrition_tip(
        user.goal
    )

    # --------------------------------------------------------
    # Save feedback
    # --------------------------------------------------------

    user.plan.feedback = feedback
    user.plan.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    # --------------------------------------------------------
    # Show updated result
    # --------------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "request": request,
            "user": user,
            "plan": user.plan,
            "ai_enabled": ai_enabled(),
            "message": "Your plan was updated from your feedback.",
        },
    )


# ============================================================
# VIEW ALL USERS
# ============================================================

@app.get("/view-all-users", response_class=HTMLResponse)
def view_all_users(
    request: Request,
    db: Session = Depends(get_db),
):

    users = (
        db.scalars(
            select(User)
            .options(joinedload(User.plan))
            .order_by(User.created_at.desc())
        )
        .unique()
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="all_users.html",
        context={
            "request": request,
            "users": users,
        },
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ai_enabled": ai_enabled(),
    }


# ============================================================
# API - GENERATE WORKOUT
# ============================================================

@app.post("/api/generate-workout")
def api_generate(
    data: UserInput,
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Find user
    # --------------------------------------------------------

    user = db.scalar(
        select(User).where(
            User.user_id == data.user_id
        )
    )

    # --------------------------------------------------------
    # Create or update user
    # --------------------------------------------------------

    if user is None:

        user = User(
            **data.model_dump()
        )

        db.add(user)
        db.flush()

    else:

        for key, value in data.model_dump().items():
            setattr(user, key, value)

    # --------------------------------------------------------
    # Generate workout
    # --------------------------------------------------------

    plan = workout_plan(
        data.username,
        data.age,
        data.weight,
        data.goal,
        data.intensity,
    )

    # --------------------------------------------------------
    # Generate nutrition tip
    # --------------------------------------------------------

    tip = nutrition_tip(
        data.goal
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_plan(
        db,
        user,
        plan,
        tip,
    )

    # --------------------------------------------------------
    # API response
    # --------------------------------------------------------

    return {
        "user": data.model_dump(),
        "workout_plan": plan,
        "nutrition_tip": tip,
    }


# ============================================================
# API - SUBMIT FEEDBACK
# ============================================================

@app.post("/api/submit-feedback")
def api_feedback(
    data: FeedbackInput,
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Find user and plan
    # --------------------------------------------------------

    user = db.scalar(
        select(User)
        .options(joinedload(User.plan))
        .where(User.user_id == data.user_id)
    )

    if not user or not user.plan:
        raise HTTPException(
            status_code=404,
            detail="User or plan not found",
        )

    # --------------------------------------------------------
    # Revise plan
    # --------------------------------------------------------

    user.plan.updated_plan = revise_plan(
        user.plan.original_plan,
        data.feedback,
    )

    # --------------------------------------------------------
    # Update nutrition
    # --------------------------------------------------------

    user.plan.updated_tip = nutrition_tip(
        user.goal
    )

    # --------------------------------------------------------
    # Save feedback
    # --------------------------------------------------------

    user.plan.feedback = data.feedback
    user.plan.updated_at = datetime.utcnow()

    db.commit()

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "user_id": user.user_id,
        "updated_plan": user.plan.updated_plan,
        "nutrition_tip": user.plan.updated_tip,
    }


# ============================================================
# API - GET ALL USERS
# ============================================================

@app.get("/api/users")
def api_users(
    db: Session = Depends(get_db),
):

    users = (
        db.scalars(
            select(User)
            .options(joinedload(User.plan))
            .order_by(User.created_at.desc())
        )
        .unique()
        .all()
    )

    return [
        {
            "user_id": u.user_id,
            "username": u.username,
            "age": u.age,
            "weight": u.weight,
            "goal": u.goal,
            "intensity": u.intensity,
            "original_plan": (
                u.plan.original_plan
                if u.plan
                else None
            ),
            "updated_plan": (
                u.plan.updated_plan
                if u.plan
                else None
            ),
        }
        for u in users
    ]