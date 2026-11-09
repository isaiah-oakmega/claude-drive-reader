"""/token 的請求與回應形狀（B3、C1）。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Grant(BaseModel):
    # extra="forbid"：本機只能送規定的欄位。scope、redirect_uri、client_id 都由 Broker 決定（B4、B5），
    # 多送任何欄位都視為形狀不合，回 422。
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthorizationCodeGrant(_Grant):
    grant_type: Literal["authorization_code"]
    code: str = Field(min_length=1, max_length=2048)
    # verifier 的字元集與長度依 RFC 7636 §4.1
    code_verifier: str = Field(pattern=r"^[A-Za-z0-9\-._~]{43,128}$")


class RefreshTokenGrant(_Grant):
    grant_type: Literal["refresh_token"]
    refresh_token: str = Field(min_length=1, max_length=2048)


# 以 grant_type 區分兩種形狀：驗證錯誤會直接指出是哪一種不合，也不會誤用另一種的規則。
TokenGrant = Annotated[AuthorizationCodeGrant | RefreshTokenGrant, Field(discriminator="grant_type")]


class IssuedToken(BaseModel):
    """回給本機的欄位（C1 的 200）。只挑合約列出的欄位，Google 多給的欄位不轉交。"""

    access_token: str
    expires_in: int
    scope: str
    token_type: str
    refresh_token: str | None = None
