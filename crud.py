import uuid
from typing import List, Optional
from sqlmodel import Session, select
from database import engine
from models import (
    Employee,
    Task,
    TaskExtraction,
    TaskStatus,
    HistoricalTaskLog,
    CalendarEvent,
)

def get_all_employees(session: Optional[Session] = None) -> List[Employee]:
    """Retrieve all employees from the database."""
    if session is None:
        with Session(engine) as local_session:
            return get_all_employees(session=local_session)
    statement = select(Employee)
    return list(session.exec(statement).all())

def get_all_tasks(session: Optional[Session] = None) -> List[Task]:
    """Retrieve all tasks from the database."""
    if session is None:
        with Session(engine) as local_session:
            return get_all_tasks(session=local_session)
    statement = select(Task)
    return list(session.exec(statement).all())

def get_employee_active_tasks(employee_id: str, session: Optional[Session] = None) -> List[Task]:
    """Retrieve active (not Done) tasks assigned to a specific employee."""
    if session is None:
        with Session(engine) as local_session:
            return get_employee_active_tasks(employee_id, session=local_session)
    statement = select(Task).where(
        Task.assigned_to == employee_id,
        Task.status != TaskStatus.DONE
    )
    return list(session.exec(statement).all())

def execute_task_assignment(
    task_req: TaskExtraction,
    assigned_employee_id: str,
    session: Optional[Session] = None
) -> Task:
    """
    Takes the approved task requirements, generates a unique ID,
    assigns it to the employee, and saves it to the database.
    """
    if session is None:
        with Session(engine) as local_session:
            return execute_task_assignment(task_req, assigned_employee_id, session=local_session)

    new_task_id = f"T-{str(uuid.uuid4())[:6].upper()}"
    new_task = Task(
        task_id=new_task_id,
        title=task_req.title,
        description=task_req.description,
        project="Ad-hoc Manager Request",
        priority=task_req.priority,
        required_skills=task_req.required_skills,
        estimated_effort_hours=task_req.estimated_effort_hours,
        status=TaskStatus.TODO,
        assigned_to=assigned_employee_id,
    )
    session.add(new_task)
    session.commit()
    session.refresh(new_task)
    return new_task

def get_task_history(session: Optional[Session] = None) -> List[HistoricalTaskLog]:
    """Retrieve all historical task logs from the database."""
    if session is None:
        with Session(engine) as local_session:
            return get_task_history(session=local_session)
    statement = select(HistoricalTaskLog)
    return list(session.exec(statement).all())

def get_employee_calendar(employee_id: str) -> List[CalendarEvent]:
    """Retrieve calendar events for an employee from mock calendar."""
    from mock_data import MOCK_CALENDAR
    return [event for event in MOCK_CALENDAR if event.employee_id == employee_id]
