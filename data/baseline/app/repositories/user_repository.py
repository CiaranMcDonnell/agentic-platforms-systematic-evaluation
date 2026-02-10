"""User repository for database operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Async repository for User CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: str) -> User | None:
        """Fetch a user by ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by email address."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        """Persist a new user."""
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        """Update an existing user."""
        await self.session.commit()
        await self.session.refresh(user)
        return user
