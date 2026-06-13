from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import datetime
import uuid

# ── Color map (server-derived from zone_type) ────────────────────────────────

ZONE_COLOR_MAP: dict[str, str] = {
    "campus":    "#22c55e",
    "red":       "#ef4444",
    "purple":    "#a855f7",
    "black":     "#1f2937",
    # Legacy types kept for backward compat
    "university": "#1FA663",
    "rape":      "#0B0B0B",
    "murder":    "#7B2CBF",
    "alert":     "#E8312A",
}


def zone_color(zone_type: str) -> str:
    return ZONE_COLOR_MAP.get(zone_type, "#E8312A")


# ── Public read schema ────────────────────────────────────────────────────────

class ZoneResponse(BaseModel):
    """Returned by all public zone read endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: Optional[str] = None
    zone_type: str
    shape_type: str = "circle"
    polygon_coords: Optional[list] = None
    center_lat: float
    center_lng: float
    radius_m: Optional[int] = None
    description_public: Optional[str] = None
    color: str = "#E8312A"
    status: str
    expires_at: Optional[datetime] = None
    label: Optional[str] = None
    tenant_id: Optional[uuid.UUID] = None
    created_at: datetime

    @classmethod
    def from_orm_with_color(cls, zone) -> "ZoneResponse":
        obj = cls.model_validate(zone)
        obj.color = zone_color(zone.zone_type.value if hasattr(zone.zone_type, 'value') else zone.zone_type)
        return obj


# ── Create schema (used by both admin and super-admin routers) ────────────────

class ZoneCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    zone_type: Literal["campus", "purple", "black", "red"]
    shape_type: Literal["polygon", "circle"]
    polygon_coords: Optional[list[list[float]]] = Field(
        default=None,
        description="[[lat, lng], ...] — required for polygon, null for circle",
    )
    center_lat: float = Field(..., ge=-90, le=90)
    center_lng: float = Field(..., ge=-180, le=180)
    radius_m: Optional[int] = Field(default=None, gt=0, le=50000)
    description: Optional[str] = Field(default=None, max_length=2000)
    university_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def _cross_validate(self) -> "ZoneCreate":
        if self.shape_type == "polygon":
            if not self.polygon_coords or len(self.polygon_coords) < 3:
                raise ValueError("Polygon requires at least 3 coordinate pairs")
            if self.radius_m is not None:
                raise ValueError("radius_m must be null for polygon zones")
            for pair in self.polygon_coords:
                if len(pair) != 2:
                    raise ValueError("Each polygon coordinate must be [lat, lng]")
                lat, lng = pair
                if not (-90 <= lat <= 90):
                    raise ValueError(f"Invalid latitude {lat}")
                if not (-180 <= lng <= 180):
                    raise ValueError(f"Invalid longitude {lng}")
        elif self.shape_type == "circle":
            if self.polygon_coords is not None:
                raise ValueError("polygon_coords must be null for circle zones")
            if not self.radius_m or self.radius_m <= 0:
                raise ValueError("radius_m is required for circle zones")
        if self.zone_type == "campus" and self.shape_type != "polygon":
            raise ValueError("Campus zones must be polygon (not circle)")
        return self


# ── Patch schema ──────────────────────────────────────────────────────────────

class ZonePatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    polygon_coords: Optional[list[list[float]]] = None
    center_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    center_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    radius_m: Optional[int] = Field(default=None, gt=0, le=50000)
    status: Optional[Literal["active", "archived"]] = None
    expires_at: Optional[datetime] = None
    university_id: Optional[uuid.UUID] = None

    @field_validator("polygon_coords")
    @classmethod
    def _validate_coords(cls, v):
        if v is None:
            return v
        if len(v) < 3:
            raise ValueError("Polygon requires at least 3 points")
        for pair in v:
            if len(pair) != 2:
                raise ValueError("Each coordinate must be [lat, lng]")
        return v
