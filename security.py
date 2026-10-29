from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

VALID_TOKENS = {
    "mgr-token-777": "manager",
    "emp-token-888": "employee",
}

def require_manager(api_key: str = Security(api_key_header)) -> str:
    role = VALID_TOKENS.get(api_key)
    if role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Manager access required"
        )
    return role

def require_employee(api_key: str = Security(api_key_header)) -> str:
    role = VALID_TOKENS.get(api_key)
    if role not in ("employee", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Employee or Manager access required"
        )
    return role
