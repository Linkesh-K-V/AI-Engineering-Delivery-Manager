from sqlmodel import Session, select
from database import engine, create_db_and_tables
from models import Employee, Task, HistoricalTaskLog
from mock_data import MOCK_EMPLOYEES, MOCK_TASKS, MOCK_HISTORY

def seed_database():
    """Seeds the SQLite database with mock data if tables are empty."""
    create_db_and_tables()
    with Session(engine) as session:
        # 1. Seed Employees
        existing_employee = session.exec(select(Employee)).first()
        if existing_employee is None:
            print(f"Seeding {len(MOCK_EMPLOYEES)} employees...")
            for emp in MOCK_EMPLOYEES:
                session.add(emp)
            session.commit()
            print("Employees successfully seeded.")
        else:
            print("Employees table is not empty. Skipping employee seeding.")

        # 2. Seed Tasks
        existing_task = session.exec(select(Task)).first()
        if existing_task is None:
            print(f"Seeding {len(MOCK_TASKS)} tasks...")
            for task in MOCK_TASKS:
                session.add(task)
            session.commit()
            print("Tasks successfully seeded.")
        else:
            print("Tasks table is not empty. Skipping task seeding.")

        # 3. Seed HistoricalTaskLogs
        existing_history = session.exec(select(HistoricalTaskLog)).first()
        if existing_history is None:
            print(f"Seeding {len(MOCK_HISTORY)} historical task logs...")
            for history in MOCK_HISTORY:
                session.add(history)
            session.commit()
            print("Historical task logs successfully seeded.")
        else:
            print("HistoricalTaskLog table is not empty. Skipping history seeding.")

if __name__ == "__main__":
    seed_database()
