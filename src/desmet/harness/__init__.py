"""
Evaluation Harness

Core evaluation engine: adapter interface, runner, metrics, and story management.

The harness.base module is a re-export shim; the canonical locations are:
  models.py, trace.py, context.py, results.py, adapter.py
"""

from .adapter import BasePlatformAdapter, VisualPlatformAdapter
from .context import StageContext
from .loader import StoryLoadError, load_all_stories, load_story
from .metrics import (
    DimensionScore,
    EvaluationDimension,
    EvaluationMetrics,
    MetricsCollector,
    SetupMetrics,
    StageMetrics,
    StoryMetrics,
)
from .models import PlatformCategory, PlatformInfo, PlatformRuntime
from .results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    StageResult,
    TestResult,
    UMLDiagram,
)
from .runner import EvaluationRunner, RunnerConfig
from .story import (
    SCORING_DIMENSIONS,
    SCORING_RUBRIC,
    AcceptanceCriterion,
    DifficultyLevel,
    StoryResult,
    StoryScore,
    StoryStatus,
    UserStory,
)
from .trace import AgentMessage, AgentTrace, ToolCall

__all__ = [
    "AgentMessage",
    "AgentTrace",
    "AcceptanceCriterion",
    "BasePlatformAdapter",
    "CodeResult",
    "DeployResult",
    "DifficultyLevel",
    "DimensionScore",
    "EvaluationDimension",
    "EvaluationMetrics",
    "EvaluationRunner",
    "MetricsCollector",
    "PlatformCategory",
    "PlatformInfo",
    "PlatformRuntime",
    "RequirementsResult",
    "RunnerConfig",
    "SCORING_DIMENSIONS",
    "SCORING_RUBRIC",
    "SetupMetrics",
    "StageContext",
    "StageMetrics",
    "StageResult",
    "StoryLoadError",
    "StoryMetrics",
    "StoryResult",
    "StoryScore",
    "StoryStatus",
    "TestResult",
    "ToolCall",
    "UMLDiagram",
    "UserStory",
    "VisualPlatformAdapter",
    "load_all_stories",
    "load_story",
]
