"""Backend models package.

Note: keep backend models as the source-of-truth schemas for OpenAPI + frontend types.
"""

from .project import (
    CreateProjectRequest,
    OutlineItem,
    Project,
    ProjectSummary,
    Resource,
    ResourceType,
    UpdateProjectRequest,
    Visual,
    WebinarType,
    MAX_FILE_SIZE,
    ALLOWED_MIME_TYPES,
    ALLOWED_EXTENSIONS,
)
from .style_config import (
    StyleConfig,
    StyleConfigEnvelope,
    STYLE_CONFIG_VERSION,
    style_config_json_schema,
    # Enums
    ContentMode,  # Spec 009
    TargetAudience,
    ReaderRole,
    PrimaryGoal,
    ReaderTakeawayStyle,
    Tone,
    Formality,
    BrandVoice,
    Perspective,
    ReadingLevel,
    BookFormat,
    ChapterLengthTarget,
    FaithfulnessLevel,
    AllowedExtrapolation,
    SourcePolicy,
    CitationStyle,
    VisualDensity,
    VisualType,
    VisualSourcePolicy,
    CaptionStyle,
    DiagramStyle,
    ResolveRepetitions,
    HandleQAndA,
    IncludeSpeakerQuotes,
    HeadingStyle,
    CalloutBlocks,
    TablePreference,
)
from .style_config_migrations import migrate_style_config_envelope
from .visuals import (
    VisualAsset,
    VisualAssetOrigin,
    VisualAssignment,
    VisualAssignmentStatus,
    VisualOpportunity,
    VisualPlan,
    VisualPlacement,
)
from .draft_plan import (
    DraftPlan,
    ChapterPlan,
    TranscriptSegment,
    TranscriptRelevance,
    GenerationMetadata,
    DRAFT_PLAN_VERSION,
    draft_plan_json_schema,
)
from .api_responses import (
    JobStatus,
    GenerationProgress,
    TokenUsage,
    GenerationStats,
    ErrorDetail,
    # Request models
    DraftGenerateRequest,
    DraftRegenerateRequest,
    # Data models (inner payload)
    DraftGenerateData,
    DraftStatusData,
    DraftCancelData,
    DraftRegenerateData,
    # Response envelopes
    DraftGenerateResponse,
    DraftStatusResponse,
    DraftCancelResponse,
    DraftRegenerateResponse,
    # Export API models (Spec 006)
    PreviewData,
    PreviewResponse,
    ExportStartData,
    ExportStartResponse,
    ExportStatusData,
    ExportStatusResponse,
    ExportCancelData,
    ExportCancelResponse,
)
from .generation_job import GenerationJob
from .export_job import (
    ExportJob,
    ExportJobStatus,
    ExportFormat,
)
from .qa_report import (
    QAReport,
    QAIssue,
    RubricScores,
    IssueCounts,
    IssueSeverity,
    IssueType,
    MAX_ISSUES,
    QA_REPORT_VERSION,
    qa_report_json_schema,
)
from .qa_job import (
    QAJob,
    QAJobStatus,
)
# Evidence Map models (Spec 009)
from .evidence_map import (
    EvidenceMap,
    ChapterEvidence,
    EvidenceEntry,
    SupportQuote,
    MustIncludeItem,
    TranscriptRange,
    GlobalContext,
    SpeakerInfo,
    ClaimType,
    MustIncludePriority,
)
# Rewrite Plan models (Spec 009)
from .rewrite_plan import (
    RewritePlan,
    RewriteSection,
    RewriteResult,
    SectionDiff,
    IssueReference,
    IssueTypeEnum,
)

__all__ = [
    # Project models
    "CreateProjectRequest",
    "OutlineItem",
    "Project",
    "ProjectSummary",
    "Resource",
    "ResourceType",
    "UpdateProjectRequest",
    "Visual",
    "WebinarType",
    "MAX_FILE_SIZE",
    "ALLOWED_MIME_TYPES",
    "ALLOWED_EXTENSIONS",
    # Style config
    "StyleConfig",
    "StyleConfigEnvelope",
    "STYLE_CONFIG_VERSION",
    "style_config_json_schema",
    "migrate_style_config_envelope",
    # Style config enums
    "TargetAudience",
    "ReaderRole",
    "PrimaryGoal",
    "ReaderTakeawayStyle",
    "Tone",
    "Formality",
    "BrandVoice",
    "Perspective",
    "ReadingLevel",
    "BookFormat",
    "ChapterLengthTarget",
    "FaithfulnessLevel",
    "AllowedExtrapolation",
    "SourcePolicy",
    "CitationStyle",
    "VisualDensity",
    "VisualType",
    "VisualSourcePolicy",
    "CaptionStyle",
    "DiagramStyle",
    "ResolveRepetitions",
    "HandleQAndA",
    "IncludeSpeakerQuotes",
    "HeadingStyle",
    "CalloutBlocks",
    "TablePreference",
    # Visuals
    "VisualAsset",
    "VisualAssetOrigin",
    "VisualAssignment",
    "VisualAssignmentStatus",
    "VisualOpportunity",
    "VisualPlan",
    "VisualPlacement",
    # Draft plan
    "DraftPlan",
    "ChapterPlan",
    "TranscriptSegment",
    "TranscriptRelevance",
    "GenerationMetadata",
    "DRAFT_PLAN_VERSION",
    "draft_plan_json_schema",
    # API responses
    "JobStatus",
    "GenerationProgress",
    "TokenUsage",
    "GenerationStats",
    "ErrorDetail",
    # Request models
    "DraftGenerateRequest",
    "DraftRegenerateRequest",
    # Data models (inner payload)
    "DraftGenerateData",
    "DraftStatusData",
    "DraftCancelData",
    "DraftRegenerateData",
    # Response envelopes
    "DraftGenerateResponse",
    "DraftStatusResponse",
    "DraftCancelResponse",
    "DraftRegenerateResponse",
    # Generation job
    "GenerationJob",
    # Export job
    "ExportJob",
    "ExportJobStatus",
    "ExportFormat",
    # Export API models (Spec 006)
    "PreviewData",
    "PreviewResponse",
    "ExportStartData",
    "ExportStartResponse",
    "ExportStatusData",
    "ExportStatusResponse",
    "ExportCancelData",
    "ExportCancelResponse",
    # QA report models
    "QAReport",
    "QAIssue",
    "RubricScores",
    "IssueCounts",
    "IssueSeverity",
    "IssueType",
    "MAX_ISSUES",
    "QA_REPORT_VERSION",
    "qa_report_json_schema",
    # QA job models
    "QAJob",
    "QAJobStatus",
    # Evidence Map models (Spec 009)
    "EvidenceMap",
    "ChapterEvidence",
    "EvidenceEntry",
    "SupportQuote",
    "MustIncludeItem",
    "TranscriptRange",
    "GlobalContext",
    "SpeakerInfo",
    "ClaimType",
    "MustIncludePriority",
    # Rewrite Plan models (Spec 009)
    "RewritePlan",
    "RewriteSection",
    "RewriteResult",
    "SectionDiff",
    "IssueReference",
    "IssueTypeEnum",
    # Content Mode (Spec 009)
    "ContentMode",
]
