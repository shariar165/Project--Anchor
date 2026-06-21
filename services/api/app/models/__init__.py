from app.models.base import Base, TimestampMixin
from app.models.tenant import Tenant, TenantEmailDomain
from app.models.platform_config import PlatformConfig
from app.models.user import User, Role, AccountStatus
from app.models.session import Session
from app.models.mfa import MFAMethod, MFARecoveryCode, MFAType
from app.models.audit import AuditLog
from app.models.anonymous import AnonymousIdentityMapping
from app.models.deanonymization import DeanonymizationRequest
from app.models.dms import DMSRecord
from app.models.e2ee import UserE2EEKey
from app.models.incident import (
    Incident, IncidentUpdate,
    INCIDENT_SEVERITIES, INCIDENT_STATUSES, OPEN_STATUSES,
)
from app.models.alert import (
    AlertPhase1Record, Zone, AlertEvent, AlertNotification,
    AlertResponse, AlertEvidence, AlertBan, AlertAdminAction,
    UserFCMToken, UserLocationSnapshot,
    GPSStatus, AlertState, RecipientType, NotifChannel, NotifStatus,
    ResponseType, AlertActionType, MediaType, FCMPlatform, ZoneType, ZoneStatus,
)
from app.models.application import (
    ApplicationTemplate, Application, ApplicationAttachment,
    ApplicationReview, StudentCampusSettings, ApplicationState,
)
from app.models.feed import (
    VerificationFeedPost, VerificationFeedPostVersion,
    VerificationFeedAttachment, VerificationFeedSignal,
    VerificationFeedFlag, VerificationFeedModeration,
    UserFeedTrust,
    PostScope, PostCategory, PostState, AIPrescreenVerdict,
    SignalType, FlagReason, ModerationAction, TrustTier,
)
from app.models.filing import (
    FilingTemplate, Filing, FilingAttachment, FilingReview,
    SubjectResponse, ClassroomReport,
    FilingCategory, FilingAnonymityMode, FilingState, ClassroomIssueType,
)
from app.models.notice import Notice, NoticeScope, NoticeStatus
from app.models.lawyer import Lawyer
from app.models.legal_right import LegalRight
from app.models.routine import AcademicRoutine, RoutineStatus
from app.models.dept_rating import DepartmentRating
from app.models.tenant_geofence import TenantGeofence
from app.models.timetable import (
    TimetableTerm, TimetableBatch, TimetableSection, TimetableLabGroup,
    TimetableRoom, TimetableCourse, TimetableFacultyProfile,
    TimetableStudentEnrollment, TimetableCourseOffering,
    TimetableTeacherEligibility, TimetableScheduleConfig,
    TimetableConstraint, TimetableSolveJob, TimetableEntry,
)

__all__ = [
    "Base", "TimestampMixin",
    "Tenant", "TenantEmailDomain",
    "PlatformConfig",
    "User", "Role", "AccountStatus",
    "Session",
    "MFAMethod", "MFARecoveryCode", "MFAType",
    "AuditLog",
    "AnonymousIdentityMapping",
    "DeanonymizationRequest",
    "DMSRecord",
    "UserE2EEKey",
    "Incident", "IncidentUpdate",
    "INCIDENT_SEVERITIES", "INCIDENT_STATUSES", "OPEN_STATUSES",
    # Alert system
    "AlertPhase1Record", "Zone", "AlertEvent", "AlertNotification",
    "AlertResponse", "AlertEvidence", "AlertBan", "AlertAdminAction",
    "UserFCMToken", "UserLocationSnapshot",
    "GPSStatus", "AlertState", "RecipientType", "NotifChannel", "NotifStatus",
    "ResponseType", "AlertActionType", "MediaType", "FCMPlatform", "ZoneType", "ZoneStatus",
    # Application system
    "ApplicationTemplate", "Application", "ApplicationAttachment",
    "ApplicationReview", "StudentCampusSettings", "ApplicationState",
    # Verification Feed
    "VerificationFeedPost", "VerificationFeedPostVersion",
    "VerificationFeedAttachment", "VerificationFeedSignal",
    "VerificationFeedFlag", "VerificationFeedModeration",
    "UserFeedTrust",
    "PostScope", "PostCategory", "PostState", "AIPrescreenVerdict",
    "SignalType", "FlagReason", "ModerationAction", "TrustTier",
    # Filing system
    "FilingTemplate", "Filing", "FilingAttachment", "FilingReview",
    "SubjectResponse", "ClassroomReport",
    "FilingCategory", "FilingAnonymityMode", "FilingState", "ClassroomIssueType",
    # Notices
    "Notice", "NoticeScope", "NoticeStatus",
    # Lawyers
    "Lawyer",
    # Legal rights (Know your rights)
    "LegalRight",
    # Academic Routines
    "AcademicRoutine", "RoutineStatus",
    # Department Ratings
    "DepartmentRating",
    # Tenant Geofence
    "TenantGeofence",
    # Timetable Generator
    "TimetableTerm", "TimetableBatch", "TimetableSection", "TimetableLabGroup",
    "TimetableRoom", "TimetableCourse", "TimetableFacultyProfile",
    "TimetableStudentEnrollment", "TimetableCourseOffering",
    "TimetableTeacherEligibility", "TimetableScheduleConfig",
    "TimetableConstraint", "TimetableSolveJob", "TimetableEntry",
]
