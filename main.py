from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import asyncio
import json
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session, create_db_and_tables
from crud import (
    get_all_employees,
    get_all_tasks,
    get_employee_active_tasks,
    execute_task_assignment,
    get_task_history,
)
from models import (
    Employee,
    Task,
    WorkloadSummary,
    TaskExtraction,
    CandidateProfile,
    ManagerApprovalRequest,
    ApprovalDecision,
    ImpactReport,
    AuditLogEntry,
    TaskDecompositionResult,
    TaskCompletionRecord,
    HistoricalTaskLog,
    EndToEndRequest,
)
from workload_engine import calculate_employee_capacity
from llm_parser import parse_manager_request
from candidate_engine import rank_candidates
from llm_reasoner import generate_recommendation
from employee_agent import analyze_employee_impact
from simulator_engine import simulate_employee_absence
from audit_service import record_audit_event, get_audit_logs
from decomposition_engine import evaluate_and_decompose_task
from agent_graph import orchestrator_app
from learning_engine import record_task_completion, get_employee_calibration_factor
from integration_service import dispatch_to_ticketing_system, send_team_notification
from security import require_manager, require_employee

WEBHOOK_URL = "https://httpbin.org/post"

app = FastAPI(
    title="AI Delivery Manager API",
    description="Backend for the Intelligent Workforce Management System",
    version="0.1.0"
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def health_check():
    return {"status": "ok", "message": "AI Delivery Manager API is running"}

@app.get("/api/employees", response_model=List[Employee])
def list_employees(session: Session = Depends(get_session)):
    """Retrieve all employees in the organization."""
    return get_all_employees(session=session)

@app.get("/api/tasks", response_model=List[Task])
def list_tasks(session: Session = Depends(get_session)):
    """Retrieve all tasks in the system."""
    return get_all_tasks(session=session)

@app.get("/api/employees/{employee_id}/workload", response_model=WorkloadSummary)
def get_employee_workload(employee_id: str, days: int = 5, session: Session = Depends(get_session)):
    """Calculate the remaining capacity for a specific employee."""
    employees = get_all_employees(session=session)
    employee = next((e for e in employees if e.employee_id == employee_id), None)
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    return calculate_employee_capacity(employee, days, session=session)

class DecomposeRequest(BaseModel):
    prompt: str
    target_deadline_days: Optional[float] = 3.0

@app.post("/api/tasks/decompose", response_model=TaskDecompositionResult)
def decompose_large_task(request: DecomposeRequest):
    """
    Analyzes whether a request is a compound task, decomposes it into 
    subtasks with dependencies, and evaluates deadline feasibility.
    """
    try:
        plan = evaluate_and_decompose_task(
            manager_prompt=request.prompt,
            target_deadline_days=request.target_deadline_days or 3.0
        )
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decomposition failed: {str(e)}")

class TaskRequest(BaseModel):
    prompt: str

@app.post("/api/tasks/analyze", response_model=TaskExtraction)
def analyze_task_request(request: TaskRequest):
    """Converts a natural language prompt into a structured task definition."""
    try:
        parsed_task = parse_manager_request(request.prompt)
        return parsed_task
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Parsing failed: {str(e)}")

@app.post("/api/candidates/rank", response_model=List[CandidateProfile])
def get_ranked_candidates(task: TaskExtraction, session: Session = Depends(get_session)):
    """
    Takes a structured task definition and returns a deterministically 
    ranked list of employee candidates based on skills and workload.
    """
    try:
        candidates = rank_candidates(task, session=session)
        return candidates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ranking failed: {str(e)}")

@app.post("/api/workflow/recommend", response_model=dict)
def full_recommendation_workflow(request: EndToEndRequest, session: Session = Depends(get_session)):
    """
    Executes the task allocation pipeline via a compiled LangGraph state machine.
    """
    initial_state = {
        "manager_prompt": request.manager_prompt,
        "parsed_task": None,
        "top_candidates": [],
        "ai_recommendation": None,
        "error": None,
        "session": session,
        "rejected_candidates": request.rejected_candidates
    }
    
    # Run the state graph synchronously
    final_state = orchestrator_app.invoke(initial_state)
    
    if final_state.get("error"):
        raise HTTPException(status_code=500, detail=final_state["error"])
        
    task_req = final_state["parsed_task"]
    rec = final_state["ai_recommendation"]
    candidates = final_state["top_candidates"]
    
    # Keep our audit ledger intact
    record_audit_event(
        event_type="AI_RECOMMENDATION_GENERATED",
        task_title=task_req.title,
        target_employee_id=rec.recommended_employee_id,
        ai_confidence=rec.confidence,
        details={
            "orchestrator": "LangGraph_v0.1",
            "reasoning_summary": rec.reasoning[:120] + "...",
            "candidate_pool_size": str(len(candidates))
        },
        session=session
    )
    
    return {
        "parsed_task": task_req,
        "top_candidates": candidates,
        "ai_recommendation": rec
    }

@app.post("/api/workflow/stream")
async def stream_workflow(request: EndToEndRequest, session: Session = Depends(get_session), user_role: str = Depends(require_manager)):
    """
    Executes the task allocation pipeline yielding SSE events to the client.
    """
    async def event_generator():
        try:
            # 1. Yield parsing status
            yield f"data: {json.dumps({'status': 'parsing', 'message': '⚡ System 1 (Jev) parsing parameters with strict type safety...'})}\n\n"
            await asyncio.sleep(0.1)

            # 2. Extract task details
            parsed_task = parse_manager_request(request.manager_prompt)

            # 3. Yield ranking status
            ranking_msg = (
                f"⚙️ Task extracted. Calculating capacity (excluding {len(request.rejected_candidates)} rejected candidates)..."
                if request.rejected_candidates
                else "⚙️ Task extracted. Calculating deterministic capacity..."
            )
            yield f"data: {json.dumps({'status': 'ranking', 'message': ranking_msg})}\n\n"
            await asyncio.sleep(0.1)

            # 4. Rank candidates with session and rejected_candidates
            candidates = rank_candidates(
                parsed_task,
                session=session,
                rejected_candidates=request.rejected_candidates
            )
            top_candidates = candidates[:3]

            # 5. Yield reasoning status
            yield f"data: {json.dumps({'status': 'reasoning', 'message': '🧠 System 2 (Llama 3) generating natural language trade-off analysis...'})}\n\n"
            await asyncio.sleep(0.1)

            # 6. Generate recommendation
            rec = generate_recommendation(parsed_task, top_candidates)

            # 7. Record audit log
            record_audit_event(
                event_type="AI_RECOMMENDATION_GENERATED",
                task_title=parsed_task.title,
                target_employee_id=rec.recommended_employee_id,
                ai_confidence=rec.confidence,
                details={
                    "orchestrator": "SSE_Streaming_Pipeline",
                    "reasoning_summary": rec.reasoning[:120] + "...",
                    "candidate_pool_size": str(len(top_candidates))
                },
                session=session
            )

            # 8. Yield complete status with final payload
            final_payload = {
                "status": "complete",
                "parsed_task": parsed_task.model_dump(mode="json"),
                "ai_recommendation": rec.model_dump(mode="json")
            }
            yield f"data: {json.dumps(final_payload)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'Pipeline failed: {str(e)}'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/workflow/approve")
async def process_manager_approval(approval: ManagerApprovalRequest, session: Session = Depends(get_session), user_role: str = Depends(require_manager)):
    """
    The final Human-in-the-Loop step. Executes the assignment only if approved.
    """
    if approval.decision == ApprovalDecision.APPROVE:
        # Query recommended employee from database
        employee = session.get(Employee, approval.recommended_employee_id)
        assignee_name = employee.name if employee else approval.recommended_employee_id

        # Dispatch to external ticketing system
        ticket_id = dispatch_to_ticketing_system(
            task_title=approval.parsed_task.title,
            task_description=approval.parsed_task.description,
            assignee_name=assignee_name,
            effort_hours=approval.parsed_task.estimated_effort_hours
        )

        # Send team webhook notification (Slack/Teams)
        notification_success = await send_team_notification(
            webhook_url=WEBHOOK_URL,
            task_title=approval.parsed_task.title,
            assignee_name=assignee_name,
            ticket_id=ticket_id
        )

        # Record manager decision in audit trail with external_ticket_id and notification status
        record_audit_event(
            event_type="MANAGER_DECISION",
            task_title=approval.parsed_task.title,
            target_employee_id=approval.recommended_employee_id,
            manager_decision=approval.decision.value,
            details={
                "feedback": approval.manager_feedback or "None",
                "external_ticket_id": ticket_id,
                "notification_sent": notification_success
            },
            session=session
        )

        # Execute the database transaction
        new_task = execute_task_assignment(
            task_req=approval.parsed_task, 
            assigned_employee_id=approval.recommended_employee_id,
            session=session
        )
        return {
            "status": "Success",
            "message": f"Task officially assigned to {approval.recommended_employee_id}",
            "task": new_task,
            "ticket_id": ticket_id
        }
        
    elif approval.decision == ApprovalDecision.REJECT:
        # Record manager decision in audit trail
        record_audit_event(
            event_type="MANAGER_DECISION",
            task_title=approval.parsed_task.title,
            target_employee_id=approval.recommended_employee_id,
            manager_decision=approval.decision.value,
            details={"feedback": approval.manager_feedback or "None"},
            session=session
        )
        return {
            "status": "Rejected",
            "message": "Recommendation rejected by manager. Task was not created.",
            "feedback_logged": approval.manager_feedback
        }

class EmployeeMessageRequest(BaseModel):
    employee_id: str
    message: str

@app.post("/api/employee/request", response_model=ImpactReport)
def process_employee_message(request: EmployeeMessageRequest, session: Session = Depends(get_session)):
    """
    Processes an employee's natural language request, determines the impact 
    on their workload, and prepares a report for the manager.
    """
    try:
        report = analyze_employee_impact(request.employee_id, request.message, session=session)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Impact Analysis failed: {str(e)}")

@app.get("/api/simulate/absence/{employee_id}")
def run_absence_simulation(employee_id: str, session: Session = Depends(get_session), user_role: str = Depends(require_manager)):
    """
    Runs a Level 1 Bounded Simulation: What happens to active tasks if this employee disappears?
    Does NOT mutate the database.
    """
    try:
        report = simulate_employee_absence(employee_id, session=session)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/dashboard")
def get_dashboard():
    return FileResponse("static/index.html")

@app.get("/api/audit/logs", response_model=List[AuditLogEntry])
def read_audit_logs(session: Session = Depends(get_session)):
    """Retrieve immutable audit trail for compliance and explainability auditing."""
    return get_audit_logs(session=session)

@app.post("/api/tasks/complete", response_model=dict)
def complete_task(record: TaskCompletionRecord, session: Session = Depends(get_session), user_role: str = Depends(require_employee)):
    """
    Marks a task as completed, logs actual effort vs estimated effort, 
    and refines the learning loop.
    """
    log_entry = record_task_completion(record, session=session)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Task not found or not assigned")
        
    return {
        "status": "Task marked Done",
        "historical_log": log_entry,
        "new_calibration_factor": get_employee_calibration_factor(log_entry.employee_id, session=session)
    }

@app.get("/api/analytics/historical", response_model=List[HistoricalTaskLog])
def list_history(session: Session = Depends(get_session)):
    """Retrieve full historical logs for audit and performance tracking."""
    return get_task_history(session=session)

@app.get("/api/dashboard/overview")
def get_dashboard_overview(session: Session = Depends(get_session), user_role: str = Depends(require_manager)):
    """Returns organizational capacity, active tasks, and latest audit logs."""
    employees = get_all_employees(session=session)
    overview = []
    
    for emp in employees:
        workload = calculate_employee_capacity(emp, days=5, session=session)
        tasks = get_employee_active_tasks(emp.employee_id, session=session)
        overview.append({
            "employee_id": emp.employee_id,
            "name": emp.name,
            "role": emp.role,
            "skills": emp.skills,
            "remaining_capacity": workload.remaining_capacity,
            "meeting_hours": workload.meeting_hours,
            "active_tasks_count": len(tasks)
        })
        
    return {
        "team_workload": overview,
        "recent_audits": get_audit_logs(session=session)[:5],
        "active_task_count": len([t for t in get_all_tasks(session=session) if t.status != "Done"])
    }