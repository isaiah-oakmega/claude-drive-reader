"""C2：Access Token Provider 的 refresh 時機、invalidate、A5，以及 current_account。"""

import pytest

from local_authorization.app import AccessTokenProvider, AuthExpired, BrokerUnreachable, NotAuthorized
from local_authorization.domain.errors import AuthExpired as DomainAuthExpired

from auth_fakes import Clock, FakeAccount, FakeBroker, FakeStore, credential, issued, raises


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def broker() -> FakeBroker:
    return FakeBroker()


def provider_with(store: FakeStore, broker: FakeBroker, clock: Clock, account: FakeAccount | None = None) -> AccessTokenProvider:
    return AccessTokenProvider(store=store, broker=broker, account=account or FakeAccount(), clock=clock)


def test_exceptions_are_reexported_from_app() -> None:
    # 其他 context 只能 import app/（規則 1），所以 app 必須重新匯出同一個例外類別
    assert AuthExpired is DomainAuthExpired


def test_without_credential_raises_not_authorized_and_never_calls_broker(broker: FakeBroker, clock: Clock) -> None:
    provider = provider_with(FakeStore(), broker, clock)

    with pytest.raises(NotAuthorized):
        provider.get_access_token()
    assert broker.refreshes == []


def test_token_is_cached_until_sixty_seconds_before_expiry(broker: FakeBroker, clock: Clock) -> None:
    provider = provider_with(FakeStore(credential()), broker, clock)

    first = provider.get_access_token()
    clock.now += 3600 - 61
    assert provider.get_access_token() == first
    assert broker.refreshes == ["1//R"]

    clock.now += 1
    assert provider.get_access_token() != first
    assert broker.refreshes == ["1//R", "1//R"]


def test_invalidate_forces_refresh_on_next_call(broker: FakeBroker, clock: Clock) -> None:
    provider = provider_with(FakeStore(credential()), broker, clock)
    provider.get_access_token()

    provider.invalidate()
    provider.get_access_token()

    assert len(broker.refreshes) == 2


def test_invalid_grant_deletes_credential(broker: FakeBroker, clock: Clock) -> None:
    store = FakeStore(credential())

    broker.refresh_answer = raises(AuthExpired())
    provider = provider_with(store, broker, clock)

    with pytest.raises(AuthExpired):
        provider.get_access_token()
    assert store.credential is None
    with pytest.raises(NotAuthorized):
        provider.get_access_token()


def test_broker_unreachable_keeps_credential(broker: FakeBroker, clock: Clock) -> None:
    store = FakeStore(credential())

    broker.refresh_answer = raises(BrokerUnreachable("https://broker.example"))

    with pytest.raises(BrokerUnreachable):
        provider_with(store, broker, clock).get_access_token()
    assert store.credential == credential()


def test_new_refresh_token_from_google_overwrites_credential(broker: FakeBroker, clock: Clock) -> None:
    store = FakeStore(credential("1//OLD"))
    broker.refresh_answer = lambda: issued(refresh="1//ROTATED")

    provider_with(store, broker, clock).get_access_token()

    assert store.credential.refresh_token == "1//ROTATED"
    assert store.credential.scope == credential().scope


def test_refresh_without_new_refresh_token_does_not_write_file(broker: FakeBroker, clock: Clock) -> None:
    store = FakeStore(credential())

    provider_with(store, broker, clock).get_access_token()

    assert store.saves == []


def test_adopted_tokens_are_used_without_refresh(broker: FakeBroker, clock: Clock) -> None:
    # 授權完成時換 code 已經拿到 access token，不需要馬上再 refresh 一次
    provider = provider_with(FakeStore(credential()), broker, clock)

    provider.adopt(issued(access="ya29.FROM-CODE", refresh="1//R"))

    assert provider.get_access_token() == "ya29.FROM-CODE"
    assert broker.refreshes == []


def test_forget_drops_cached_token(broker: FakeBroker, clock: Clock) -> None:
    store = FakeStore(credential())
    provider = provider_with(store, broker, clock)
    provider.get_access_token()

    store.delete()
    provider.forget()

    with pytest.raises(NotAuthorized):
        provider.get_access_token()


# ---------- current_account ----------


def test_current_account_is_looked_up_once_and_cached(broker: FakeBroker, clock: Clock) -> None:
    account = FakeAccount("someone@example.com")
    provider = provider_with(FakeStore(credential()), broker, clock, account)

    assert provider.current_account() == "someone@example.com"
    assert provider.current_account() == "someone@example.com"
    assert len(account.lookups) == 1


def test_current_account_is_none_when_not_authorized(broker: FakeBroker, clock: Clock) -> None:
    account = FakeAccount()

    assert provider_with(FakeStore(), broker, clock, account).current_account() is None
    assert account.lookups == []


def test_current_account_is_none_when_token_unavailable(broker: FakeBroker, clock: Clock) -> None:
    broker.refresh_answer = raises(BrokerUnreachable("https://broker.example"))

    assert provider_with(FakeStore(credential()), broker, clock).current_account() is None


def test_rejected_credential_is_remembered_until_new_authorization(broker: FakeBroker, clock: Clock) -> None:
    # auth_status 要能說明「原本的授權已失效」，不是只顯示尚未授權
    broker.refresh_answer = raises(AuthExpired())
    provider = provider_with(FakeStore(credential()), broker, clock)
    assert provider.credential_rejected is False

    assert provider.current_account() is None
    assert provider.credential_rejected is True

    provider.adopt(issued(refresh="1//R2"))
    assert provider.credential_rejected is False


def test_logout_clears_rejected_credential_notice(broker: FakeBroker, clock: Clock) -> None:
    broker.refresh_answer = raises(AuthExpired())
    provider = provider_with(FakeStore(credential()), broker, clock)
    with pytest.raises(AuthExpired):
        provider.get_access_token()

    provider.forget()

    assert provider.credential_rejected is False


def test_unreachable_broker_is_not_a_rejected_credential(broker: FakeBroker, clock: Clock) -> None:
    broker.refresh_answer = raises(BrokerUnreachable("https://broker.example"))
    provider = provider_with(FakeStore(credential()), broker, clock)

    assert provider.current_account() is None
    assert provider.credential_rejected is False


def test_new_authorization_or_logout_clears_cached_account(broker: FakeBroker, clock: Clock) -> None:
    account = FakeAccount("first@example.com")
    provider = provider_with(FakeStore(credential()), broker, clock, account)
    provider.current_account()

    account.address = "second@example.com"
    provider.adopt(issued(refresh="1//R2"))
    assert provider.current_account() == "second@example.com"

    account.address = "third@example.com"
    provider.forget()
    assert provider.current_account() == "third@example.com"
