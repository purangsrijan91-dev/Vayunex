"""Spatial Boundary Validation and Prompt Injection Defense.

Safeguards the reasoning pipeline against physically impossible inland coordinates
and adversarial prompt injection vectors in meteorological inputs.
"""
import re
from typing import Tuple
from app.config import settings


class SpatialBoundaryError(ValueError):
    """Raised when spatial coordinates violate physical coastal boundaries."""
    pass


class PromptInjectionError(ValueError):
    """Raised when user-supplied strings match known jailbreak or injection patterns."""
    pass


# High-risk prompt injection keywords and control token regexes
INJECTION_PATTERNS = [
    r"\bignore\s+previous\s+instructions\b",
    r"\bsystem\s+prompt\b",
    r"\bdisregard\s+(all\s+)?prior\b",
    r"\byou\s+are\s+now\s+a\b",
    r"\bjailbreak\b",
    r"<\|im_start\|>",
    r"<\|endoftext\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"\bact\s+as\s+unrestricted\b",
    r"\bprint\s+system\s+instructions\b"
]
COMPILED_INJECTION_REGEX = re.compile("|".join(INJECTION_PATTERNS), flags=re.IGNORECASE)


def validate_coastal_coordinates(lat: float, lon: float) -> Tuple[float, float]:
    """Validate that coordinates are physically located within the active coastal envelope.

    Prevents hallucinated storm surge modeling in non-coastal inland territories
    (e.g., Delhi, Nagpur, Hyderabad) and enforces correct (latitude, longitude) axis ordering.
    """
    # 1. Axis & range bounds check
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise SpatialBoundaryError(
            f"Coordinates out of physical bounds: lat={lat}, lon={lon}. Expected -90<=lat<=90, -180<=lon<=180."
        )

    # 2. Check for axis-inversion bug (e.g., passing lon ~86 as latitude)
    if lat > 35.0 or lon < 60.0 or lon > 100.0:
        raise SpatialBoundaryError(
            f"Potential axis-inversion detected: lat={lat}, lon={lon}. Coordinates must represent Indian subcontinental latitudes."
        )

    # 3. Physical coastal storm surge envelope check (Bay of Bengal active surge zone)
    min_lat, min_lon, max_lat, max_lon = settings.EAST_COAST_ENVELOPE
    if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
        raise SpatialBoundaryError(
            f"Coordinate ({lat:.4f}, {lon:.4f}) is outside the active coastal storm surge envelope "
            f"[{min_lat}N-{max_lat}N, {min_lon}E-{max_lon}E]. Storm surge modeling is physically invalid for inland locations."
        )

    return lat, lon


def validate_sector_bounds(sector_name: str, lat: float, lon: float) -> bool:
    """Check if coordinates fall inside the designated sector bounding box."""
    sector_info = settings.COASTAL_SECTORS.get(sector_name)
    if not sector_info:
        # If not a recognized sector key, fallback to envelope check
        validate_coastal_coordinates(lat, lon)
        return True

    min_lat, min_lon, max_lat, max_lon = sector_info["bbox"]
    # Allow small 0.1 degree buffer for peripheral asset networks
    buffer = 0.1
    if not ((min_lat - buffer) <= lat <= (max_lat + buffer) and (min_lon - buffer) <= lon <= (max_lon + buffer)):
        raise SpatialBoundaryError(
            f"Asset coordinate ({lat:.4f}, {lon:.4f}) falls outside specified sector '{sector_name}' "
            f"bounding box [{min_lat}, {min_lon}, {max_lat}, {max_lon}]."
        )
    return True


def sanitize_text_input(text: str, max_length: int = 250) -> str:
    """Sanitize user-provided text inputs against prompt injection and control character abuse."""
    if not text:
        return ""

    # Truncate excessive input
    cleaned = text.strip()[:max_length]

    # Check for adversarial prompt injection attempts
    if COMPILED_INJECTION_REGEX.search(cleaned):
        raise PromptInjectionError("Input rejected: contains disallowed instruction bypass patterns.")

    # Remove non-printable or dangerous control characters
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", cleaned)

    # Escape raw curly braces to prevent format string interpolation exploits
    cleaned = cleaned.replace("{", "{{").replace("}", "}}")

    return cleaned
