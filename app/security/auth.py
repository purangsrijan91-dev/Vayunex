"""Authentication and Role-Based Access Control (RBAC) Module.

Enforces role boundaries across Disaster Commanders, Insurance Underwriters,
and Field Operators via API Keys and Role headers.
"""
from enum import Enum
from typing import List, Optional
from fastapi import Header, HTTPException, Security, status
from app.config import settings


class AegisRole(str, Enum):
    DISASTER_COMMANDER = "DISASTER_COMMANDER"
    INSURANCE_UNDERWRITER = "INSURANCE_UNDERWRITER"
    FIELD_OPERATOR = "FIELD_OPERATOR"


# API Key to Role Mapping
API_KEY_ROLE_MAP = {
    settings.API_KEY_DISASTER_COMMANDER: AegisRole.DISASTER_COMMANDER,
    settings.API_KEY_INSURANCE_UNDERWRITER: AegisRole.INSURANCE_UNDERWRITER,
    settings.API_KEY_FIELD_OPERATOR: AegisRole.FIELD_OPERATOR
}


def authenticate_role(
    x_aegis_role: Optional[str] = Header(None, alias="X-Aegis-Role"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> AegisRole:
    """Resolve and authenticate caller role via API Key or explicit Role header.

    If an API key is provided, it must match configured secrets and takes precedence.
    If no API key is provided, X-Aegis-Role is accepted for operational UI/demo mode.
    Defaults to FIELD_OPERATOR if neither is specified.
    """
    if x_api_key:
        role = API_KEY_ROLE_MAP.get(x_api_key)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked Aegis API Key"
            )
        return role

    if x_aegis_role:
        try:
            return AegisRole(x_aegis_role.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unrecognized X-Aegis-Role. Supported: {[r.value for r in AegisRole]}"
            )

    # Default to least-privilege role
    return AegisRole.FIELD_OPERATOR


def require_roles(allowed_roles: List[AegisRole]):
    """FastAPI dependency factory enforcing that caller role is in allowed_roles."""
    def role_checker(current_role: AegisRole = Security(authenticate_role)) -> AegisRole:
        if current_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for role [{current_role.value}]. Required: {[r.value for r in allowed_roles]}"
            )
        return current_role
    return role_checker
