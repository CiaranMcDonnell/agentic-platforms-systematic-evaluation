"""
Evaluation Harness

Core evaluation engine: adapter interface, runner, metrics, and story management.
"""

from .base import (
    BasePlatformAdapter,
    VisualPlatformAdapter,
    EvaluationContext,
    ExecutionResult,
    PlatformInfo,
    PlatformCategory,
    PlatformRuntime,
    AgentTrace,
    AgentMessage,
    ToolCall,
)
from .runner import EvaluationRunner, RunnerConfig
from .metrics import (
    MetricsCollector,
    EvaluationMetrics,
    DimensionScore,
    EvaluationDimension,
    StoryMetrics,
    SetupMetrics,
)
from .story import (
    UserStory,
    StoryResult,
    StoryScore,
    StoryStatus,
    DifficultyLevel,
    AcceptanceCriterion,
    SCORING_DIMENSIONS,
    SCORING_RUBRIC,
)
from .loader import load_story, load_all_stories, StoryLoadError

__all__ = [
    "BasePlatformAdapter",
    "VisualPlatformAdapter",
    "EvaluationContext",
    "ExecutionResult",
    "PlatformInfo",
    "PlatformCategory",
    "PlatformRuntime",
    "AgentTrace",
    "AgentMessage",
    "ToolCall",
    "EvaluationRunner",
    "RunnerConfig",
    "MetricsCollector",
    "EvaluationMetrics",
    "DimensionScore",
    "EvaluationDimension",
    "StoryMetrics",
    "SetupMetrics",
    "UserStory",
    "StoryResult",
    "StoryScore",
    "StoryStatus",
    "DifficultyLevel",
    "AcceptanceCriterion",
    "SCORING_DIMENSIONS",
    "SCORING_RUBRIC",
    "load_story",
    "load_all_stories",
    "StoryLoadError",
]
