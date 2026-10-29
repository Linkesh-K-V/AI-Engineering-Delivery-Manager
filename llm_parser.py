import os
import re
import logging
from typing import Dict
from typesafe_sdk import TypeSafeClient, Choice, Score, Noul
from models import TaskExtraction, TaskPriority, SkillLevel

logger = logging.getLogger(__name__)

# Ensure TYPESAFE_API_KEY is defined in the environment if not already set
if "TYPESAFE_API_KEY" not in os.environ:
    os.environ["TYPESAFE_API_KEY"] = "mock-typesafe-key"

client = TypeSafeClient(model="jev-1.13.0")

DOMAIN_SKILLS_MAP: Dict[str, Dict[str, SkillLevel]] = {
    "backend": {
        "Python": SkillLevel.ADVANCED,
        "FastAPI": SkillLevel.INTERMEDIATE,
        "PostgreSQL": SkillLevel.INTERMEDIATE,
    },
    "frontend": {
        "React": SkillLevel.ADVANCED,
        "TypeScript": SkillLevel.INTERMEDIATE,
        "UI/UX": SkillLevel.BASIC,
    },
    "devops": {
        "Docker": SkillLevel.ADVANCED,
        "CI/CD": SkillLevel.INTERMEDIATE,
        "AWS": SkillLevel.ADVANCED,
    },
    "ai_ml": {
        "Python": SkillLevel.ADVANCED,
        "PyTorch": SkillLevel.INTERMEDIATE,
        "LLMs": SkillLevel.ADVANCED,
    },
}

def _heuristic_domain(prompt: str) -> str:
    if re.search(r'\b(?:react|typescript|frontend|ui|ux|css|html|figma|designer)\b', prompt, re.IGNORECASE):
        return "frontend"
    elif re.search(r'\b(?:docker|kubernetes|aws|devops|ci/cd|cicd|pipeline|deploy|infrastructure)\b', prompt, re.IGNORECASE):
        return "devops"
    elif re.search(r'\b(?:ai|ml|machine learning|pytorch|model|models|llm|llms|llama|nlp)\b', prompt, re.IGNORECASE):
        return "ai_ml"
    elif re.search(r'\b(?:backend|api|apis|fastapi|python|sql|postgres|postgresql|database|db|server)\b', prompt, re.IGNORECASE):
        return "backend"
    return "backend"

def _heuristic_priority_score(prompt: str) -> float:
    if re.search(r'\b(?:urgent|asap|critical|immediately|emergency|high)\b', prompt, re.IGNORECASE):
        return 2.0
    elif re.search(r'\b(?:medium|soon|next sprint|feature)\b', prompt, re.IGNORECASE):
        return 1.0
    return 0.0

def _heuristic_requires_review(prompt: str) -> bool:
    return bool(re.search(r'\b(?:critical|outage|risk|security|production|prod)\b', prompt, re.IGNORECASE))

def parse_manager_request(prompt: str) -> TaskExtraction:
    """
    System 1 (Jev / TypeSafe AI):
    Parses unstructured manager requests into a strictly validated TaskExtraction object
    using deterministic, fast type extraction.
    """
    questions = {
        "domain": Choice(
            instructions="Select the primary technical domain for this task",
            criteria={
                "backend": "Backend development, APIs, servers, databases, Python, FastAPI",
                "frontend": "Frontend development, UI/UX, React, TypeScript, web interfaces",
                "devops": "DevOps, infrastructure, CI/CD, Docker, AWS, cloud deployment",
                "ai_ml": "AI/ML engineering, LLMs, data science, PyTorch, model training"
            }
        ),
        "priority": Score(
            instructions="Assess the priority or urgency level of this task",
            criteria=["low", "medium", "high"]
        ),
        "requires_review": Noul(
            instructions="Does this task imply high risk, security impact, or critical compliance review?"
        )
    }

    try:
        response = client.system_one(prompt, questions)
        domain_answer = response.answers["domain"]
        priority_answer = response.answers["priority"]
        review_answer = response.answers["requires_review"]

        domain_choice = getattr(domain_answer, "choice", "backend")
        priority_score = getattr(priority_answer, "score", 1.0)
        requires_review = getattr(review_answer, "noul", 0.0) >= 0.5
    except Exception as e:
        logger.warning("TypeSafe System 1 API call not reachable or unauthenticated (%s). Using deterministic parser.", e)
        domain_choice = _heuristic_domain(prompt)
        priority_score = _heuristic_priority_score(prompt)
        requires_review = _heuristic_requires_review(prompt)

    # Map priority score & requires_review to TaskPriority
    if priority_score >= 1.5:
        priority = TaskPriority.CRITICAL if requires_review else TaskPriority.HIGH
    elif priority_score >= 0.5:
        priority = TaskPriority.MEDIUM
    else:
        priority = TaskPriority.LOW

    # Map domain to SkillLevel keys
    skills = dict(DOMAIN_SKILLS_MAP.get(domain_choice, DOMAIN_SKILLS_MAP["backend"]))

    # Augment with recognized skills explicitly mentioned in prompt
    skill_patterns = [
        (r'\bpython\b', "Python", SkillLevel.ADVANCED),
        (r'\b(?:postgres|postgresql)\b', "PostgreSQL", SkillLevel.INTERMEDIATE),
        (r'\bfastapi\b', "FastAPI", SkillLevel.ADVANCED),
        (r'\breact\b', "React", SkillLevel.ADVANCED),
        (r'\btypescript\b', "TypeScript", SkillLevel.ADVANCED),
        (r'\bdocker\b', "Docker", SkillLevel.ADVANCED),
        (r'\baws\b', "AWS", SkillLevel.ADVANCED),
        (r'\b(?:ci/cd|cicd)\b', "CI/CD", SkillLevel.ADVANCED),
        (r'\bpytorch\b', "PyTorch", SkillLevel.ADVANCED),
        (r'\b(?:llm|llms)\b', "LLMs", SkillLevel.ADVANCED),
        (r'\btesting\b', "Testing", SkillLevel.ADVANCED),
        (r'\bqa\b', "Testing", SkillLevel.ADVANCED),
        (r'\bsql\b', "SQL", SkillLevel.INTERMEDIATE),
        (r'\bfigma\b', "Figma", SkillLevel.ADVANCED),
    ]
    for pattern, s_name, s_level in skill_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            skills[s_name] = s_level

    # Extract effort if specified
    match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hours|hrs|hour|h\b)', prompt, re.IGNORECASE)
    estimated_effort = float(match.group(1)) if match else 8.0

    # Build title & description
    clean_prompt = prompt.strip()
    first_line = clean_prompt.split('\n')[0].strip()
    title = first_line[:60] if len(first_line) > 60 else first_line
    if not title:
        title = f"{domain_choice.capitalize()} Task"
    description = clean_prompt

    return TaskExtraction(
        title=title,
        description=description,
        priority=priority,
        required_skills=skills,
        estimated_effort_hours=estimated_effort
    )
