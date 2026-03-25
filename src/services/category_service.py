from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.category import Category


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_categories(self, user_id: int, type_: str) -> list[Category]:
        stmt = (
            select(Category)
            .where(
                Category.type == type_,
                or_(Category.is_default.is_(True), Category.user_id == user_id),
            )
            .order_by(Category.is_default.desc(), Category.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, name: str, type_: str, user_id: int) -> Category:
        category = Category(name=name, type=type_, user_id=user_id, is_default=False)
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def delete(self, category_id: int, user_id: int) -> bool:
        stmt = select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id,
            Category.is_default.is_(False),
        )
        result = await self.session.execute(stmt)
        category = result.scalar_one_or_none()
        if category is None:
            return False
        await self.session.delete(category)
        await self.session.commit()
        return True

    async def get_by_id(self, category_id: int) -> Category | None:
        stmt = select(Category).where(Category.id == category_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
