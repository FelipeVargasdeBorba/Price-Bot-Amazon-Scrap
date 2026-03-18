import asyncio
import logging
from scraper import get_product_info
from database import Database

logger = logging.getLogger(__name__)


class PriceMonitor:
    """
    Gerencia a lógica de verificação e comparação de preços.
    """

    def __init__(self, db: Database):
        self.db = db

    async def check_product(self, product: dict) -> tuple[float, float, float] | None:
        """
        Verifica se o preço de um produto mudou.

        Args:
            product: Dicionário com dados do produto (id, url, current_price, name)

        Returns:
            Tupla (old_price, new_price, difference) se houve mudança, ou None
        """
        product_id = product["id"]
        url = product["url"]
        old_price = product["current_price"]
        name = product["name"]

        logger.info(f"🔍 Verificando: [{product_id}] {name[:40]}...")

        try:
            new_info = await asyncio.get_event_loop().run_in_executor(
                None, get_product_info, url
            )

            if not new_info or new_info["price"] is None:
                logger.warning(f"⚠️ Não foi possível obter preço do produto ID={product_id}")
                self.db.update_last_checked(product_id)
                return None

            new_price = new_info["price"]

            self.db.update_last_checked(product_id)

            if self.prices_differ(old_price, new_price):
                diff = self.calculate_difference(old_price, new_price)
                self.db.update_price(product_id, new_price)
                logger.info(
                    f"💹 Mudança detectada: [{product_id}] {name[:40]} | "
                    f"R$ {old_price:.2f} → R$ {new_price:.2f} ({diff:+.2f})"
                )
                return old_price, new_price, diff

            logger.info(f"✅ Preço inalterado: [{product_id}] R$ {old_price:.2f}")
            return None

        except Exception as e:
            logger.error(f"❌ Erro ao verificar produto ID={product_id}: {e}")
            raise

    @staticmethod
    def prices_differ(old: float, new: float, tolerance: float = 0.01) -> bool:
        """
        Verifica se dois preços são diferentes, respeitando uma tolerância.

        Args:
            old: Preço antigo
            new: Preço novo
            tolerance: Diferença mínima para considerar uma mudança (padrão: R$ 0,01)
        """
        return abs(new - old) > tolerance

    @staticmethod
    def calculate_difference(old: float, new: float) -> float:
        """
        Calcula a diferença entre dois preços.

        Returns:
            Valor negativo = redução de preço (bom!)
            Valor positivo = aumento de preço
        """
        return new - old

    @staticmethod
    def calculate_percentage_change(old: float, new: float) -> float:
        """Calcula a variação percentual entre dois preços."""
        if old == 0:
            return 0.0
        return ((new - old) / old) * 100

    def format_price_change_message(self, product: dict, old_price: float, new_price: float) -> str:
        """Formata uma mensagem de texto simples sobre a mudança de preço."""
        diff = self.calculate_difference(old_price, new_price)
        pct = self.calculate_percentage_change(old_price, new_price)
        emoji = "📉" if diff < 0 else "📈"
        action = "caiu" if diff < 0 else "subiu"

        return (
            f"{emoji} **{product['name'][:80]}**\n"
            f"Preço {action} de R$ {old_price:.2f} para R$ {new_price:.2f} "
            f"(R$ {diff:+.2f} | {pct:+.1f}%)"
        )
