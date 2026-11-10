"""A1、A2：Authorization Attempt 的生命週期。時間以注入的數字表示，不依賴真實時鐘。"""

import base64
import hashlib

import pytest

from local_authorization.domain.attempt import (
    AttemptResult,
    AuthorizationAttempt,
    CodeReceived,
    Pkce,
)
from local_authorization.domain.limits import ATTEMPT_TTL_SECONDS

PORT = 53682
NOW = 1000.0


def start(now: float = NOW) -> AuthorizationAttempt:
    return AuthorizationAttempt.start(port=PORT, now=now)


# ---------- PKCE ----------


def test_pkce_challenge_is_s256_of_verifier() -> None:
    pkce = Pkce.generate()

    digest = hashlib.sha256(pkce.verifier.encode("ascii")).digest()
    assert pkce.challenge == base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    # RFC 7636 §4.1：verifier 長度 43–128；S256 的 challenge 固定 43 字元
    assert 43 <= len(pkce.verifier) <= 128
    assert len(pkce.challenge) == 43


def test_each_attempt_gets_fresh_pkce_and_state() -> None:
    first, second = start(), start()

    assert first.pkce.verifier != second.pkce.verifier
    assert first.state != second.state


# ---------- 有效的 callback 結束 Attempt ----------


def test_valid_callback_with_code_hands_over_the_code() -> None:
    attempt = start()

    verdict = attempt.receive_callback({"state": attempt.state, "code": "4/CODE"}, now=NOW + 1)

    assert verdict == CodeReceived(code="4/CODE")
    assert attempt.is_pending(NOW + 1) is False


def test_code_exchange_outcome_is_recorded() -> None:
    succeeded, failed = start(), start()
    succeeded.receive_callback({"state": succeeded.state, "code": "4/A"}, now=NOW)
    failed.receive_callback({"state": failed.state, "code": "4/B"}, now=NOW)

    succeeded.finish_exchange(ok=True)
    failed.finish_exchange(ok=False)

    assert succeeded.result is AttemptResult.SUCCEEDED
    assert failed.result is AttemptResult.FAILED


def test_user_denial_ends_attempt_as_denied() -> None:
    attempt = start()

    verdict = attempt.receive_callback({"state": attempt.state, "error": "access_denied"}, now=NOW)

    assert verdict is AttemptResult.DENIED
    assert attempt.result is AttemptResult.DENIED


def test_other_google_error_ends_attempt_as_failed() -> None:
    attempt = start()

    verdict = attempt.receive_callback({"state": attempt.state, "error": "server_error"}, now=NOW)

    assert verdict is AttemptResult.FAILED
    assert attempt.result is AttemptResult.FAILED


# ---------- A2：不合格的請求回 400，但不結束 Attempt ----------


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"code": "4/CODE"},
        {"state": "53682.wrong-nonce-wrong-nonce", "code": "4/CODE"},
        {"state": "53682.wrong-nonce-wrong-nonce", "error": "access_denied"},
        {"state": "５３６８２.全形與非 ASCII 字元", "code": "4/CODE"},
    ],
    ids=["empty", "no-state", "wrong-state", "wrong-state-denial", "non-ascii"],
)
def test_request_without_matching_state_is_rejected_and_attempt_keeps_waiting(params: dict) -> None:
    attempt = start()

    assert attempt.receive_callback(params, now=NOW + 1) is None
    assert attempt.is_pending(NOW + 1)

    # 雜訊請求之後，真正的 callback 仍然能完成授權
    verdict = attempt.receive_callback({"state": attempt.state, "code": "4/REAL"}, now=NOW + 2)
    assert verdict == CodeReceived(code="4/REAL")


def test_valid_state_without_code_or_error_is_rejected_and_attempt_keeps_waiting() -> None:
    attempt = start()

    assert attempt.receive_callback({"state": attempt.state}, now=NOW) is None
    assert attempt.is_pending(NOW)


# ---------- A2：一次性 ----------


def test_attempt_is_single_use() -> None:
    attempt = start()
    attempt.receive_callback({"state": attempt.state, "code": "4/FIRST"}, now=NOW)
    attempt.finish_exchange(ok=True)

    assert attempt.receive_callback({"state": attempt.state, "code": "4/SECOND"}, now=NOW + 1) is None
    assert attempt.result is AttemptResult.SUCCEEDED


# ---------- A2：5 分鐘後過期 ----------


def test_attempt_expires_after_ttl() -> None:
    attempt = start()

    assert ATTEMPT_TTL_SECONDS == 300
    assert attempt.is_pending(NOW + ATTEMPT_TTL_SECONDS - 0.1)
    assert attempt.is_pending(NOW + ATTEMPT_TTL_SECONDS) is False


def test_callback_after_expiry_is_rejected_and_marks_timeout() -> None:
    attempt = start()

    assert attempt.receive_callback({"state": attempt.state, "code": "4/LATE"}, now=NOW + ATTEMPT_TTL_SECONDS) is None
    assert attempt.result is AttemptResult.TIMED_OUT


def test_expire_marks_pending_attempt_as_timed_out_but_not_a_finished_one() -> None:
    pending, denied = start(), start()
    denied.receive_callback({"state": denied.state, "error": "access_denied"}, now=NOW)

    pending.expire()
    denied.expire()

    assert pending.result is AttemptResult.TIMED_OUT
    assert denied.result is AttemptResult.DENIED


def test_seconds_left_counts_down_to_zero() -> None:
    attempt = start()

    assert attempt.seconds_left(NOW + 100) == ATTEMPT_TTL_SECONDS - 100
    assert attempt.seconds_left(NOW + ATTEMPT_TTL_SECONDS + 5) == 0
