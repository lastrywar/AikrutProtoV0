from fastapi import FastAPI, APIRouter, HTTPException, Depends, File, UploadFile, Form, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import httpx
import pdfplumber
import io
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'talent-ai-secret-key-2024')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Create the main app
app = FastAPI(title="TalentAI - CV Screening Platform")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

# Auth Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    company_id: Optional[str] = None
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Company Models
class CompanyValue(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    weight: float  # 0-100, total must equal 100

class CompanyCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    industry: Optional[str] = ""
    website: Optional[str] = ""
    values: List[CompanyValue] = []

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    values: Optional[List[CompanyValue]] = None

class CompanyResponse(BaseModel):
    id: str
    name: str
    description: str
    industry: str
    website: str
    values: List[CompanyValue]
    created_at: str
    updated_at: str

# Job Models
class PlaybookItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    weight: float  # 0-100, total per category must equal 100

class JobPlaybook(BaseModel):
    character: List[PlaybookItem] = []
    requirement: List[PlaybookItem] = []
    skill: List[PlaybookItem] = []

class JobCreate(BaseModel):
    title: str
    description: str
    requirements: str
    location: Optional[str] = ""
    employment_type: Optional[str] = "full-time"
    salary_range: Optional[str] = ""
    playbook: Optional[JobPlaybook] = None

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    salary_range: Optional[str] = None
    playbook: Optional[JobPlaybook] = None
    status: Optional[str] = None

class JobResponse(BaseModel):
    id: str
    company_id: str
    title: str
    description: str
    requirements: str
    location: str
    employment_type: str
    salary_range: str
    playbook: Optional[JobPlaybook]
    status: str
    created_at: str
    updated_at: str

# Candidate Models
class CandidateEvidence(BaseModel):
    type: str  # cv, psychotest, knowledge_test
    file_name: str
    content: str  # parsed text content
    uploaded_at: str

class CandidateCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""

class CandidateResponse(BaseModel):
    id: str
    company_id: str
    name: str
    email: str
    phone: str
    evidence: List[CandidateEvidence]
    created_at: str
    updated_at: str

# Analysis Models
class ScoreBreakdown(BaseModel):
    item_id: str
    item_name: str
    raw_score: float  # 0-100
    weight: float
    weighted_score: float
    reasoning: str

class CategoryScore(BaseModel):
    category: str  # character, requirement, skill
    score: float
    breakdown: List[ScoreBreakdown]

class AnalysisResult(BaseModel):
    id: str
    job_id: str
    candidate_id: str
    final_score: float
    category_scores: List[CategoryScore]
    overall_reasoning: str
    company_values_alignment: Optional[Dict[str, Any]] = None
    created_at: str

class BatchAnalysisRequest(BaseModel):
    job_id: str
    candidate_ids: List[str]

# Settings Models
class AISettings(BaseModel):
    openrouter_api_key: Optional[str] = ""
    model_name: str = "openai/gpt-4o-mini"
    language: str = "en"  # en or id

class SettingsUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    model_name: Optional[str] = None
    language: Optional[str] = None

# ==================== AUTH HELPERS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== AI SERVICE ====================

async def get_ai_settings(user_id: str) -> AISettings:
    settings = await db.settings.find_one({"user_id": user_id}, {"_id": 0})
    if settings:
        return AISettings(**settings)
    return AISettings()

async def call_openrouter(api_key: str, model: str, messages: List[Dict], temperature: float = 0.7) -> str:
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenRouter API key not configured. Please set it in Settings.")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://talentai.app",
                "X-Title": "TalentAI CV Screening"
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4000
            }
        )
        
        if response.status_code != 200:
            error_detail = response.text
            logger.error(f"OpenRouter API error: {error_detail}")
            raise HTTPException(status_code=response.status_code, detail=f"AI API error: {error_detail}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]

def parse_pdf(file_content: bytes) -> str:
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.error(f"PDF parsing error: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse PDF file")
    return text.strip()

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "company_id": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user)
    
    # Create default settings
    await db.settings.insert_one({
        "user_id": user_id,
        "openrouter_api_key": "",
        "model_name": "openai/gpt-4o-mini",
        "language": "en"
    })
    
    token = create_token(user_id)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user_data.email,
            name=user_data.name,
            company_id=None,
            created_at=user["created_at"]
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            company_id=user.get("company_id"),
            created_at=user["created_at"]
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        company_id=current_user.get("company_id"),
        created_at=current_user["created_at"]
    )

# ==================== COMPANY ROUTES ====================

@api_router.post("/company", response_model=CompanyResponse)
async def create_company(data: CompanyCreate, current_user: dict = Depends(get_current_user)):
    if current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="User already has a company")
    
    company_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    company = {
        "id": company_id,
        "name": data.name,
        "description": data.description or "",
        "industry": data.industry or "",
        "website": data.website or "",
        "values": [v.model_dump() for v in data.values],
        "created_at": now,
        "updated_at": now
    }
    
    await db.companies.insert_one(company)
    await db.users.update_one({"id": current_user["id"]}, {"$set": {"company_id": company_id}})
    
    return CompanyResponse(**company)

@api_router.get("/company", response_model=Optional[CompanyResponse])
async def get_company(current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        return None
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    if not company:
        return None
    
    return CompanyResponse(**company)

@api_router.put("/company", response_model=CompanyResponse)
async def update_company(data: CompanyUpdate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        raise HTTPException(status_code=404, detail="No company found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "values" in update_data:
        update_data["values"] = [v.model_dump() if hasattr(v, 'model_dump') else v for v in update_data["values"]]
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.companies.update_one({"id": current_user["company_id"]}, {"$set": update_data})
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    return CompanyResponse(**company)

@api_router.post("/company/generate-values")
async def generate_company_values(narrative: str = Form(...), current_user: dict = Depends(get_current_user)):
    settings = await get_ai_settings(current_user["id"])
    
    lang_instruction = "Respond in English." if settings.language == "en" else "Respond in Indonesian (Bahasa Indonesia)."
    
    prompt = f"""Based on this company culture narrative, generate 5-7 structured company values.

Narrative: {narrative}

{lang_instruction}

Return a JSON array with this structure:
[
  {{"name": "Value Name", "description": "Brief description of this value", "weight": 15}}
]

Requirements:
- Each value should have a clear, concise name
- Description should be 1-2 sentences
- Weights should total exactly 100
- Values should be distinct and meaningful for candidate evaluation"""

    messages = [{"role": "user", "content": prompt}]
    response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages)
    
    try:
        # Extract JSON from response
        json_start = response.find('[')
        json_end = response.rfind(']') + 1
        values_json = response[json_start:json_end]
        values = json.loads(values_json)
        
        # Add IDs
        for v in values:
            v["id"] = str(uuid.uuid4())
        
        return {"values": values}
    except Exception as e:
        logger.error(f"Failed to parse AI response: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse AI-generated values")

# ==================== JOB ROUTES ====================

@api_router.post("/jobs", response_model=JobResponse)
async def create_job(data: JobCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    job = {
        "id": job_id,
        "company_id": current_user["company_id"],
        "title": data.title,
        "description": data.description,
        "requirements": data.requirements,
        "location": data.location or "",
        "employment_type": data.employment_type or "full-time",
        "salary_range": data.salary_range or "",
        "playbook": data.playbook.model_dump() if data.playbook else None,
        "status": "open",
        "created_at": now,
        "updated_at": now
    }
    
    await db.jobs.insert_one(job)
    return JobResponse(**job)

@api_router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        return []
    
    jobs = await db.jobs.find({"company_id": current_user["company_id"]}, {"_id": 0}).to_list(1000)
    return [JobResponse(**job) for job in jobs]

@api_router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job)

@api_router.put("/jobs/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, data: JobUpdate, current_user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "playbook" in update_data and update_data["playbook"]:
        update_data["playbook"] = update_data["playbook"].model_dump() if hasattr(update_data["playbook"], 'model_dump') else update_data["playbook"]
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.jobs.update_one({"id": job_id}, {"$set": update_data})
    
    updated_job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    return JobResponse(**updated_job)

@api_router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.jobs.delete_one({"id": job_id, "company_id": current_user.get("company_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted"}

@api_router.post("/jobs/generate-description")
async def generate_job_description(title: str = Form(...), context: str = Form(""), current_user: dict = Depends(get_current_user)):
    settings = await get_ai_settings(current_user["id"])
    
    lang_instruction = "Write in English." if settings.language == "en" else "Write in Indonesian (Bahasa Indonesia)."
    
    prompt = f"""Generate a professional job description and requirements for the position: {title}

Additional context: {context}

{lang_instruction}

Return a JSON object with:
{{
  "description": "Full job description (responsibilities, about the role, what you'll do)",
  "requirements": "List of requirements (experience, skills, qualifications)"
}}

Make it professional, detailed, and suitable for attracting qualified candidates."""

    messages = [{"role": "user", "content": prompt}]
    response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages)
    
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        return json.loads(response[json_start:json_end])
    except:
        return {"description": response, "requirements": ""}

@api_router.post("/jobs/{job_id}/generate-playbook")
async def generate_job_playbook(job_id: str, current_user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    settings = await get_ai_settings(current_user["id"])
    
    lang_instruction = "Write in English." if settings.language == "en" else "Write in Indonesian (Bahasa Indonesia)."
    
    company_values_text = ""
    if company and company.get("values"):
        company_values_text = "Company Values:\n" + "\n".join([f"- {v['name']}: {v['description']}" for v in company["values"]])
    
    prompt = f"""Generate a comprehensive job evaluation playbook/rubric for screening candidates.

Job Title: {job['title']}
Job Description: {job['description']}
Requirements: {job['requirements']}
{company_values_text}

{lang_instruction}

Create evaluation criteria in 3 categories. Each category must have exactly 5 items with weights totaling 100%.

Return a JSON object:
{{
  "character": [
    {{"name": "Criterion Name", "description": "What to evaluate", "weight": 20}}
  ],
  "requirement": [
    {{"name": "Criterion Name", "description": "What to evaluate", "weight": 20}}
  ],
  "skill": [
    {{"name": "Criterion Name", "description": "What to evaluate", "weight": 20}}
  ]
}}

Categories:
- Character: Personality traits, cultural fit, soft skills, work ethic
- Requirement: Education, experience, certifications, mandatory qualifications  
- Skill: Technical abilities, tools, domain expertise

Make criteria specific to this role and measurable from CV/resume review."""

    messages = [{"role": "user", "content": prompt}]
    response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages, temperature=0.5)
    
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        playbook_data = json.loads(response[json_start:json_end])
        
        # Add IDs to each item
        for category in ["character", "requirement", "skill"]:
            if category in playbook_data:
                for item in playbook_data[category]:
                    item["id"] = str(uuid.uuid4())
        
        # Update job with playbook
        await db.jobs.update_one(
            {"id": job_id},
            {"$set": {"playbook": playbook_data, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        return {"playbook": playbook_data}
    except Exception as e:
        logger.error(f"Failed to parse playbook: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate playbook")

# ==================== CANDIDATE ROUTES ====================

@api_router.post("/candidates", response_model=CandidateResponse)
async def create_candidate(data: CandidateCreate, current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    candidate_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    candidate = {
        "id": candidate_id,
        "company_id": current_user["company_id"],
        "name": data.name,
        "email": data.email,
        "phone": data.phone or "",
        "evidence": [],
        "created_at": now,
        "updated_at": now
    }
    
    await db.candidates.insert_one(candidate)
    return CandidateResponse(**candidate)

@api_router.get("/candidates", response_model=List[CandidateResponse])
async def list_candidates(current_user: dict = Depends(get_current_user)):
    if not current_user.get("company_id"):
        return []
    
    candidates = await db.candidates.find({"company_id": current_user["company_id"]}, {"_id": 0}).to_list(1000)
    return [CandidateResponse(**c) for c in candidates]

@api_router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(candidate_id: str, current_user: dict = Depends(get_current_user)):
    candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateResponse(**candidate)

@api_router.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.candidates.delete_one({"id": candidate_id, "company_id": current_user.get("company_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"message": "Candidate deleted"}

@api_router.post("/candidates/upload-cv")
async def upload_cv(
    file: UploadFile = File(...),
    candidate_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    content = await file.read()
    parsed_text = parse_pdf(content)
    
    if not parsed_text:
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Extract basic info from CV using simple parsing
    lines = parsed_text.split('\n')
    name = lines[0].strip() if lines else "Unknown"
    email = ""
    phone = ""
    
    for line in lines[:20]:  # Check first 20 lines
        line = line.strip()
        if '@' in line and '.' in line:
            email = line
        if any(c.isdigit() for c in line) and len([c for c in line if c.isdigit()]) >= 8:
            phone = line
    
    if candidate_id:
        # Add evidence to existing candidate
        evidence = {
            "type": "cv",
            "file_name": file.filename,
            "content": parsed_text,
            "uploaded_at": now
        }
        
        await db.candidates.update_one(
            {"id": candidate_id, "company_id": current_user["company_id"]},
            {"$push": {"evidence": evidence}, "$set": {"updated_at": now}}
        )
        
        candidate = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
        return CandidateResponse(**candidate)
    else:
        # Create new candidate with CV
        candidate_id = str(uuid.uuid4())
        candidate = {
            "id": candidate_id,
            "company_id": current_user["company_id"],
            "name": name,
            "email": email,
            "phone": phone,
            "evidence": [{
                "type": "cv",
                "file_name": file.filename,
                "content": parsed_text,
                "uploaded_at": now
            }],
            "created_at": now,
            "updated_at": now
        }
        
        await db.candidates.insert_one(candidate)
        return CandidateResponse(**candidate)

@api_router.post("/candidates/{candidate_id}/upload-evidence")
async def upload_evidence(
    candidate_id: str,
    file: UploadFile = File(...),
    evidence_type: str = Form(...),  # psychotest, knowledge_test
    current_user: dict = Depends(get_current_user)
):
    candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user.get("company_id")})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    content = await file.read()
    
    if file.filename.lower().endswith('.pdf'):
        parsed_text = parse_pdf(content)
    else:
        parsed_text = content.decode('utf-8', errors='ignore')
    
    now = datetime.now(timezone.utc).isoformat()
    evidence = {
        "type": evidence_type,
        "file_name": file.filename,
        "content": parsed_text,
        "uploaded_at": now
    }
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {"$push": {"evidence": evidence}, "$set": {"updated_at": now}}
    )
    
    updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    return CandidateResponse(**updated)

# ==================== ANALYSIS ROUTES ====================

@api_router.post("/analysis/run", response_model=List[AnalysisResult])
async def run_batch_analysis(request: BatchAnalysisRequest, current_user: dict = Depends(get_current_user)):
    job = await db.jobs.find_one({"id": request.job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.get("playbook"):
        raise HTTPException(status_code=400, detail="Job playbook not configured. Generate a playbook first.")
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    settings = await get_ai_settings(current_user["id"])
    
    results = []
    
    for candidate_id in request.candidate_ids:
        candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user["company_id"]}, {"_id": 0})
        if not candidate:
            continue
        
        # Check if analysis already exists
        existing = await db.analyses.find_one({"job_id": request.job_id, "candidate_id": candidate_id}, {"_id": 0})
        if existing:
            results.append(AnalysisResult(**existing))
            continue
        
        # Compile all evidence
        all_evidence = "\n\n".join([
            f"=== {e['type'].upper()} ({e['file_name']}) ===\n{e['content']}"
            for e in candidate.get("evidence", [])
        ])
        
        if not all_evidence:
            continue
        
        lang_instruction = "Respond in English." if settings.language == "en" else "Respond in Indonesian (Bahasa Indonesia)."
        
        company_values_text = ""
        if company and company.get("values"):
            company_values_text = "Company Values to consider:\n" + "\n".join([
                f"- {v['name']} (Weight: {v['weight']}%): {v['description']}" 
                for v in company["values"]
            ])
        
        playbook = job["playbook"]
        
        prompt = f"""You are an expert HR analyst. Evaluate this candidate against the job criteria.

JOB: {job['title']}
Description: {job['description']}
Requirements: {job['requirements']}

{company_values_text}

CANDIDATE EVIDENCE:
{all_evidence}

EVALUATION RUBRIC:
Character Traits:
{json.dumps(playbook.get('character', []), indent=2)}

Requirements:
{json.dumps(playbook.get('requirement', []), indent=2)}

Skills:
{json.dumps(playbook.get('skill', []), indent=2)}

{lang_instruction}

For each criterion in each category, score 0-100 based on evidence from the candidate's documents.
Be objective and cite specific evidence for each score.

Return JSON:
{{
  "category_scores": [
    {{
      "category": "character",
      "breakdown": [
        {{"item_id": "id", "item_name": "name", "raw_score": 85, "reasoning": "Evidence-based justification"}}
      ]
    }},
    {{
      "category": "requirement",
      "breakdown": [...]
    }},
    {{
      "category": "skill",
      "breakdown": [...]
    }}
  ],
  "overall_reasoning": "Summary of candidate fit",
  "company_values_alignment": {{
    "score": 80,
    "notes": "How candidate aligns with company values"
  }}
}}"""

        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages, temperature=0.3)
            
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            analysis_data = json.loads(response[json_start:json_end])
            
            # Calculate weighted scores
            category_scores = []
            total_weighted = 0
            total_weight = 0
            
            for cat_data in analysis_data.get("category_scores", []):
                category = cat_data["category"]
                playbook_items = {item["id"]: item for item in playbook.get(category, [])}
                
                breakdown = []
                cat_total = 0
                cat_weight = 0
                
                for item_score in cat_data.get("breakdown", []):
                    item_id = item_score.get("item_id", "")
                    playbook_item = playbook_items.get(item_id, {})
                    weight = playbook_item.get("weight", 20)
                    raw_score = item_score.get("raw_score", 0)
                    weighted = (raw_score * weight) / 100
                    
                    breakdown.append(ScoreBreakdown(
                        item_id=item_id,
                        item_name=item_score.get("item_name", playbook_item.get("name", "")),
                        raw_score=raw_score,
                        weight=weight,
                        weighted_score=weighted,
                        reasoning=item_score.get("reasoning", "")
                    ))
                    
                    cat_total += weighted
                    cat_weight += weight
                
                cat_score = (cat_total / cat_weight * 100) if cat_weight > 0 else 0
                category_scores.append(CategoryScore(
                    category=category,
                    score=round(cat_score, 1),
                    breakdown=breakdown
                ))
                
                total_weighted += cat_score
                total_weight += 1
            
            final_score = round(total_weighted / total_weight, 1) if total_weight > 0 else 0
            
            analysis_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            
            analysis = {
                "id": analysis_id,
                "job_id": request.job_id,
                "candidate_id": candidate_id,
                "final_score": final_score,
                "category_scores": [cs.model_dump() for cs in category_scores],
                "overall_reasoning": analysis_data.get("overall_reasoning", ""),
                "company_values_alignment": analysis_data.get("company_values_alignment"),
                "created_at": now
            }
            
            await db.analyses.insert_one(analysis)
            results.append(AnalysisResult(**analysis))
            
        except Exception as e:
            logger.error(f"Analysis failed for candidate {candidate_id}: {e}")
            continue
    
    return results

@api_router.get("/analysis/job/{job_id}", response_model=List[AnalysisResult])
async def get_job_analyses(job_id: str, min_score: Optional[float] = None, current_user: dict = Depends(get_current_user)):
    query = {"job_id": job_id}
    
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if min_score is not None:
        query["final_score"] = {"$gte": min_score}
    
    analyses = await db.analyses.find(query, {"_id": 0}).sort("final_score", -1).to_list(1000)
    return [AnalysisResult(**a) for a in analyses]

@api_router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    analysis = await db.analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisResult(**analysis)

@api_router.delete("/analysis/{analysis_id}")
async def delete_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.analyses.delete_one({"id": analysis_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": "Analysis deleted"}

# ==================== SETTINGS ROUTES ====================

@api_router.get("/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    settings = await db.settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    if settings:
        # Mask API key for security
        if settings.get("openrouter_api_key"):
            key = settings["openrouter_api_key"]
            settings["openrouter_api_key_masked"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "****"
            settings["has_api_key"] = True
        else:
            settings["openrouter_api_key_masked"] = ""
            settings["has_api_key"] = False
        del settings["openrouter_api_key"]
    return settings or {"model_name": "openai/gpt-4o-mini", "language": "en", "has_api_key": False}

@api_router.put("/settings")
async def update_settings(data: SettingsUpdate, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    await db.settings.update_one(
        {"user_id": current_user["id"]},
        {"$set": update_data},
        upsert=True
    )
    
    return {"message": "Settings updated"}

# ==================== DASHBOARD ROUTES ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    company_id = current_user.get("company_id")
    if not company_id:
        return {
            "total_candidates": 0,
            "open_jobs": 0,
            "analyses_completed": 0,
            "avg_score": 0
        }
    
    total_candidates = await db.candidates.count_documents({"company_id": company_id})
    open_jobs = await db.jobs.count_documents({"company_id": company_id, "status": "open"})
    
    # Get all job IDs for this company
    jobs = await db.jobs.find({"company_id": company_id}, {"id": 1}).to_list(1000)
    job_ids = [j["id"] for j in jobs]
    
    analyses_completed = await db.analyses.count_documents({"job_id": {"$in": job_ids}})
    
    # Calculate average score
    pipeline = [
        {"$match": {"job_id": {"$in": job_ids}}},
        {"$group": {"_id": None, "avg_score": {"$avg": "$final_score"}}}
    ]
    avg_result = await db.analyses.aggregate(pipeline).to_list(1)
    avg_score = round(avg_result[0]["avg_score"], 1) if avg_result else 0
    
    return {
        "total_candidates": total_candidates,
        "open_jobs": open_jobs,
        "analyses_completed": analyses_completed,
        "avg_score": avg_score
    }

@api_router.get("/dashboard/recent-activity")
async def get_recent_activity(current_user: dict = Depends(get_current_user)):
    company_id = current_user.get("company_id")
    if not company_id:
        return []
    
    activities = []
    
    # Recent candidates
    recent_candidates = await db.candidates.find(
        {"company_id": company_id},
        {"_id": 0, "id": 1, "name": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    for c in recent_candidates:
        activities.append({
            "type": "candidate_added",
            "message": f"New candidate: {c['name']}",
            "timestamp": c["created_at"]
        })
    
    # Recent jobs
    recent_jobs = await db.jobs.find(
        {"company_id": company_id},
        {"_id": 0, "id": 1, "title": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    for j in recent_jobs:
        activities.append({
            "type": "job_created",
            "message": f"New job: {j['title']}",
            "timestamp": j["created_at"]
        })
    
    # Sort by timestamp
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    return activities[:10]

# Include router and middleware
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
