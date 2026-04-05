from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import secrets
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

from database import get_db
from models import User, Analysis
from schemas import (
    UserCreate, UserResponse, LoginRequest, TokenResponse,
    AnalysisResponse
)
from security import hash_password, verify_password, create_access_token, decode_access_token
from ai import analyze_resume, extract_text_from_pdf
from mailer import send_verification_email

app = FastAPI(title="ResumeIQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------- Auth Dependency ----------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


# ---------- Root ----------

@app.get("/")
async def home():
    return {"message": "ResumeIQ API is alive!"}


# ---------- Auth Routes ----------

@app.post("/auth/register", response_model=UserResponse, status_code=201)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check duplicate email
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Block disposable/fake email domains
    blocked_domains = [
        "mailinator.com", "tempmail.com", "guerrillamail.com",
        "10minutemail.com", "throwaway.email", "fakeinbox.com",
        "yopmail.com", "sharklasers.com", "trashmail.com",
        "maildrop.cc", "dispostable.com", "spamgourmet.com"
    ]
    email_domain = user.email.split("@")[1].lower()
    if email_domain in blocked_domains:
        raise HTTPException(status_code=400, detail="Please use a real email address")

    # Set is_verified=True so anyone can login immediately
    verification_token = secrets.token_urlsafe(32)
    new_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hash_password(user.password),
        is_verified=True,  # ← no verification required
        verification_token=verification_token
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Still try to send welcome email but don't block if it fails
    try:
        send_verification_email(new_user.name, new_user.email, verification_token)
    except Exception as e:
        print(f"Email send failed: {e}")

    return new_user

@app.get("/auth/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.verification_token == token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user.is_verified = True
    user.verification_token = None
    await db.commit()
    return {"message": "Email verified! You can now login."}


@app.post("/auth/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


# ---------- User Routes ----------

@app.get("/users/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------- Analysis Routes ----------

@app.post("/analyze", response_model=AnalysisResponse, status_code=201)
async def analyze(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not resume.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file_bytes = await resume.read()

    try:
        resume_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(resume_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract enough text from PDF."
        )

    analysis_result = await analyze_resume(resume_text, job_description)

    new_analysis = Analysis(
        resume_text=resume_text,
        job_description=job_description,
        result=json.dumps(analysis_result),
        match_score=analysis_result.get("match_score", 0),
        user_id=current_user.id
    )
    db.add(new_analysis)
    await db.commit()
    await db.refresh(new_analysis)
    return new_analysis


@app.get("/analyses", response_model=list[AnalysisResponse])
async def get_analyses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Analysis)
        .where(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
    )
    return result.scalars().all()


@app.get("/analyses/{analysis_id}")
async def get_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return {
        "id": analysis.id,
        "match_score": analysis.match_score,
        "job_description": analysis.job_description,
        "result": json.loads(analysis.result),
        "created_at": analysis.created_at
    }


@app.delete("/analyses/{analysis_id}")
async def delete_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    await db.delete(analysis)
    await db.commit()
    return {"message": "Analysis deleted"}


# ---------- Export PDF ----------

@app.get("/analyses/{analysis_id}/export")
async def export_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    data = json.loads(analysis.result)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("ResumeIQ Analysis Report", styles['Title']))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"ATS Match Score: {analysis.match_score}%", styles['Heading1']))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Overall Feedback", styles['Heading2']))
    story.append(Paragraph(data.get('overall_feedback', ''), styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Missing Keywords", styles['Heading2']))
    missing = data.get('missing_keywords', [])
    if missing:
        story.append(Paragraph(", ".join(missing), styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Top Suggestions", styles['Heading2']))
    for i, suggestion in enumerate(data.get('top_suggestions', []), 1):
        story.append(Paragraph(f"{i}. {suggestion}", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Section Feedback", styles['Heading2']))
    for section, details in data.get('sections', {}).items():
        story.append(Paragraph(f"{section.title()} — Score: {details.get('score', 0)}%", styles['Heading3']))
        story.append(Paragraph(details.get('feedback', ''), styles['Normal']))
        story.append(Spacer(1, 0.1 * inch))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=resumeiq-analysis-{analysis_id}.pdf"}
    )