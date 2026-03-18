import sqlite3
import logging
from datetime import datetime
from config import DATABASE_FILE

logger = logging.getLogger(__name__)


class Database:
    """Gerencia todas as operações de banco de dados SQLite."""

    def __init__(self):
        self.db_file = DATABASE_FILE
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Cria e retorna uma conexão com o banco de dados."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Inicializa o banco de dados e cria as tabelas necessárias."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       TEXT    NOT NULL,
                    channel_id    TEXT    NOT NULL,
                    url           TEXT    NOT NULL,
                    name          TEXT    NOT NULL,
                    initial_price REAL    NOT NULL,
                    current_price REAL    NOT NULL,
                    last_checked  TEXT,
                    created_at    TEXT    NOT NULL,
                    active        INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    price      REAL    NOT NULL,
                    recorded_at TEXT   NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)
            conn.commit()
        logger.info(f"📦 Banco de dados inicializado: {self.db_file}")

    def add_product(self, user_id: str, channel_id: str, url: str, name: str, price: float) -> int:
        """
        Adiciona um novo produto para monitoramento.

        Returns:
            ID do produto criado
        """
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO products (user_id, channel_id, url, name, initial_price, current_price, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, channel_id, url, name, price, price, now)
            )
            product_id = cursor.lastrowid

            conn.execute(
                "INSERT INTO price_history (product_id, price, recorded_at) VALUES (?, ?, ?)",
                (product_id, price, now)
            )
            conn.commit()

        logger.info(f"➕ Produto adicionado ao DB: ID={product_id}, {name[:40]}, R$ {price:.2f}")
        return product_id

    def get_user_products(self, user_id: str) -> list[dict]:
        """Retorna todos os produtos ativos de um usuário."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM products WHERE user_id = ? AND active = 1 ORDER BY id",
                (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_all_products(self) -> list[dict]:
        """Retorna todos os produtos ativos de todos os usuários."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM products WHERE active = 1"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_product(self, product_id: int, user_id: str) -> dict | None:
        """Retorna um produto específico de um usuário."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE id = ? AND user_id = ? AND active = 1",
                (product_id, user_id)
            ).fetchone()
        return dict(row) if row else None

    def update_price(self, product_id: int, new_price: float):
        """Atualiza o preço atual de um produto e registra no histórico."""
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE products SET current_price = ?, last_checked = ? WHERE id = ?",
                (new_price, now, product_id)
            )
            conn.execute(
                "INSERT INTO price_history (product_id, price, recorded_at) VALUES (?, ?, ?)",
                (product_id, new_price, now)
            )
            conn.commit()

    def update_last_checked(self, product_id: int):
        """Atualiza apenas o timestamp de última verificação."""
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE products SET last_checked = ? WHERE id = ?",
                (now, product_id)
            )
            conn.commit()

    def remove_product(self, product_id: int, user_id: str):
        """Marca um produto como inativo (soft delete)."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE products SET active = 0 WHERE id = ? AND user_id = ?",
                (product_id, user_id)
            )
            conn.commit()
        logger.info(f"🗑️ Produto ID={product_id} removido do monitoramento.")

    def get_price_history(self, product_id: int) -> list[dict]:
        """Retorna o histórico de preços de um produto."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM price_history WHERE product_id = ? ORDER BY recorded_at DESC LIMIT 20",
                (product_id,)
            ).fetchall()
        return [dict(row) for row in rows]
