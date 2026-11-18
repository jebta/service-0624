import jwt
from fastapi import HTTPException, status

from atguigu.app.schemas import CurrentUser
from atguigu.common.settings import get_settings


def authorized_user(authorization: str | None, *role: str) -> CurrentUser:
    """
    根据访问接口的认证信息：bearer，验证是否是user权限
    并且返回CurrentUser对象
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证失败")

    # 获取jwt令牌
    access_token = authorization.split(" ")[1]

    # 令牌解码
    current_user = decode_access_token(access_token)

    if current_user.role not in role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")

    return current_user


# 检验用户权限，并且或的当前user对象
def decode_access_token(access_token):
    """
    根据令牌解码
    """
    pyload = jwt.decode(access_token, key=get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm])
    return CurrentUser.model_validate(pyload)


def encode_access_token(user_id: str) -> str:
    """
    编码
    """
    current_user = CurrentUser(user_id=user_id)
    access_token = jwt.encode(current_user.model_dump(), key=get_settings().jwt_secret,
                              algorithm=get_settings().jwt_algorithm)

    return access_token
