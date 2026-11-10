"""authorize、auth_status、logout 的 use case（A1、A2、A6、Q1）。listener 與瀏覽器都是假的，callback 由測試直接觸發。"""

from datetime import UTC, datetime

import pytest

from local_authorization.app import (
    AccessTokenProvider,
    AttemptResult,
    AuthorizationService,
    BrokerUnreachable,
    CallbackPortUnavailable,
)
from local_authorization.domain.credential import RevokeOutcome
from local_authorization.domain.limits import ATTEMPT_TTL_SECONDS

from auth_fakes import Clock, FakeAccount, FakeBroker, FakeListen, FakeRevoker, FakeStore, credential, issued, raises

FIXED_TIME = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)


class World:
    def __init__(self, initial=None, callback_port: int | None = None, browser_opens: bool = True) -> None:
        self.clock = Clock()
        self.store = FakeStore(initial)
        self.broker = FakeBroker()
        self.account = FakeAccount()
        self.revoker = FakeRevoker()
        self.listen = FakeListen()
        self.opened: list[str] = []
        self.tokens = AccessTokenProvider(store=self.store, broker=self.broker, account=self.account, clock=self.clock)

        def open_browser(url: str) -> bool:
            self.opened.append(url)
            return browser_opens

        self.service = AuthorizationService(
            broker=self.broker,
            store=self.store,
            tokens=self.tokens,
            revoker=self.revoker,
            listen=self.listen,
            open_browser=open_browser,
            callback_port=callback_port,
            clock=self.clock,
            utc_now=lambda: FIXED_TIME,
        )

    @property
    def listener(self):
        return self.listen.listeners[-1]

    def state_in(self, url: str) -> str:
        return url.split("state=")[1].split("&")[0]


@pytest.fixture
def world() -> World:
    return World()


# ---------- authorize ----------


def test_authorize_returns_broker_url_and_opens_browser(world: World) -> None:
    started = world.service.authorize()

    assert started.url.startswith("https://broker.example/authorize?state=53682.")
    assert world.opened == [started.url]
    assert started.browser_opened is True
    assert started.expires_in_seconds == ATTEMPT_TTL_SECONDS
    assert world.listen.requested_ports == [None]
    assert world.listener.timeout_seconds == ATTEMPT_TTL_SECONDS


def test_authorize_reports_when_browser_did_not_open() -> None:
    world = World(browser_opens=False)

    assert world.service.authorize().browser_opened is False


def test_configured_callback_port_is_used() -> None:
    world = World(callback_port=50000)

    started = world.service.authorize()

    assert world.listen.requested_ports == [50000]
    assert "state=50000." in started.url


def test_port_that_cannot_be_bound_is_reported() -> None:
    world = World(callback_port=50000)
    world.listen.error = OSError("address already in use")

    with pytest.raises(CallbackPortUnavailable) as raised:
        world.service.authorize()
    assert raised.value.port == 50000


# ---------- callback：成功 ----------


def test_successful_callback_saves_credential_and_primes_tokens(world: World) -> None:
    started = world.service.authorize()

    result = world.listener.callback(state=world.state_in(started.url), code="4/CODE")

    assert result is AttemptResult.SUCCEEDED
    code, verifier = world.broker.exchanges[0]
    assert code == "4/CODE" and len(verifier) >= 43
    assert world.store.credential.refresh_token == "1//NEW"
    assert world.store.credential.obtained_at == "2026-11-10T12:00:00+00:00"
    # 換 code 拿到的 access token 直接可用，不需要再 refresh
    assert world.tokens.get_access_token() == "ya29.NEW"
    assert world.broker.refreshes == []

    status = world.service.status()
    assert (status.authorized, status.account, status.attempt_in_progress, status.last_result) == (
        True,
        "someone@example.com",
        False,
        AttemptResult.SUCCEEDED,
    )


def test_code_verifier_matches_the_challenge_sent_to_broker(world: World) -> None:
    import base64
    import hashlib

    started = world.service.authorize()
    world.listener.callback(state=world.state_in(started.url), code="4/CODE")

    _, verifier = world.broker.exchanges[0]
    challenge = started.url.split("code_challenge=")[1]
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


# ---------- callback：不算數的請求 ----------


def test_noise_request_does_not_end_attempt(world: World) -> None:
    started = world.service.authorize()

    assert world.listener.callback(state="53682.someone-else-guessing", code="4/X") is None
    assert world.service.status().attempt_in_progress is True

    assert world.listener.callback(state=world.state_in(started.url), code="4/CODE") is AttemptResult.SUCCEEDED


# ---------- callback：拒絕與失敗 ----------


def test_denial_keeps_existing_credential_and_is_reported() -> None:
    world = World(initial=credential("1//EXISTING"))
    started = world.service.authorize()

    result = world.listener.callback(state=world.state_in(started.url), error="access_denied")

    assert result is AttemptResult.DENIED
    assert world.store.credential.refresh_token == "1//EXISTING"
    assert world.broker.exchanges == []
    status = world.service.status()
    assert (status.attempt_in_progress, status.last_result) == (False, AttemptResult.DENIED)


@pytest.mark.parametrize(
    "answer",
    [
        raises(BrokerUnreachable("https://broker.example")),
        lambda: issued(access="ya29.A", refresh=None),
    ],
    ids=["broker-down", "no-refresh-token"],
)
def test_failed_code_exchange_keeps_existing_credential(answer) -> None:
    world = World(initial=credential("1//EXISTING"))
    world.broker.exchange_answer = answer
    started = world.service.authorize()

    result = world.listener.callback(state=world.state_in(started.url), code="4/CODE")

    assert result is AttemptResult.FAILED
    assert world.store.credential.refresh_token == "1//EXISTING"
    assert world.service.status().last_result is AttemptResult.FAILED


# ---------- 逾時 ----------


def test_listener_timeout_is_reported_as_timed_out(world: World) -> None:
    world.service.authorize()

    world.listener.on_timeout()

    status = world.service.status()
    assert (status.attempt_in_progress, status.last_result) == (False, AttemptResult.TIMED_OUT)


def test_status_notices_expiry_even_before_timer_fires(world: World) -> None:
    world.service.authorize()

    world.clock.now += ATTEMPT_TTL_SECONDS

    status = world.service.status()
    assert (status.attempt_in_progress, status.last_result) == (False, AttemptResult.TIMED_OUT)


# ---------- A1：新的 authorize 取代舊的 ----------


def test_new_authorize_closes_and_replaces_previous_attempt(world: World) -> None:
    first = world.service.authorize()
    first_listener = world.listener

    second = world.service.authorize()

    assert first_listener.closed is True
    assert first_listener.handle({"state": world.state_in(first.url), "code": "4/OLD"}) is None
    assert world.listener.callback(state=world.state_in(second.url), code="4/NEW") is AttemptResult.SUCCEEDED
    assert world.broker.exchanges[0][0] == "4/NEW"


def test_previous_result_is_kept_while_new_attempt_is_pending(world: World) -> None:
    started = world.service.authorize()
    world.listener.callback(state=world.state_in(started.url), error="access_denied")

    world.service.authorize()

    status = world.service.status()
    assert (status.attempt_in_progress, status.last_result) == (True, AttemptResult.DENIED)


# ---------- auth_status ----------


def test_status_before_any_attempt(world: World) -> None:
    status = world.service.status()

    assert (status.authorized, status.account, status.attempt_in_progress, status.last_result) == (False, None, False, None)
    assert status.credentials_path == world.store.path
    assert status.permissions_enforced is True


def test_status_with_credential_from_an_earlier_session() -> None:
    world = World(initial=credential())

    status = world.service.status()

    assert (status.authorized, status.account, status.last_result) == (True, "someone@example.com", None)


# ---------- logout（A6） ----------


def test_logout_revokes_then_deletes(world: World) -> None:
    world = World(initial=credential("1//R"))
    world.tokens.get_access_token()

    report = world.service.logout()

    assert world.revoker.revoked == ["1//R"]
    assert world.store.credential is None
    assert (report.had_credential, report.revoke, report.deleted) == (True, RevokeOutcome.REVOKED, True)
    assert world.service.status().authorized is False


def test_logout_deletes_even_when_revoke_fails() -> None:
    world = World(initial=credential("1//R"))
    world.revoker.outcome = RevokeOutcome.FAILED

    report = world.service.logout()

    assert world.store.credential is None
    assert (report.revoke, report.deleted) == (RevokeOutcome.FAILED, True)


def test_logout_without_credential_does_nothing(world: World) -> None:
    report = world.service.logout()

    assert world.revoker.revoked == []
    assert (report.had_credential, report.revoke, report.deleted) == (False, None, False)
