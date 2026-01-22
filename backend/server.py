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
    candidate_name: Optional[str] = None  # Store name for when candidate is deleted
    final_score: float
    category_scores: List[CategoryScore]
    overall_reasoning: str
    company_values_alignment: Optional[Dict[str, Any]] = None
    strengths: Optional[List[str]] = []
    gaps: Optional[List[str]] = []
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

from bson import ObjectId

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

def serialize_doc(doc):
    """Recursively convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if key == '_id':
                continue  # Skip _id field
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = serialize_doc(value)
            elif isinstance(value, list):
                result[key] = serialize_doc(value)
            else:
                result[key] = value
        return result
    return doc

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
    
    if context.strip():
        # Generate based on narrative
        prompt = f"""Based on the following job description narrative, generate a professional and structured job description and requirements.

Job Title: {title}
Narrative/Context: {context}

{lang_instruction}

Return a JSON object with:
{{
  "description": "Full job description including: About the Role, Key Responsibilities (as bullet points), What You'll Do",
  "requirements": "List of requirements including: Required Experience, Required Skills, Qualifications, Nice-to-haves"
}}

Make it professional, well-structured, and suitable for attracting qualified candidates. Use the narrative as the primary source of information."""
    else:
        # Generate based on title only
        prompt = f"""Generate a professional job description and requirements for the position: {title}

{lang_instruction}

Return a JSON object with:
{{
  "description": "Full job description including: About the Role, Key Responsibilities (as bullet points), What You'll Do",
  "requirements": "List of requirements including: Required Experience, Required Skills, Qualifications, Nice-to-haves"
}}

Make it professional, detailed, and suitable for attracting qualified candidates."""

    messages = [{"role": "user", "content": prompt}]
    response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages)
    
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(response[json_start:json_end])
            return result
        else:
            return {"description": response, "requirements": ""}
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

# Candidate search/pagination endpoint - MUST be before {candidate_id} route
@api_router.get("/candidates/search")
async def search_candidates(
    q: str = Query("", description="Search query"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Search and paginate candidates"""
    if not current_user.get("company_id"):
        return {"candidates": [], "total": 0, "page": page, "pages": 0}
    
    company_id = current_user["company_id"]
    
    # Build search query
    query = {"company_id": company_id}
    if q.strip():
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.candidates.count_documents(query)
    pages = (total + limit - 1) // limit
    
    # Get paginated results
    skip = (page - 1) * limit
    candidates = await db.candidates.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    return {
        "candidates": candidates,
        "total": total,
        "page": page,
        "pages": pages,
        "limit": limit
    }

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
    
    # Try AI-powered parsing first, fallback to basic parsing
    settings = await get_ai_settings(current_user["id"])
    admin_settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    
    name = ""
    email = ""
    phone = ""
    
    # Use AI to extract contact info if API key is available
    if settings.openrouter_api_key:
        try:
            cv_parse_prompt = admin_settings.get("cv_parse_prompt") if admin_settings else None
            
            if cv_parse_prompt:
                prompt = cv_parse_prompt.format(cv_text=parsed_text[:3000])
            else:
                prompt = f"""Extract contact information from this CV/resume text.

CV TEXT (first 3000 chars):
{parsed_text[:3000]}

Return ONLY a JSON object with:
{{
  "name": "Full name of the candidate",
  "email": "Email address or empty string if not found",
  "phone": "Phone number or empty string if not found"
}}

Rules:
- Name should be the person's full name, NOT a company name or job title
- Phone should be a valid phone number format
- If information is unclear or not found, return empty string
- Do NOT make up information"""

            messages = [{"role": "user", "content": prompt}]
            response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages, temperature=0.1)
            
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                contact_info = json.loads(response[json_start:json_end])
                name = contact_info.get("name", "").strip()
                email = contact_info.get("email", "").strip()
                phone = contact_info.get("phone", "").strip()
        except Exception as e:
            logger.warning(f"AI CV parsing failed, using fallback: {e}")
    
    # Fallback to basic parsing if AI didn't work
    if not name:
        lines = parsed_text.split('\n')
        # Try to find name in first few non-empty lines
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) > 2 and len(line) < 50:
                # Check if it looks like a name (no numbers, no @ symbol)
                if not any(c.isdigit() for c in line) and '@' not in line:
                    name = line
                    break
        if not name:
            name = "Unknown Candidate"
    
    if not email:
        import re
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, parsed_text)
        email = emails[0] if emails else ""
    
    if not phone:
        import re
        # Common phone patterns
        phone_patterns = [
            r'\+?[\d\s\-\(\)]{10,}',
            r'\d{3}[\s\-]?\d{3}[\s\-]?\d{4}',
            r'\(\d{3}\)\s?\d{3}[\s\-]?\d{4}'
        ]
        for pattern in phone_patterns:
            phones = re.findall(pattern, parsed_text[:1000])
            if phones:
                phone = phones[0].strip()
                break
    
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
        
        # Serialize to remove any ObjectId
        candidate = serialize_doc(candidate)
        
        # Check if analysis already exists
        existing = await db.analyses.find_one({"job_id": request.job_id, "candidate_id": candidate_id}, {"_id": 0})
        if existing:
            existing = serialize_doc(existing)
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
            company_values_text = "Company Values to evaluate alignment:\n" + "\n".join([
                f"- {v['name']} (Weight: {v['weight']}%): {v['description']}" 
                for v in company["values"]
            ])
        
        playbook = job["playbook"]
        
        # Enhanced prompt for better scoring
        prompt = f"""You are an AI evaluator for candidate-job fit analysis.

JOB POSITION: {job['title']}
Job Description: {job['description']}
Job Requirements: {job['requirements']}

{company_values_text}

CANDIDATE: {candidate['name']}
CANDIDATE EVIDENCE:
{all_evidence}

EVALUATION PLAYBOOK:

CHARACTER TRAITS (evaluate personality, soft skills, cultural fit):
{json.dumps(playbook.get('character', []), indent=2)}

REQUIREMENTS (evaluate education, experience, certifications):
{json.dumps(playbook.get('requirement', []), indent=2)}

SKILLS (evaluate technical abilities, tools, domain expertise):
{json.dumps(playbook.get('skill', []), indent=2)}

{lang_instruction}

SCORING PROCESS:
1. For EACH subcategory in each category, analyze the candidate evidence
2. Assign a score 0-100 based on how well the evidence supports that criterion
3. Provide short reasoning with specific evidence references
4. If evidence is missing or unclear, score lower and note the gap

IMPORTANT RULES:
- Be objective and consistent
- Do NOT hallucinate evidence - only reference what's in the documents
- If evidence is missing for a criterion, assign lower score (20-40) and explain
- Use ONLY the selected output language

Return a JSON object with this EXACT structure:
{{
  "category_scores": [
    {{
      "category": "character",
      "breakdown": [
        {{"item_id": "{playbook.get('character', [{}])[0].get('id', 'id1') if playbook.get('character') else 'id1'}", "item_name": "Name from playbook", "raw_score": 75, "reasoning": "Specific evidence-based justification"}}
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
  "overall_reasoning": "2-3 sentence summary of candidate's overall fit for this role",
  "company_values_alignment": {{
    "score": 80,
    "breakdown": [
      {{"value_name": "Value Name", "score": 85, "reasoning": "How candidate aligns"}}
    ],
    "notes": "Overall assessment of cultural fit"
  }},
  "strengths": ["List of 2-3 key strengths"],
  "gaps": ["List of 2-3 areas needing improvement or missing evidence"]
}}

Ensure you evaluate ALL items in each category of the playbook. Do not skip any."""

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
                "candidate_name": candidate["name"],  # Store name for reference
                "final_score": final_score,
                "category_scores": [cs.model_dump() for cs in category_scores],
                "overall_reasoning": analysis_data.get("overall_reasoning", ""),
                "company_values_alignment": analysis_data.get("company_values_alignment"),
                "strengths": analysis_data.get("strengths", []),
                "gaps": analysis_data.get("gaps", []),
                "created_at": now
            }
            
            await db.analyses.insert_one(analysis)
            results.append(AnalysisResult(**analysis))
            
        except Exception as e:
            logger.error(f"Analysis failed for candidate {candidate_id}: {e}")
            continue
    
    return results

# Streaming analysis endpoint for progress tracking
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse

@api_router.post("/analysis/run-stream")
async def run_streaming_analysis(request: BatchAnalysisRequest, current_user: dict = Depends(get_current_user)):
    """Run analysis with streaming progress updates"""
    job = await db.jobs.find_one({"id": request.job_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.get("playbook"):
        raise HTTPException(status_code=400, detail="Job playbook not configured")
    
    company = await db.companies.find_one({"id": current_user["company_id"]}, {"_id": 0})
    settings = await get_ai_settings(current_user["id"])
    
    # Get prompts from admin settings
    admin_settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    job_fit_prompt_template = admin_settings.get("job_fit_prompt") if admin_settings else None
    
    async def generate_results():
        total = len(request.candidate_ids)
        
        for idx, candidate_id in enumerate(request.candidate_ids):
            candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user["company_id"]}, {"_id": 0})
            
            if not candidate:
                yield f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'candidate_id': candidate_id, 'status': 'skipped', 'message': 'Candidate not found'})}\n\n"
                continue
            
            # Serialize to ensure no ObjectId
            candidate = serialize_doc(candidate)
            
            # Send progress update - starting
            yield f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'candidate_id': candidate_id, 'candidate_name': candidate['name'], 'status': 'analyzing'})}\n\n"
            
            # Check existing
            existing = await db.analyses.find_one({"job_id": request.job_id, "candidate_id": candidate_id}, {"_id": 0})
            if existing:
                # Serialize to ensure no ObjectId
                existing = serialize_doc(existing)
                yield f"data: {json.dumps({'type': 'result', 'current': idx + 1, 'total': total, 'analysis': existing})}\n\n"
                continue
            
            # Compile evidence
            all_evidence = "\n\n".join([
                f"=== {e['type'].upper()} ({e['file_name']}) ===\n{e['content']}"
                for e in candidate.get("evidence", [])
            ])
            
            if not all_evidence:
                yield f"data: {json.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'candidate_id': candidate_id, 'status': 'skipped', 'message': 'No evidence'})}\n\n"
                continue
            
            lang_instruction = "Respond in English." if settings.language == "en" else "Respond in Indonesian (Bahasa Indonesia)."
            
            company_values_text = ""
            if company and company.get("values"):
                company_values_text = "Company Values to evaluate alignment:\n" + "\n".join([
                    f"- {v['name']} (Weight: {v['weight']}%): {v['description']}" 
                    for v in company["values"]
                ])
            
            playbook = job["playbook"]
            
            # Use custom prompt if available, otherwise default
            if job_fit_prompt_template:
                prompt = job_fit_prompt_template.format(
                    job_title=job['title'],
                    job_description=job['description'],
                    job_requirements=job['requirements'],
                    company_values=company_values_text,
                    candidate_name=candidate['name'],
                    candidate_evidence=all_evidence,
                    character_playbook=json.dumps(playbook.get('character', []), indent=2),
                    requirement_playbook=json.dumps(playbook.get('requirement', []), indent=2),
                    skill_playbook=json.dumps(playbook.get('skill', []), indent=2),
                    language_instruction=lang_instruction
                )
            else:
                prompt = f"""You are an AI evaluator for candidate-job fit analysis.

JOB POSITION: {job['title']}
Job Description: {job['description']}
Job Requirements: {job['requirements']}

{company_values_text}

CANDIDATE: {candidate['name']}
CANDIDATE EVIDENCE:
{all_evidence}

EVALUATION PLAYBOOK:

CHARACTER TRAITS:
{json.dumps(playbook.get('character', []), indent=2)}

REQUIREMENTS:
{json.dumps(playbook.get('requirement', []), indent=2)}

SKILLS:
{json.dumps(playbook.get('skill', []), indent=2)}

{lang_instruction}

For EACH item in the playbook, score 0-100 with evidence-based reasoning.
If evidence is missing, score lower (20-40) and note the gap.

Return JSON:
{{
  "category_scores": [
    {{"category": "character", "breakdown": [{{"item_id": "id", "item_name": "name", "raw_score": 75, "reasoning": "evidence"}}]}},
    {{"category": "requirement", "breakdown": [...]}},
    {{"category": "skill", "breakdown": [...]}}
  ],
  "overall_reasoning": "Summary",
  "company_values_alignment": {{"score": 80, "breakdown": [{{"value_name": "name", "score": 85, "reasoning": "why"}}], "notes": "cultural fit"}},
  "strengths": ["strength1", "strength2"],
  "gaps": ["gap1", "gap2"]
}}"""

            messages = [{"role": "user", "content": prompt}]
            
            try:
                response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages, temperature=0.3)
                
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                analysis_data = json.loads(response[json_start:json_end])
                
                # Calculate scores
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
                        
                        breakdown.append({
                            "item_id": item_id,
                            "item_name": item_score.get("item_name", playbook_item.get("name", "")),
                            "raw_score": raw_score,
                            "weight": weight,
                            "weighted_score": weighted,
                            "reasoning": item_score.get("reasoning", "")
                        })
                        
                        cat_total += weighted
                        cat_weight += weight
                    
                    cat_score = (cat_total / cat_weight * 100) if cat_weight > 0 else 0
                    category_scores.append({
                        "category": category,
                        "score": round(cat_score, 1),
                        "breakdown": breakdown
                    })
                    
                    total_weighted += cat_score
                    total_weight += 1
                
                final_score = round(total_weighted / total_weight, 1) if total_weight > 0 else 0
                
                analysis_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                
                analysis = {
                    "id": analysis_id,
                    "job_id": request.job_id,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate["name"],  # Store name for reference
                    "final_score": final_score,
                    "category_scores": category_scores,
                    "overall_reasoning": analysis_data.get("overall_reasoning", ""),
                    "company_values_alignment": analysis_data.get("company_values_alignment"),
                    "strengths": analysis_data.get("strengths", []),
                    "gaps": analysis_data.get("gaps", []),
                    "created_at": now
                }
                
                await db.analyses.insert_one(analysis)
                
                # Serialize to ensure no ObjectId before JSON dump
                analysis = serialize_doc(analysis)
                yield f"data: {json.dumps({'type': 'result', 'current': idx + 1, 'total': total, 'analysis': analysis})}\n\n"
                
            except Exception as e:
                logger.error(f"Analysis failed for {candidate_id}: {e}")
                yield f"data: {json.dumps({'type': 'error', 'current': idx + 1, 'total': total, 'candidate_id': candidate_id, 'error': str(e)})}\n\n"
        
        yield f"data: {json.dumps({'type': 'complete', 'total': total})}\n\n"
    
    return FastAPIStreamingResponse(
        generate_results(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@api_router.post("/candidates/check-duplicates")
async def check_duplicate_candidates(
    emails: List[str] = [],
    current_user: dict = Depends(get_current_user)
):
    """Check if candidates with given emails already exist"""
    if not current_user.get("company_id"):
        return {"duplicates": []}
    
    # Find existing candidates with matching emails
    existing = await db.candidates.find(
        {"company_id": current_user["company_id"], "email": {"$in": emails}},
        {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).to_list(100)
    
    return {"duplicates": existing}

@api_router.get("/analysis/job/{job_id}", response_model=List[AnalysisResult])
async def get_job_analyses(job_id: str, min_score: Optional[float] = None, current_user: dict = Depends(get_current_user)):
    query = {"job_id": job_id}
    
    job = await db.jobs.find_one({"id": job_id, "company_id": current_user.get("company_id")})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if min_score is not None:
        query["final_score"] = {"$gte": min_score}
    
    analyses = await db.analyses.find(query, {"_id": 0}).sort("final_score", -1).to_list(1000)
    # Serialize to ensure no ObjectId in nested structures
    analyses = [serialize_doc(a) for a in analyses]
    return [AnalysisResult(**a) for a in analyses]

@api_router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    analysis = await db.analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    # Serialize to ensure no ObjectId
    analysis = serialize_doc(analysis)
    return AnalysisResult(**analysis)

@api_router.delete("/analysis/{analysis_id}")
async def delete_analysis(analysis_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.analyses.delete_one({"id": analysis_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": "Analysis deleted"}

class BulkDeleteRequest(BaseModel):
    ids: List[str]

@api_router.post("/analysis/bulk-delete")
async def bulk_delete_analyses(request: BulkDeleteRequest, current_user: dict = Depends(get_current_user)):
    """Delete multiple analysis results at once"""
    if not request.ids:
        raise HTTPException(status_code=400, detail="No IDs provided")
    
    result = await db.analyses.delete_many({"id": {"$in": request.ids}})
    return {"message": f"Deleted {result.deleted_count} analysis result(s)"}

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

# ==================== ADMIN SETTINGS ROUTES ====================

class AdminSettingsUpdate(BaseModel):
    cv_parse_prompt: Optional[str] = None
    company_values_prompt: Optional[str] = None
    job_desc_title_prompt: Optional[str] = None
    job_desc_narrative_prompt: Optional[str] = None
    playbook_prompt: Optional[str] = None
    job_fit_prompt: Optional[str] = None

@api_router.get("/admin-settings")
async def get_admin_settings(current_user: dict = Depends(get_current_user)):
    """Get all admin/prompt settings"""
    settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    
    # Return defaults if not set
    defaults = {
        "cv_parse_prompt": """Extract contact information from this CV/resume text.

CV TEXT (first 3000 chars):
{cv_text}

Return ONLY a JSON object with:
{{
  "name": "Full name of the candidate",
  "email": "Email address or empty string if not found",
  "phone": "Phone number or empty string if not found"
}}

Rules:
- Name should be the person's full name, NOT a company name or job title
- Phone should be a valid phone number format
- If information is unclear or not found, return empty string
- Do NOT make up information""",
        
        "company_values_prompt": """Based on this company culture narrative, generate 5-7 structured company values.

Narrative: {narrative}

{language_instruction}

Return a JSON array with this structure:
[
  {{"name": "Value Name", "description": "Brief description of this value", "weight": 15}}
]

Requirements:
- Each value should have a clear, concise name
- Description should be 1-2 sentences
- Weights should total exactly 100
- Values should be distinct and meaningful for candidate evaluation""",
        
        "job_desc_title_prompt": """Generate a professional job description and requirements for the position: {job_title}

{language_instruction}

Return a JSON object with:
{{
  "description": "Full job description including: About the Role, Key Responsibilities (as bullet points), What You'll Do",
  "requirements": "List of requirements including: Required Experience, Required Skills, Qualifications, Nice-to-haves"
}}

Make it professional, detailed, and suitable for attracting qualified candidates.""",
        
        "job_desc_narrative_prompt": """Based on the following job description narrative, generate a professional and structured job description and requirements.

Job Title: {job_title}
Narrative/Context: {narrative}

{language_instruction}

Return a JSON object with:
{{
  "description": "Full job description including: About the Role, Key Responsibilities (as bullet points), What You'll Do",
  "requirements": "List of requirements including: Required Experience, Required Skills, Qualifications, Nice-to-haves"
}}

Make it professional, well-structured, and suitable for attracting qualified candidates. Use the narrative as the primary source of information.""",
        
        "playbook_prompt": """Generate a comprehensive job evaluation playbook/rubric for screening candidates.

Job Title: {job_title}
Job Description: {job_description}
Requirements: {job_requirements}
{company_values}

{language_instruction}

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

Make criteria specific to this role and measurable from CV/resume review.""",
        
        "job_fit_prompt": """You are an AI evaluator for candidate-job fit analysis.

JOB POSITION: {job_title}
Job Description: {job_description}
Job Requirements: {job_requirements}

{company_values}

CANDIDATE: {candidate_name}
CANDIDATE EVIDENCE:
{candidate_evidence}

EVALUATION PLAYBOOK:

CHARACTER TRAITS:
{character_playbook}

REQUIREMENTS:
{requirement_playbook}

SKILLS:
{skill_playbook}

{language_instruction}

SCORING PROCESS:
1. For EACH subcategory in each category, analyze the candidate evidence
2. Assign a score 0-100 based on how well the evidence supports that criterion
3. Provide short reasoning with specific evidence references
4. If evidence is missing for a criterion, assign lower score (20-40) and explain

IMPORTANT RULES:
- Be objective and consistent
- Do NOT hallucinate evidence - only reference what's in the documents
- If evidence is missing, score lower and note the gap
- Use ONLY the selected output language

Return JSON:
{{
  "category_scores": [
    {{"category": "character", "breakdown": [{{"item_id": "id", "item_name": "name", "raw_score": 75, "reasoning": "evidence"}}]}},
    {{"category": "requirement", "breakdown": [...]}},
    {{"category": "skill", "breakdown": [...]}}
  ],
  "overall_reasoning": "Summary",
  "company_values_alignment": {{"score": 80, "breakdown": [{{"value_name": "name", "score": 85, "reasoning": "why"}}], "notes": "cultural fit"}},
  "strengths": ["strength1", "strength2"],
  "gaps": ["gap1", "gap2"]
}}"""
    }
    
    if settings:
        # Merge with defaults
        for key in defaults:
            if key not in settings or not settings[key]:
                settings[key] = defaults[key]
        return settings
    
    return defaults

@api_router.put("/admin-settings")
async def update_admin_settings(data: AdminSettingsUpdate, current_user: dict = Depends(get_current_user)):
    """Update admin/prompt settings"""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["user_id"] = current_user["id"]
    
    await db.admin_settings.update_one(
        {"user_id": current_user["id"]},
        {"$set": update_data},
        upsert=True
    )
    
    return {"message": "Admin settings updated"}

@api_router.post("/admin-settings/reset/{prompt_key}")
async def reset_admin_prompt(prompt_key: str, current_user: dict = Depends(get_current_user)):
    """Reset a specific prompt to default"""
    valid_keys = ["cv_parse_prompt", "company_values_prompt", "job_desc_title_prompt", 
                  "job_desc_narrative_prompt", "playbook_prompt", "job_fit_prompt"]
    
    if prompt_key not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Invalid prompt key. Valid keys: {valid_keys}")
    
    await db.admin_settings.update_one(
        {"user_id": current_user["id"]},
        {"$unset": {prompt_key: ""}}
    )
    
    return {"message": f"{prompt_key} reset to default"}

# ==================== CANDIDATE UPDATE ROUTE ====================

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

@api_router.put("/candidates/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(candidate_id: str, data: CandidateUpdate, current_user: dict = Depends(get_current_user)):
    candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user.get("company_id")})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.candidates.update_one({"id": candidate_id}, {"$set": update_data})
    
    updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    return CandidateResponse(**updated)

# Re-parse candidate CV with AI
@api_router.post("/candidates/{candidate_id}/reparse")
async def reparse_candidate_cv(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Re-parse candidate info from CV using AI"""
    candidate = await db.candidates.find_one({"id": candidate_id, "company_id": current_user.get("company_id")}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Find CV evidence
    cv_evidence = next((e for e in candidate.get("evidence", []) if e["type"] == "cv"), None)
    if not cv_evidence:
        raise HTTPException(status_code=400, detail="No CV found for this candidate")
    
    settings = await get_ai_settings(current_user["id"])
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=400, detail="Configure OpenRouter API key first")
    
    admin_settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
    cv_parse_prompt = admin_settings.get("cv_parse_prompt") if admin_settings else None
    
    parsed_text = cv_evidence["content"]
    
    if cv_parse_prompt:
        prompt = cv_parse_prompt.format(cv_text=parsed_text[:3000])
    else:
        prompt = f"""Extract contact information from this CV/resume text.

CV TEXT (first 3000 chars):
{parsed_text[:3000]}

Return ONLY a JSON object with:
{{
  "name": "Full name of the candidate",
  "email": "Email address or empty string if not found",
  "phone": "Phone number or empty string if not found"
}}

Rules:
- Name should be the person's full name, NOT a company name or job title
- Phone should be a valid phone number format
- If information is unclear or not found, return empty string
- Do NOT make up information"""

    messages = [{"role": "user", "content": prompt}]
    response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages, temperature=0.1)
    
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    if json_start >= 0 and json_end > json_start:
        contact_info = json.loads(response[json_start:json_end])
        
        update_data = {
            "name": contact_info.get("name", candidate["name"]).strip() or candidate["name"],
            "email": contact_info.get("email", candidate["email"]).strip() or candidate["email"],
            "phone": contact_info.get("phone", candidate["phone"]).strip() or candidate["phone"],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.candidates.update_one({"id": candidate_id}, {"$set": update_data})
        
        updated = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
        return CandidateResponse(**updated)
    
    raise HTTPException(status_code=500, detail="Failed to parse CV")

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

# ==================== EXTENSION: ZIP UPLOAD & DUPLICATE DETECTION ====================
# NOTE: These endpoints are ADDITIVE and do not modify existing flows
# Existing upload-cv and check-duplicates endpoints remain unchanged

import zipfile
import re

# Helper: Normalize phone number for comparison (strip all non-digits)
def normalize_phone(phone: str) -> str:
    """Normalize phone number by removing all non-digit characters"""
    if not phone:
        return ""
    return re.sub(r'\D', '', phone)

# Helper: Normalize email for comparison (lowercase, strip whitespace)
def normalize_email(email: str) -> str:
    """Normalize email for comparison"""
    if not email:
        return ""
    return email.lower().strip()

# Helper: Normalize name for comparison (lowercase, strip extra whitespace)
def normalize_name(name: str) -> str:
    """Normalize name for comparison"""
    if not name:
        return ""
    return ' '.join(name.lower().split())

# Models for new endpoints
class DuplicateDetectionRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None

class DuplicateMatch(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_phone: str
    match_reasons: List[str]
    confidence: str  # "high", "medium"

class DuplicateDetectionResponse(BaseModel):
    has_duplicates: bool
    matches: List[DuplicateMatch]

class MergeRequest(BaseModel):
    source_candidate_id: str
    target_candidate_id: str

class MergeLogEntry(BaseModel):
    action: str
    source_id: str
    target_id: str
    source_name: str
    target_name: str
    evidence_transferred: int
    merged_by: str
    merged_at: str

@api_router.post("/candidates/detect-duplicates", response_model=DuplicateDetectionResponse)
async def detect_duplicates(
    data: DuplicateDetectionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    NEW ENDPOINT: Enhanced duplicate detection using hard rules.
    
    Checks for duplicates based on:
    1. Email match (case-insensitive)
    2. Phone match (normalized - digits only)
    3. Email + Name match combination
    
    Returns potential duplicates with match reasons for HR decision.
    Does NOT auto-merge - waits for explicit merge request.
    """
    if not current_user.get("company_id"):
        return DuplicateDetectionResponse(has_duplicates=False, matches=[])
    
    company_id = current_user["company_id"]
    matches = []
    
    # Normalize input values
    input_email = normalize_email(data.email) if data.email else ""
    input_phone = normalize_phone(data.phone) if data.phone else ""
    input_name = normalize_name(data.name) if data.name else ""
    
    # Skip if no data provided
    if not input_email and not input_phone and not input_name:
        return DuplicateDetectionResponse(has_duplicates=False, matches=[])
    
    # Get all candidates for this company
    candidates = await db.candidates.find(
        {"company_id": company_id},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1}
    ).to_list(10000)
    
    for candidate in candidates:
        match_reasons = []
        
        cand_email = normalize_email(candidate.get("email", ""))
        cand_phone = normalize_phone(candidate.get("phone", ""))
        cand_name = normalize_name(candidate.get("name", ""))
        
        # Rule 1: Email match (case-insensitive)
        if input_email and cand_email and input_email == cand_email:
            match_reasons.append("email_match")
        
        # Rule 2: Phone match (normalized)
        if input_phone and cand_phone and len(input_phone) >= 7 and len(cand_phone) >= 7:
            # Match if last 7+ digits are the same (handles country code differences)
            if input_phone[-7:] == cand_phone[-7:] or input_phone == cand_phone:
                match_reasons.append("phone_match")
        
        # Rule 3: Email + Name combination match
        if input_email and input_name and cand_email and cand_name:
            if input_email == cand_email and input_name == cand_name:
                if "email_match" not in match_reasons:
                    match_reasons.append("email_match")
                match_reasons.append("name_match")
        
        if match_reasons:
            # Determine confidence
            if "email_match" in match_reasons and ("phone_match" in match_reasons or "name_match" in match_reasons):
                confidence = "high"
            elif "email_match" in match_reasons:
                confidence = "high"
            elif "phone_match" in match_reasons:
                confidence = "medium"
            else:
                confidence = "medium"
            
            matches.append(DuplicateMatch(
                candidate_id=candidate["id"],
                candidate_name=candidate.get("name", ""),
                candidate_email=candidate.get("email", ""),
                candidate_phone=candidate.get("phone", ""),
                match_reasons=match_reasons,
                confidence=confidence
            ))
    
    return DuplicateDetectionResponse(
        has_duplicates=len(matches) > 0,
        matches=matches
    )

@api_router.post("/candidates/merge")
async def merge_candidates(
    data: MergeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    NEW ENDPOINT: Merge two candidates.
    
    - Appends all evidence from source candidate to target candidate
    - Does NOT overwrite any existing target candidate fields
    - Logs the merge action for audit purposes
    - Deletes the source candidate after successful merge
    
    Returns the updated target candidate.
    """
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    company_id = current_user["company_id"]
    
    # Fetch source candidate
    source = await db.candidates.find_one(
        {"id": data.source_candidate_id, "company_id": company_id},
        {"_id": 0}
    )
    if not source:
        raise HTTPException(status_code=404, detail="Source candidate not found")
    
    # Fetch target candidate
    target = await db.candidates.find_one(
        {"id": data.target_candidate_id, "company_id": company_id},
        {"_id": 0}
    )
    if not target:
        raise HTTPException(status_code=404, detail="Target candidate not found")
    
    # Prevent self-merge
    if data.source_candidate_id == data.target_candidate_id:
        raise HTTPException(status_code=400, detail="Cannot merge candidate with itself")
    
    now = datetime.now(timezone.utc).isoformat()
    source_evidence = source.get("evidence", [])
    
    # Append source evidence to target (do NOT overwrite existing)
    if source_evidence:
        # Mark transferred evidence with merge metadata
        for ev in source_evidence:
            ev["merged_from"] = data.source_candidate_id
            ev["merged_at"] = now
        
        await db.candidates.update_one(
            {"id": data.target_candidate_id},
            {
                "$push": {"evidence": {"$each": source_evidence}},
                "$set": {"updated_at": now}
            }
        )
    
    # Create merge log entry
    merge_log = {
        "id": str(uuid.uuid4()),
        "action": "candidate_merge",
        "source_id": data.source_candidate_id,
        "target_id": data.target_candidate_id,
        "source_name": source.get("name", ""),
        "target_name": target.get("name", ""),
        "source_email": source.get("email", ""),
        "target_email": target.get("email", ""),
        "evidence_transferred": len(source_evidence),
        "merged_by": current_user["id"],
        "merged_by_name": current_user.get("name", ""),
        "company_id": company_id,
        "merged_at": now
    }
    await db.merge_logs.insert_one(merge_log)
    
    # Delete source candidate
    await db.candidates.delete_one({"id": data.source_candidate_id})
    
    # Fetch and return updated target
    updated_target = await db.candidates.find_one({"id": data.target_candidate_id}, {"_id": 0})
    
    logger.info(f"Merged candidate {data.source_candidate_id} into {data.target_candidate_id}")
    
    return {
        "message": "Candidates merged successfully",
        "target_candidate": CandidateResponse(**updated_target),
        "evidence_transferred": len(source_evidence),
        "merge_log_id": merge_log["id"]
    }

@api_router.get("/candidates/merge-logs")
async def get_merge_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    """
    NEW ENDPOINT: Get merge audit logs for the company.
    """
    if not current_user.get("company_id"):
        return []
    
    logs = await db.merge_logs.find(
        {"company_id": current_user["company_id"]},
        {"_id": 0}
    ).sort("merged_at", -1).limit(limit).to_list(limit)
    
    return logs

class ZipUploadResponse(BaseModel):
    status: str  # "created", "duplicate_warning", "error"
    candidate: Optional[CandidateResponse] = None
    duplicates: Optional[List[DuplicateMatch]] = None
    message: str
    files_processed: int
    evidence_attached: int

@api_router.post("/candidates/upload-zip", response_model=ZipUploadResponse)
async def upload_zip(
    file: UploadFile = File(...),
    force_create: bool = Form(False),
    current_user: dict = Depends(get_current_user)
):
    """
    NEW ENDPOINT: Upload a ZIP file containing candidate evidence.
    
    One ZIP file = one candidate
    
    Expected ZIP structure:
    - CV/resume PDF (required): looked for in root or cv/ folder
    - Additional evidence: psychotest/, knowledge_test/, or evidence/ folders
    
    Process:
    1. Extract ZIP contents
    2. Find and parse CV to get candidate info
    3. Run duplicate detection BEFORE creating candidate
    4. If duplicates found and force_create=False: return warning
    5. If no duplicates or force_create=True: create candidate with all evidence
    
    Reuses existing PDF parsing logic.
    """
    if not current_user.get("company_id"):
        raise HTTPException(status_code=400, detail="Create a company first")
    
    if not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    
    company_id = current_user["company_id"]
    content = await file.read()
    
    try:
        zip_buffer = io.BytesIO(content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            
            # Find CV file (PDF in root or cv/ folder)
            cv_file = None
            cv_content = None
            evidence_files = []
            
            for fname in file_list:
                # Skip directories and hidden files
                if fname.endswith('/') or fname.startswith('__MACOSX') or '/.' in fname:
                    continue
                
                lower_fname = fname.lower()
                base_name = fname.split('/')[-1].lower()
                
                # Identify CV file
                if lower_fname.endswith('.pdf'):
                    # Priority: files in root or cv/ folder, or with cv/resume in name
                    is_cv = (
                        '/' not in fname or  # Root level
                        fname.lower().startswith('cv/') or
                        fname.lower().startswith('resume/') or
                        'cv' in base_name or
                        'resume' in base_name
                    )
                    
                    if is_cv and cv_file is None:
                        cv_file = fname
                        cv_content = zf.read(fname)
                    else:
                        # Treat as additional evidence
                        evidence_files.append({
                            "name": fname,
                            "content": zf.read(fname),
                            "type": categorize_evidence(fname)
                        })
                elif lower_fname.endswith(('.txt', '.doc', '.docx')):
                    # Other document types as evidence
                    evidence_files.append({
                        "name": fname,
                        "content": zf.read(fname),
                        "type": categorize_evidence(fname)
                    })
            
            if not cv_file or not cv_content:
                raise HTTPException(
                    status_code=400, 
                    detail="No CV/resume PDF found in ZIP. Please include a PDF file in the root or cv/ folder."
                )
            
            # Parse CV using existing function
            parsed_text = parse_pdf(cv_content)
            if not parsed_text:
                raise HTTPException(status_code=400, detail="Could not extract text from CV PDF")
            
            # Extract candidate info (reuse existing AI/fallback logic)
            settings = await get_ai_settings(current_user["id"])
            admin_settings = await db.admin_settings.find_one({"user_id": current_user["id"]}, {"_id": 0})
            
            name = ""
            email = ""
            phone = ""
            
            # AI parsing
            if settings.openrouter_api_key:
                try:
                    cv_parse_prompt = admin_settings.get("cv_parse_prompt") if admin_settings else None
                    
                    if cv_parse_prompt:
                        prompt = cv_parse_prompt.format(cv_text=parsed_text[:3000])
                    else:
                        prompt = f"""Extract contact information from this CV/resume text.

CV TEXT (first 3000 chars):
{parsed_text[:3000]}

Return ONLY a JSON object with:
{{
  "name": "Full name of the candidate",
  "email": "Email address or empty string if not found",
  "phone": "Phone number or empty string if not found"
}}

Rules:
- Name should be the person's full name, NOT a company name or job title
- Phone should be a valid phone number format
- If information is unclear or not found, return empty string
- Do NOT make up information"""

                    messages = [{"role": "user", "content": prompt}]
                    response = await call_openrouter(settings.openrouter_api_key, settings.model_name, messages, temperature=0.1)
                    
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        contact_info = json.loads(response[json_start:json_end])
                        name = contact_info.get("name", "").strip()
                        email = contact_info.get("email", "").strip()
                        phone = contact_info.get("phone", "").strip()
                except Exception as e:
                    logger.warning(f"AI CV parsing failed in ZIP upload, using fallback: {e}")
            
            # Fallback parsing (same as existing upload-cv)
            if not name:
                lines = parsed_text.split('\n')
                for line in lines[:10]:
                    line = line.strip()
                    if line and len(line) > 2 and len(line) < 50:
                        if not any(c.isdigit() for c in line) and '@' not in line:
                            name = line
                            break
                if not name:
                    name = "Unknown Candidate"
            
            if not email:
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                emails = re.findall(email_pattern, parsed_text)
                email = emails[0] if emails else ""
            
            if not phone:
                phone_patterns = [
                    r'\+?[\d\s\-\(\)]{10,}',
                    r'\d{3}[\s\-]?\d{3}[\s\-]?\d{4}',
                    r'\(\d{3}\)\s?\d{3}[\s\-]?\d{4}'
                ]
                for pattern in phone_patterns:
                    phones = re.findall(pattern, parsed_text[:1000])
                    if phones:
                        phone = phones[0].strip()
                        break
            
            # Run duplicate detection BEFORE creating
            if not force_create:
                dup_response = await detect_duplicates(
                    DuplicateDetectionRequest(email=email, phone=phone, name=name),
                    current_user
                )
                
                if dup_response.has_duplicates:
                    return ZipUploadResponse(
                        status="duplicate_warning",
                        candidate=None,
                        duplicates=dup_response.matches,
                        message=f"Found {len(dup_response.matches)} potential duplicate(s). Review and choose to merge or create new.",
                        files_processed=1 + len(evidence_files),
                        evidence_attached=0
                    )
            
            # Create candidate
            now = datetime.now(timezone.utc).isoformat()
            candidate_id = str(uuid.uuid4())
            
            # Build evidence list
            evidence_list = [{
                "type": "cv",
                "file_name": cv_file.split('/')[-1],
                "content": parsed_text,
                "uploaded_at": now,
                "source": "zip_upload"
            }]
            
            # Add additional evidence files
            for ev_file in evidence_files:
                if ev_file["content"]:
                    # Parse PDF or decode text
                    if ev_file["name"].lower().endswith('.pdf'):
                        try:
                            ev_content = parse_pdf(ev_file["content"])
                        except:
                            ev_content = "[Binary PDF - parsing failed]"
                    else:
                        try:
                            ev_content = ev_file["content"].decode('utf-8', errors='ignore')
                        except:
                            ev_content = "[Binary content]"
                    
                    evidence_list.append({
                        "type": ev_file["type"],
                        "file_name": ev_file["name"].split('/')[-1],
                        "content": ev_content,
                        "uploaded_at": now,
                        "source": "zip_upload"
                    })
            
            candidate = {
                "id": candidate_id,
                "company_id": company_id,
                "name": name,
                "email": email,
                "phone": phone,
                "evidence": evidence_list,
                "created_at": now,
                "updated_at": now,
                "upload_source": "zip"
            }
            
            await db.candidates.insert_one(candidate)
            
            logger.info(f"Created candidate {candidate_id} from ZIP upload with {len(evidence_list)} evidence files")
            
            return ZipUploadResponse(
                status="created",
                candidate=CandidateResponse(**candidate),
                duplicates=None,
                message=f"Candidate created successfully with {len(evidence_list)} evidence file(s)",
                files_processed=1 + len(evidence_files),
                evidence_attached=len(evidence_list)
            )
    
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ZIP upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process ZIP file: {str(e)}")

def categorize_evidence(filename: str) -> str:
    """Helper: Categorize evidence file based on path/name"""
    lower = filename.lower()
    
    if 'psycho' in lower or 'personality' in lower or 'assessment' in lower:
        return 'psychotest'
    elif 'knowledge' in lower or 'test' in lower or 'exam' in lower or 'quiz' in lower:
        return 'knowledge_test'
    elif 'cert' in lower or 'certificate' in lower or 'diploma' in lower:
        return 'certificate'
    elif 'portfolio' in lower or 'work' in lower or 'sample' in lower:
        return 'portfolio'
    elif 'reference' in lower or 'recommendation' in lower:
        return 'reference'
    else:
        return 'other'

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
