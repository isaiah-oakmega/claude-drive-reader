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
from local_authorization.domain.limits import MAX_CALLBACK_PORT, MIN_CALLBACK_PORT

__all__ = [
    "AccessTokenProvider",
    "AttemptResult",
    "AuthExpired",
    "AuthorizationError",
    "AuthorizationService",
    "AuthorizationStarted",
    "AuthStatus",
    "BrokerUnreachable",
    "CallbackPortUnavailable",
    "LogoutReport",
    "MAX_CALLBACK_PORT",
    "MIN_CALLBACK_PORT",
    "NotAuthorized",
    "RevokeOutcome",
]
