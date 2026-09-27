"""Security and boundary protection module."""
from app.security.auth import (
    AegisRole,
    authenticate_role,
    require_roles
)
from app.security.sanitizer import (
    SpatialBoundaryError,
    PromptInjectionError,
    validate_coastal_coordinates,
    validate_sector_bounds,
    sanitize_text_input
)

__all__ = [
    "AegisRole",
    "authenticate_role",
    "require_roles",
    "SpatialBoundaryError",
    "PromptInjectionError",
    "validate_coastal_coordinates",
    "validate_sector_bounds",
    "sanitize_text_input"
]
