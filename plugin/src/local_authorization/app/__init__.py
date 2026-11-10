"""Local Authorization 對外公開的 API。其他 context 與 mcp_server 只從這裡 import（依賴規則 1）。"""

from local_authorization.app.authorization_service import (
    AuthorizationService,
    AuthorizationStarted,
    AuthStatus,
    LogoutReport,
)
from local_authorization.app.token_provider import AccessTokenProvider
from local_authorization.domain.attempt import AttemptResult
from local_authorization.domain.credential import RevokeOutcome
from local_authorization.domain.errors import (
    AuthExpired,
    AuthorizationError,
    BrokerUnreachable,
    CallbackPortUnavailable,
    NotAuthorized,
)

__all__ = [
    "AccessTokenProvider",
    "AttemptResult",
    "AuthExpired",
    "AuthStatus",
    "AuthorizationError",
    "AuthorizationService",
    "AuthorizationStarted",
    "BrokerUnreachable",
    "CallbackPortUnavailable",
    "LogoutReport",
    "NotAuthorized",
    "RevokeOutcome",
]
