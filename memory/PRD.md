# TalentAI - AI CV Screening Platform

## Product Overview
AI-powered CV screening platform helping HR teams reduce time spent on candidate evaluation using explainable, weighted, and configurable AI scoring.

## User Personas
- **Primary**: HR Recruiters - Need to screen large volumes of CVs efficiently
- **Secondary**: Hiring Managers - Need to review shortlisted candidates with clear reasoning

## Core Requirements
1. **Authentication**: JWT-based email/password authentication
2. **Company Settings**: Company profile and configurable company values with weights
3. **Job Vacancies**: Job descriptions with AI-generated evaluation playbooks
4. **Talent Pool**: CV upload, parsing, and candidate evidence management
5. **Job Fit Analysis**: AI-powered batch scoring with explainable reasoning
6. **Settings**: OpenRouter API configuration, model selection, language preferences

## Tech Stack
- **Frontend**: React + Tailwind CSS + shadcn/ui
- **Backend**: FastAPI + Python
- **Database**: MongoDB
- **AI**: OpenRouter API (configurable)

## Implementation Status

### ✅ Completed (Phase 1 MVP) - January 21, 2025
- User registration and login with JWT auth
- Dashboard with KPI cards and activity feed
- Company settings with General Info and Company Values tabs
- AI-powered company values generation
- Job vacancy CRUD with AI-generated descriptions
- Evaluation playbook generation (Character/Requirement/Skill categories)
- Talent Pool with PDF CV upload and parsing
- Candidate evidence management
- Job Fit Analysis with batch AI scoring
- Explainable scoring with category breakdowns
- Shortlist filtering by minimum score
- Settings page (API key, model, language)
- Responsive sidebar navigation
- Modern pastel SaaS UI design

### ✅ Bug Fixes - January 22, 2026
- **ObjectId Serialization**: Fixed `serialize_doc` helper to recursively convert MongoDB ObjectIds to strings
- **Deleted Candidate Handling**: Analysis results now show "[Deleted] Candidate Name" for removed candidates
- **Duplicate Candidate Detection**: `/api/candidates/check-duplicates` endpoint with frontend confirmation dialog
- **Analysis Modal Scrollability**: Modal now properly scrolls with `h-[85vh]` and `overflow-y-auto`
- **Bulk Delete Analysis**: Added bulk delete functionality for analysis results
- **Route Ordering**: Fixed `/candidates/search` route to be matched before `/candidates/{candidate_id}`
- **Super Admin Settings**: Page at `/admin-settings` for configuring AI prompts

### 🔄 P0 Features (High Priority)
- Bulk CV upload progress indicator
- Export analysis results to CSV/PDF
- Email notifications for completed analyses

### 📋 P1 Features (Medium Priority)
- Job status management (open/closed/draft)
- Analysis comparison view

### 📝 P2 Features (Lower Priority)
- Team member management
- Role-based access control
- Analytics dashboard with charts
- API rate limiting dashboard

## Scoring Model
1. AI scores each playbook criterion (0-100)
2. Scores are normalized and weighted per subcategory
3. Category scores aggregated (Character, Requirement, Skill)
4. Final score calculated as weighted average (0-100)
5. Explainable reasoning provided with evidence references

## Language Support
- English (default)
- Indonesian (Bahasa Indonesia)
- All AI outputs follow selected language setting

## API Endpoints
- `/api/auth/*` - Authentication
- `/api/company` - Company management
- `/api/jobs/*` - Job vacancy management
- `/api/candidates/*` - Candidate management
- `/api/analysis/*` - Job fit analysis
- `/api/settings` - User settings
- `/api/dashboard/*` - Dashboard statistics

## Next Steps
1. Configure OpenRouter API key in Settings
2. Create company profile and values
3. Create job vacancies and generate playbooks
4. Upload candidate CVs
5. Run batch analysis
6. Review and shortlist candidates
