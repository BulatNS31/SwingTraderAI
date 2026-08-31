from typing import Annotated, Any, Callable, Coroutine
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.services.analysis_service import AnalysisService
from swingtraderai.api.services.indicator_service import IndicatorService
from swingtraderai.api.services.setup_service import SetupService
from swingtraderai.api.services.ticker_service import TickerService
from swingtraderai.core.security import decode_token
from swingtraderai.db.models.user import User, UserRole
from swingtraderai.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_ticker_service(db: AsyncSession = Depends(get_db)) -> TickerService:
	return TickerService(db)


async def get_indicator_service(
	ticker_service: TickerService = Depends(get_ticker_service),
) -> IndicatorService:
	return IndicatorService(ticker_service=ticker_service)


async def get_setup_service(
	ticker_service: TickerService = Depends(get_ticker_service),
) -> SetupService:
	return SetupService(ticker_service=ticker_service)


async def get_analysis_service(
	indicator_service: IndicatorService = Depends(get_indicator_service),
	setup_service: SetupService = Depends(get_setup_service),
) -> AnalysisService:
	return AnalysisService(indicator_service, setup_service)


async def get_current_user(
	token: Annotated[str, Depends(oauth2_scheme)],
	db: Annotated[AsyncSession, Depends(get_db)],
	request: Request,
) -> User:
	credentials_exception = HTTPException(
		status_code=status.HTTP_401_UNAUTHORIZED,
		detail="Could not validate credentials",
		headers={"WWW-Authenticate": "Bearer"},
	)

	try:
		payload = decode_token(token)
		user_id_str = payload.sub
		token_type = getattr(payload, "type", None)

		if user_id_str is None or token_type != "access":
			raise credentials_exception

		user_id = UUID(user_id_str)

	except (JWTError, ValueError, AttributeError) as exc:
		raise credentials_exception from exc

	user = await db.get(User, user_id)
	if user is None:
		raise credentials_exception

	if not user.is_active:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
		)

	request.state.user = user

	return user


def require_role(
	required_role: UserRole,
) -> Callable[[User], Coroutine[Any, Any, User]]:
	"""
	Фабрика зависимостей: требует определённую роль или выше
	"""

	async def dependency(
		current_user: Annotated[User, Depends(get_current_user)],
	) -> User:
		if current_user.role != required_role:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail=f"Required role: {required_role.value}",
			)
		return current_user

	return dependency


get_current_active_user = get_current_user

get_current_admin = require_role(UserRole.ADMIN)
get_current_tester_or_higher = require_role(UserRole.TESTER)
get_current_support_or_higher = require_role(UserRole.SUPPORT)


ROLE_HIERARCHY = {
	UserRole.ADMIN: 4,
	UserRole.SUPPORT: 3,
	UserRole.TESTER: 2,
	UserRole.USER: 1,
}


def require_role_or_higher(
	min_role: UserRole,
) -> Callable[[User], Coroutine[Any, Any, User]]:
	min_level = ROLE_HIERARCHY[min_role]

	async def dep(current_user: Annotated[User, Depends(get_current_user)]) -> User:
		user_level = ROLE_HIERARCHY.get(current_user.role, 0)
		if user_level < min_level:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail=f"Required minimum role: {min_role.value} or higher",
			)
		return current_user

	return dep
