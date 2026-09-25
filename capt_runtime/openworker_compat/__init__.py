"""CAPT-owned adaptations of selected OpenWorker mechanisms.

These modules are adapted from andrewyng/openworker under the MIT License.
CAPT RuntimeService/EventStore authority remains canonical; this package does
not expose OpenWorker's alternate engine/server as a CAPT runtime.
"""

from .attachments import build_user_content, content_to_text, reviewer_text
from .clock import current_time
from .environment import environment_context
from .readonly import is_readonly_command, read_targets
from .toolresult import bound_tool_result
from .url_guard import check_url
from .workspace_trust import WorkspaceTrustStore

__all__ = [
    "WorkspaceTrustStore",
    "bound_tool_result",
    "build_user_content",
    "check_url",
    "content_to_text",
    "current_time",
    "environment_context",
    "is_readonly_command",
    "read_targets",
    "reviewer_text",
]
