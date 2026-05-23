import os
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

os.environ.setdefault("SERVICE_TOKEN", "test-service-token")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db?schema=public")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("RECOMMENDATION_SERVICE_URL", "http://recommendation.test")
os.environ.setdefault("SEARCH_SERVICE_URL", "http://search.test")
os.environ.setdefault("INVENTORY_SERVICE_URL", "http://inventory.test")
os.environ.setdefault("VOICE_SERVICE_URL", "http://voice.test")
os.environ.setdefault("ANOMALY_SERVICE_URL", "http://anomaly.test")

from app.auth.jwt import create_access_token, get_password_hash
from app.core import database as database_module
from app.core.database import get_db_session
from app.models.user import UserRole
import app.routes.orders as orders_module
import main as main_module


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FakeUserTable:
    def __init__(self, fake_db):
        self.fake_db = fake_db

    async def create(self, data):
        return self.fake_db.add_user(**data)

    async def find_first(self, where=None, order=None):
        where = where or {}
        for user in self.fake_db.users.values():
            if self._matches(user, where):
                return user
        return None

    async def find_unique(self, where, include=None):
        if "id" in where:
            return self.fake_db.users.get(where["id"])
        if "email" in where:
            return next((user for user in self.fake_db.users.values() if user.email == where["email"]), None)
        if "phone" in where:
            return next((user for user in self.fake_db.users.values() if user.phone == where["phone"]), None)
        return None

    def _matches(self, user, where):
        if "OR" in where:
            return any(self._matches(user, clause) for clause in where["OR"])

        for field, expected in where.items():
            if field == "OR":
                continue

            actual = getattr(user, field, None)
            if isinstance(expected, dict):
                if "not" in expected and actual == expected["not"]:
                    return False
            elif actual != expected:
                return False
        return True


class FakeRefreshTokenTable:
    def __init__(self, fake_db):
        self.fake_db = fake_db

    async def create(self, data):
        token = SimpleNamespace(
            id=self.fake_db.next_ids["refresh_token"],
            token=data["token"],
            userId=data["userId"],
            expiresAt=data["expiresAt"],
            isRevoked=data.get("isRevoked", False),
            createdAt=utcnow(),
        )
        self.fake_db.next_ids["refresh_token"] += 1
        self.fake_db.refresh_tokens[token.id] = token
        return token


class FakeRestaurantTable:
    def __init__(self, fake_db):
        self.fake_db = fake_db

    async def find_unique(self, where):
        return self.fake_db.restaurants.get(where.get("id"))


class FakeTableTable:
    def __init__(self, fake_db):
        self.fake_db = fake_db

    async def find_unique(self, where):
        table = self.fake_db.tables.get(where.get("id"))
        if not table:
            return None
        restaurant_id = where.get("restaurantId")
        if restaurant_id is not None and table.restaurantId != restaurant_id:
            return None
        return table


class FakeDishTable:
    def __init__(self, fake_db):
        self.fake_db = fake_db

    async def find_unique(self, where):
        return self.fake_db.dishes.get(where.get("id"))

    async def update(self, where, data):
        dish = self.fake_db.dishes[where["id"]]
        if "quantity" in data:
            dish.quantity = data["quantity"]
        return dish

    async def count(self, where=None):
        where = where or {}
        ingredient_id = (
            where.get("ingredients", {})
            .get("some", {})
            .get("ingredientId")
        )
        if ingredient_id is None:
            return 0
        return self.fake_db.ingredient_dish_counts.get(ingredient_id, 0)


class FakeIngredientTable:
    def __init__(self, fake_db):
        self.fake_db = fake_db

    async def find_many(self, where=None, skip=0, take=None, order=None):
        where = where or {}
        records = list(self.fake_db.ingredients.values())

        for field, expected in where.items():
            records = [record for record in records if getattr(record, field) == expected]

        if order:
            field, direction = next(iter(order.items()))
            records.sort(key=lambda record: getattr(record, field), reverse=direction == "desc")

        if skip:
            records = records[skip:]
        if take is not None:
            records = records[:take]
        return records


class FakeOrderTable:
    def __init__(self, fake_db):
        self.fake_db = fake_db

    async def create(self, data):
        order = SimpleNamespace(
            id=self.fake_db.next_ids["order"],
            orderNumber=data["orderNumber"],
            userId=data.get("userId"),
            restaurantId=data["restaurantId"],
            tableId=data.get("tableId"),
            type=data["type"],
            status=data["status"],
            subtotal=data["subtotal"],
            deliveryFee=data["deliveryFee"],
            discount=data["discount"],
            totalAmount=data["totalAmount"],
            deliveryAddressId=data.get("deliveryAddressId"),
            estimatedDeliveryTime=data.get("estimatedDeliveryTime"),
            actualDeliveryTime=data.get("actualDeliveryTime"),
            paymentStatus=data["paymentStatus"],
            paymentMethod=data.get("paymentMethod"),
            notes=data.get("notes"),
            orderTime=data["orderTime"],
            confirmedAt=data.get("confirmedAt"),
            preparedAt=data.get("preparedAt"),
            readyAt=data.get("readyAt"),
            completedAt=data.get("completedAt"),
            createdAt=utcnow(),
            updatedAt=utcnow(),
        )
        self.fake_db.next_ids["order"] += 1
        self.fake_db.orders[order.id] = order
        return order

    async def find_unique(self, where, include=None):
        order = self.fake_db.orders.get(where["id"])
        if not order:
            return None

        items = []
        for order_item in self.fake_db.order_items.values():
            if order_item.orderId != order.id:
                continue
            items.append(
                {
                    "id": order_item.id,
                    "dishId": order_item.dishId,
                    "quantity": order_item.quantity,
                    "unitPrice": order_item.unitPrice,
                    "totalPrice": order_item.totalPrice,
                    "notes": order_item.notes,
                    "dish": {
                        "id": self.fake_db.dishes[order_item.dishId].id,
                        "name": self.fake_db.dishes[order_item.dishId].name,
                    },
                }
            )

        return {
            "id": order.id,
            "orderNumber": order.orderNumber,
            "userId": order.userId,
            "restaurantId": order.restaurantId,
            "tableId": order.tableId,
            "type": order.type,
            "status": order.status,
            "subtotal": order.subtotal,
            "deliveryFee": order.deliveryFee,
            "discount": order.discount,
            "totalAmount": order.totalAmount,
            "deliveryAddressId": order.deliveryAddressId,
            "estimatedDeliveryTime": order.estimatedDeliveryTime,
            "actualDeliveryTime": order.actualDeliveryTime,
            "paymentStatus": order.paymentStatus,
            "paymentMethod": order.paymentMethod,
            "notes": order.notes,
            "orderTime": order.orderTime,
            "confirmedAt": order.confirmedAt,
            "preparedAt": order.preparedAt,
            "readyAt": order.readyAt,
            "completedAt": order.completedAt,
            "createdAt": order.createdAt,
            "updatedAt": order.updatedAt,
            "items": items,
            "user": None,
            "table": {
                "id": self.fake_db.tables[order.tableId].id,
                "number": self.fake_db.tables[order.tableId].number,
            } if order.tableId else None,
            "restaurant": {
                "id": self.fake_db.restaurants[order.restaurantId].id,
                "name": self.fake_db.restaurants[order.restaurantId].name,
            },
        }


class FakeOrderItemTable:
    def __init__(self, fake_db):
        self.fake_db = fake_db

    async def create(self, data):
        order_item = SimpleNamespace(
            id=self.fake_db.next_ids["order_item"],
            orderId=data["orderId"],
            dishId=data["dishId"],
            quantity=data["quantity"],
            unitPrice=data["unitPrice"],
            totalPrice=data["totalPrice"],
            notes=data.get("notes"),
            createdAt=utcnow(),
        )
        self.fake_db.next_ids["order_item"] += 1
        self.fake_db.order_items[order_item.id] = order_item
        return order_item


class FakeDb:
    def __init__(self):
        self.next_ids = {
            "user": 1,
            "refresh_token": 1,
            "order": 1,
            "order_item": 1,
            "ingredient": 1,
        }
        self.users = {}
        self.refresh_tokens = {}
        self.orders = {}
        self.order_items = {}
        self.ingredient_dish_counts = {}

        self.restaurants = {
            1: SimpleNamespace(id=1, name="Test Restaurant", isActive=True)
        }
        self.tables = {
            1: SimpleNamespace(id=1, restaurantId=1, number="T1", isActive=True)
        }
        self.dishes = {
            1: SimpleNamespace(id=1, name="Burger", isAvailable=True, quantity=100, price=25.0)
        }
        self.ingredients = {}

        self.user = FakeUserTable(self)
        self.refreshtoken = FakeRefreshTokenTable(self)
        self.restaurant = FakeRestaurantTable(self)
        self.table = FakeTableTable(self)
        self.dish = FakeDishTable(self)
        self.ingredient = FakeIngredientTable(self)
        self.order = FakeOrderTable(self)
        self.orderitem = FakeOrderItemTable(self)

        self.add_ingredient(
            name="Tomato",
            category="Vegetable",
            isVegetarian=True,
            isVegan=True,
            isGlutenFree=True,
            isDairyFree=True,
            dish_count=2,
        )
        self.add_ingredient(
            name="Cheese",
            category="Dairy",
            allergenInfo="Milk",
            isVegetarian=True,
            isVegan=False,
            isGlutenFree=True,
            isDairyFree=False,
            dish_count=1,
        )

    def add_user(
        self,
        *,
        email=None,
        phone,
        firstName,
        lastName,
        password,
        role=UserRole.CLIENT.value,
        restaurantId=None,
        isActive=True,
    ):
        user = SimpleNamespace(
            id=self.next_ids["user"],
            email=email,
            phone=phone,
            firstName=firstName,
            lastName=lastName,
            password=password,
            role=role,
            restaurantId=restaurantId,
            isActive=isActive,
            createdAt=utcnow(),
            updatedAt=utcnow(),
            restaurant=self.restaurants.get(restaurantId),
            address=None,
        )
        self.next_ids["user"] += 1
        self.users[user.id] = user
        return user

    def add_ingredient(
        self,
        *,
        name,
        category,
        description=None,
        allergenInfo=None,
        isVegetarian=False,
        isVegan=False,
        isGlutenFree=False,
        isDairyFree=False,
        dish_count=0,
    ):
        ingredient = SimpleNamespace(
            id=self.next_ids["ingredient"],
            name=name,
            description=description,
            allergenInfo=allergenInfo,
            category=category,
            isVegetarian=isVegetarian,
            isVegan=isVegan,
            isGlutenFree=isGlutenFree,
            isDairyFree=isDairyFree,
            nutritionalInfo=None,
            isActive=True,
            createdAt=utcnow(),
            updatedAt=utcnow(),
        )
        self.next_ids["ingredient"] += 1
        self.ingredients[ingredient.id] = ingredient
        self.ingredient_dish_counts[ingredient.id] = dish_count
        return ingredient


@pytest.fixture
def fake_db():
    return FakeDb()


@pytest.fixture
def create_user(fake_db):
    def _create_user(
        *,
        email="user@example.com",
        phone=213555000001,
        first_name="Test",
        last_name="User",
        password="Password123",
        role=UserRole.CLIENT.value,
        restaurant_id=None,
    ):
        return fake_db.add_user(
            email=email,
            phone=phone,
            firstName=first_name,
            lastName=last_name,
            password=get_password_hash(password),
            role=role,
            restaurantId=restaurant_id,
        )

    return _create_user


@pytest.fixture
def auth_headers():
    def _auth_headers(user):
        token = create_access_token({"sub": str(user.id)})
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers


@pytest_asyncio.fixture
async def app(fake_db, monkeypatch):
    async def fake_connect_db():
        database_module.db = fake_db

    async def fake_disconnect_db():
        database_module.db = None

    async def fake_ensure_admin_user_exists():
        return None

    async def override_db_session():
        return fake_db

    async def fake_notifications(**kwargs):
        return None

    monkeypatch.setattr(main_module, "connect_db", fake_connect_db)
    monkeypatch.setattr(main_module, "disconnect_db", fake_disconnect_db)
    monkeypatch.setattr(main_module, "ensure_admin_user_exists", fake_ensure_admin_user_exists)
    monkeypatch.setattr(orders_module, "create_restaurant_event_notifications", fake_notifications)

    database_module.db = fake_db
    main_module.app.dependency_overrides[get_db_session] = override_db_session

    yield main_module.app

    main_module.app.dependency_overrides.clear()
    database_module.db = None


@pytest_asyncio.fixture
async def async_client(app):
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
