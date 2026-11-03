import asyncio
from datetime import datetime

import aiosqlite

from bot.utils import dt_to_str

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    price       INTEGER NOT NULL,
    photo_id    TEXT,
    in_stock    INTEGER NOT NULL DEFAULT 1,
    hidden      INTEGER NOT NULL DEFAULT 0,
    deleted     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category_id, hidden, deleted);

CREATE TABLE IF NOT EXISTS cart (
    user_id    INTEGER NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty        INTEGER NOT NULL,
    PRIMARY KEY (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    username       TEXT,
    full_name      TEXT    NOT NULL,
    client_name    TEXT    NOT NULL,
    phone          TEXT    NOT NULL,
    delivery       TEXT    NOT NULL,            -- pickup | delivery
    address        TEXT,
    comment        TEXT,
    items_total    INTEGER NOT NULL,
    delivery_price INTEGER NOT NULL,
    total          INTEGER NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'new',
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, created_at);

-- Название и цена фиксируются на момент заказа
CREATE TABLE IF NOT EXISTS order_items (
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    price      INTEGER NOT NULL,
    qty        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);

CREATE TABLE IF NOT EXISTS order_messages (
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    chat_id    INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    PRIMARY KEY (order_id, chat_id, message_id)
);
"""

PRODUCT_SELECT = """
SELECT p.*, c.name AS category_name
FROM products p JOIN categories c ON c.id = p.category_id
"""
VISIBLE = "p.hidden = 0 AND p.deleted = 0"
MAX_QTY = 99


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.connect() не вызван")
        return self._conn

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path, isolation_level=None)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(SCHEMA)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cur:
            return list(await cur.fetchall())

    async def _write(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        async with self._lock:
            return await self.conn.execute(sql, params)

    # --- Категории ---

    async def all_categories(self) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM categories ORDER BY name")

    async def visible_categories(self) -> list[aiosqlite.Row]:
        return await self._fetchall(
            f"""SELECT c.id, c.name, COUNT(p.id) AS cnt
                FROM categories c JOIN products p ON p.category_id = c.id
                WHERE {VISIBLE} GROUP BY c.id ORDER BY c.name"""
        )

    async def get_category(self, category_id: int) -> aiosqlite.Row | None:
        return await self._fetchone("SELECT * FROM categories WHERE id = ?", (category_id,))

    async def get_or_create_category(self, name: str) -> int:
        async with self._lock:
            await self.conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
        row = await self._fetchone("SELECT id FROM categories WHERE name = ?", (name,))
        return row["id"]

    # --- Товары ---

    async def add_product(
        self, *, category_id: int, name: str, description: str, price: int, photo_id: str | None
    ) -> int:
        cur = await self._write(
            "INSERT INTO products (category_id, name, description, price, photo_id) VALUES (?, ?, ?, ?, ?)",
            (category_id, name, description, price, photo_id),
        )
        return cur.lastrowid

    async def get_product(self, product_id: int) -> aiosqlite.Row | None:
        return await self._fetchone(f"{PRODUCT_SELECT} WHERE p.id = ?", (product_id,))

    async def category_products(self, category_id: int) -> list[aiosqlite.Row]:
        return await self._fetchall(
            f"{PRODUCT_SELECT} WHERE p.category_id = ? AND {VISIBLE} ORDER BY p.id", (category_id,)
        )

    async def all_products(self) -> list[aiosqlite.Row]:
        return await self._fetchall(f"{PRODUCT_SELECT} WHERE p.deleted = 0 ORDER BY c.name, p.id")

    async def set_product(self, product_id: int, field: str, value: int) -> None:
        if field not in {"price", "in_stock", "hidden"}:
            raise ValueError(field)
        await self._write(f"UPDATE products SET {field} = ? WHERE id = ?", (value, product_id))

    async def delete_product(self, product_id: int) -> None:
        async with self._lock:
            await self.conn.execute("UPDATE products SET deleted = 1 WHERE id = ?", (product_id,))
            await self.conn.execute("DELETE FROM cart WHERE product_id = ?", (product_id,))

    # --- Корзина ---

    async def cart_qty(self, user_id: int, product_id: int) -> int:
        row = await self._fetchone("SELECT qty FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        return row["qty"] if row else 0

    async def cart_change(self, user_id: int, product_id: int, delta: int) -> int:
        async with self._lock:
            if delta > 0:
                await self.conn.execute(
                    """INSERT INTO cart (user_id, product_id, qty) VALUES (?, ?, MIN(?, ?))
                       ON CONFLICT (user_id, product_id) DO UPDATE SET qty = MIN(qty + excluded.qty, ?)""",
                    (user_id, product_id, delta, MAX_QTY, MAX_QTY),
                )
            else:
                await self.conn.execute(
                    "UPDATE cart SET qty = qty + ? WHERE user_id = ? AND product_id = ?", (delta, user_id, product_id)
                )
                await self.conn.execute("DELETE FROM cart WHERE user_id = ? AND qty <= 0", (user_id,))
        return await self.cart_qty(user_id, product_id)

    async def cart_remove(self, user_id: int, product_id: int) -> None:
        await self._write("DELETE FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))

    async def cart_clear(self, user_id: int) -> None:
        await self._write("DELETE FROM cart WHERE user_id = ?", (user_id,))

    async def cart_items(self, user_id: int) -> list[aiosqlite.Row]:
        return await self._fetchall(
            """SELECT p.id AS product_id, p.name, p.price, p.in_stock, p.hidden, p.deleted, c.qty
               FROM cart c JOIN products p ON p.id = c.product_id
               WHERE c.user_id = ? ORDER BY c.rowid""",
            (user_id,),
        )

    # --- Заказы ---

    async def create_order(
        self,
        *,
        user_id: int,
        username: str | None,
        full_name: str,
        client_name: str,
        phone: str,
        delivery: str,
        address: str | None,
        comment: str | None,
        items: list,
        items_total: int,
        delivery_price: int,
        now: datetime,
    ) -> int:
        """Создаёт заказ с позициями и очищает корзину — одной транзакцией."""
        ts = dt_to_str(now)
        async with self._lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                cur = await self.conn.execute(
                    """INSERT INTO orders (user_id, username, full_name, client_name, phone, delivery, address,
                                           comment, items_total, delivery_price, total, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, username, full_name, client_name, phone, delivery, address, comment,
                     items_total, delivery_price, items_total + delivery_price, ts, ts),
                )
                order_id = cur.lastrowid
                await self.conn.executemany(
                    "INSERT INTO order_items (order_id, product_id, name, price, qty) VALUES (?, ?, ?, ?, ?)",
                    [(order_id, i["product_id"], i["name"], i["price"], i["qty"]) for i in items],
                )
                await self.conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
                await self.conn.execute("COMMIT")
                return order_id
            except BaseException:
                await self.conn.execute("ROLLBACK")
                raise

    async def get_order(self, order_id: int) -> aiosqlite.Row | None:
        return await self._fetchone("SELECT * FROM orders WHERE id = ?", (order_id,))

    async def order_items(self, order_id: int) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM order_items WHERE order_id = ? ORDER BY rowid", (order_id,))

    async def user_orders(self, user_id: int, limit: int = 5) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))

    async def recent_orders(self, limit: int = 10, status: str | None = None) -> list[aiosqlite.Row]:
        if status:
            return await self._fetchall(
                "SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit)
            )
        return await self._fetchall("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))

    async def all_orders(self) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM orders ORDER BY id")

    async def count_orders_since(self, user_id: int, since: datetime) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) FROM orders WHERE user_id = ? AND created_at >= ?", (user_id, dt_to_str(since))
        )
        return row[0]

    async def last_contact(self, user_id: int) -> aiosqlite.Row | None:
        return await self._fetchone(
            "SELECT client_name, phone, address FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
        )

    async def set_status(self, order_id: int, status: str, now: datetime, only_from: str | None = None) -> bool:
        sql = "UPDATE orders SET status = ?, updated_at = ? WHERE id = ? AND status != ?"
        params: tuple = (status, dt_to_str(now), order_id, status)
        if only_from:
            sql += " AND status = ?"
            params += (only_from,)
        cur = await self._write(sql, params)
        return cur.rowcount > 0

    async def add_message(self, order_id: int, chat_id: int, message_id: int) -> None:
        await self._write(
            "INSERT OR IGNORE INTO order_messages (order_id, chat_id, message_id) VALUES (?, ?, ?)",
            (order_id, chat_id, message_id),
        )

    async def order_messages(self, order_id: int) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT chat_id, message_id FROM order_messages WHERE order_id = ?", (order_id,))

    # --- Статистика ---

    async def stats_since(self, since: datetime) -> tuple[int, int]:
        row = await self._fetchone(
            "SELECT COUNT(*), COALESCE(SUM(total), 0) FROM orders WHERE status != 'cancelled' AND created_at >= ?",
            (dt_to_str(since),),
        )
        return row[0], row[1]

    async def top_products(self, since: datetime, limit: int = 5) -> list[aiosqlite.Row]:
        return await self._fetchall(
            """SELECT i.name, SUM(i.qty) AS qty, SUM(i.qty * i.price) AS revenue
               FROM order_items i JOIN orders o ON o.id = i.order_id
               WHERE o.status != 'cancelled' AND o.created_at >= ?
               GROUP BY i.product_id ORDER BY qty DESC, revenue DESC LIMIT ?""",
            (dt_to_str(since), limit),
        )
