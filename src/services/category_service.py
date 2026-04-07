from sqlalchemy import select, or_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.category import Category
from src.database.models.deleted_category import DeletedCategory


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_categories(self, user_id: int, type_: str) -> list[Category]:
        deleted_default_exists = exists().where(
            DeletedCategory.user_id == user_id,
            DeletedCategory.category_id == Category.id,
        )
        stmt = (
            select(Category)
            .where(
                Category.type == type_,
                or_(Category.is_default.is_(True), Category.user_id == user_id),
                # Hide default categories deleted by this user
                ~deleted_default_exists,
            )
            .order_by(Category.is_default.desc(), Category.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, name: str, type_: str, user_id: int, emoji: str | None = None) -> Category:
        category = Category(name=name, type=type_, user_id=user_id, is_default=False, emoji=emoji)
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def delete(self, category_id: int, user_id: int) -> bool:
        stmt = select(Category).where(Category.id == category_id)
        result = await self.session.execute(stmt)
        category = result.scalar_one_or_none()
        if category is None:
            return False

        # User-owned category: delete physically
        if category.is_default is False:
            if category.user_id != user_id:
                return False
            await self.session.delete(category)
            await self.session.commit()
            return True

        # Default category: mark as deleted for this user
        stmt = select(DeletedCategory).where(
            DeletedCategory.user_id == user_id,
            DeletedCategory.category_id == category_id,
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing is None:
            self.session.add(DeletedCategory(user_id=user_id, category_id=category_id))
            await self.session.commit()
        return True

    async def get_by_id(self, category_id: int) -> Category | None:
        stmt = select(Category).where(Category.id == category_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
