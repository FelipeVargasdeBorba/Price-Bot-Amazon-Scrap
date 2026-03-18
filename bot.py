import discord
from discord.ext import commands, tasks
import asyncio
import logging
from datetime import datetime

from scraper import get_product_info
from database import Database
from price_monitor import PriceMonitor
from config import BOT_TOKEN, CHECK_INTERVAL_MINUTES, LOG_FILE, SERPAPI_KEY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

db = Database()
monitor = PriceMonitor(db)

@bot.event
async def on_ready():
    logger.info(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")

    if SERPAPI_KEY == "SUA_CHAVE_SERPAPI_AQUI":
        logger.warning("⚠️  SERPAPI_KEY não configurada! Edite o config.py")

    price_check_loop.start()
    logger.info(f"🔄 Loop iniciado (intervalo: {CHECK_INTERVAL_MINUTES} min)")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Argumento faltando. Use `!help` para ver os comandos.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        logger.error(f"Erro no comando: {error}")
        await ctx.send(f"❌ Ocorreu um erro: {str(error)}")

@bot.command(name="monitorar", aliases=["monitor", "add"])
async def monitorar(ctx, *, query: str = None):
    """
    Monitora o preço de um produto na Amazon.

    Uso:
      !monitorar <url da Amazon>
      !monitorar <ASIN>
      !monitorar <nome do produto>

    Exemplos:
      !monitorar https://www.amazon.com.br/dp/B0CHX3QBCH
      !monitorar B0CHX3QBCH
      !monitorar iPhone 16 128gb
    """
    if not query:
        await ctx.send(
            "❌ Informe o produto. Exemplos:\n"
            "`!monitorar https://www.amazon.com.br/dp/B0CHX3QBCH`\n"
            "`!monitorar B0CHX3QBCH`\n"
            "`!monitorar iPhone 16 128gb`"
        )
        return

    if SERPAPI_KEY == "SUA_CHAVE_SERPAPI_AQUI":
        await ctx.send(
            "❌ A chave da SerpAPI não está configurada!\n"
            "Edite o `config.py` e adicione sua chave em `SERPAPI_KEY`.\n"
            "Crie sua conta gratuita em: https://serpapi.com/users/sign_up"
        )
        return

    await ctx.send(f"🔍 Buscando **{query[:60]}** na Amazon, aguarde...")

    try:
        product = await asyncio.get_event_loop().run_in_executor(
            None, get_product_info, query
        )
    except Exception as e:
        logger.error(f"Erro ao buscar produto: {e}")
        await ctx.send(f"❌ Erro ao buscar o produto.\n`{str(e)}`")
        return

    if not product:
        await ctx.send(
            "❌ Produto não encontrado ou sem preço disponível na Amazon.\n"
            "Tente um nome mais específico ou use a URL direta do produto."
        )
        return

    user_id = str(ctx.author.id)
    channel_id = str(ctx.channel.id)

    url = product.get("url", f"https://www.amazon.com.br/dp/{product.get('asin', '')}")

    product_id = db.add_product(
        user_id=user_id,
        channel_id=channel_id,
        url=url,
        name=product["name"],
        price=product["price"]
    )

    embed = discord.Embed(
        title="✅ Produto adicionado ao monitoramento!",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="📦 Produto", value=product["name"][:256], inline=False)
    embed.add_field(name="💰 Preço Atual", value=f"R$ {product['price']:.2f}", inline=True)
    embed.add_field(name="⏱️ Verificação", value=f"A cada {CHECK_INTERVAL_MINUTES} min", inline=True)
    embed.add_field(name="🆔 ID", value=f"`{product_id}`", inline=True)
    if product.get("asin"):
        embed.add_field(name="🏷️ ASIN", value=f"`{product['asin']}`", inline=True)
    embed.add_field(name="🔗 Link", value=f"[Ver na Amazon]({url})", inline=False)
    embed.set_footer(text=f"Monitorado por {ctx.author.display_name} • Amazon.com.br via SerpAPI")

    await ctx.send(embed=embed)
    logger.info(f"{ctx.author} adicionou: {product['name'][:50]} | R$ {product['price']:.2f}")


@bot.command(name="lista", aliases=["list", "produtos"])
async def lista(ctx):
    """Lista todos os produtos que você está monitorando."""
    user_id = str(ctx.author.id)
    products = db.get_user_products(user_id)

    if not products:
        await ctx.send(
            "📋 Você não está monitorando nenhum produto.\n"
            "Use `!monitorar <produto ou URL>` para começar."
        )
        return

    embed = discord.Embed(
        title=f"📋 Seus produtos monitorados ({len(products)})",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    for p in products:
        diff = p["current_price"] - p["initial_price"]
        diff_str = f"({'📉' if diff < 0 else '📈'} R$ {diff:+.2f})" if diff != 0 else ""
        embed.add_field(
            name=f"[{p['id']}] {p['name'][:50]}",
            value=(
                f"💰 Preço atual: **R$ {p['current_price']:.2f}** {diff_str}\n"
                f"📊 Preço inicial: R$ {p['initial_price']:.2f}\n"
                f"🕐 Última verificação: {p['last_checked'] or 'Nunca'}\n"
                f"🔗 [Ver na Amazon]({p['url']})"
            ),
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command(name="parar", aliases=["stop", "remover"])
async def parar(ctx, product_id: int = None):
    """Para o monitoramento de um produto. Uso: !parar <id>"""
    if product_id is None:
        await ctx.send("❌ Informe o ID do produto. Use `!lista` para ver seus produtos.")
        return

    user_id = str(ctx.author.id)
    product = db.get_product(product_id, user_id)

    if not product:
        await ctx.send(f"❌ Produto `{product_id}` não encontrado ou não pertence a você.")
        return

    db.remove_product(product_id, user_id)
    embed = discord.Embed(
        title="🛑 Monitoramento pausado",
        description=f"**{product['name'][:100]}** removido.",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    await ctx.send(embed=embed)
    logger.info(f"{ctx.author} removeu produto ID {product_id}")


@bot.command(name="verificar", aliases=["check"])
async def verificar(ctx, product_id: int = None):
    """Verifica o preço de um produto agora. Uso: !verificar <id>"""
    if product_id is None:
        await ctx.send("❌ Informe o ID. Use `!lista` para ver seus produtos.")
        return

    user_id = str(ctx.author.id)
    product = db.get_product(product_id, user_id)

    if not product:
        await ctx.send(f"❌ Produto `{product_id}` não encontrado.")
        return

    await ctx.send(f"🔍 Verificando **{product['name'][:50]}**... (consome 1 busca da SerpAPI)")

    try:
        result = await monitor.check_product(product)
        if result:
            old_price, new_price, diff = result
            sign = "📉" if diff < 0 else "📈"
            embed = discord.Embed(
                title=f"{sign} Preço atualizado!",
                color=discord.Color.green() if diff < 0 else discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="📦 Produto", value=product["name"][:256], inline=False)
            embed.add_field(name="💰 Preço Antigo", value=f"R$ {old_price:.2f}", inline=True)
            embed.add_field(name="💰 Preço Novo", value=f"R$ {new_price:.2f}", inline=True)
            embed.add_field(name="📊 Diferença", value=f"R$ {diff:+.2f}", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"✅ Preço mantido em **R$ {product['current_price']:.2f}**")
    except Exception as e:
        await ctx.send(f"❌ Erro ao verificar: `{str(e)}`")


@bot.command(name="buscar", aliases=["search"])
async def buscar(ctx, *, query: str = None):
    """
    Busca um produto na Amazon sem monitorar. Útil para testar.
    Uso: !buscar iPhone 16 128gb
    """
    if not query:
        await ctx.send("❌ Informe o produto. Ex: `!buscar iPhone 16 128gb`")
        return

    await ctx.send(f"🔍 Buscando **{query[:60]}**...")

    try:
        product = await asyncio.get_event_loop().run_in_executor(
            None, get_product_info, query
        )
    except Exception as e:
        await ctx.send(f"❌ Erro: `{str(e)}`")
        return

    if not product:
        await ctx.send("❌ Produto não encontrado ou sem preço disponível.")
        return

    embed = discord.Embed(
        title="🔎 Resultado da busca",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="📦 Produto", value=product["name"][:256], inline=False)
    embed.add_field(name="💰 Preço", value=f"R$ {product['price']:.2f}", inline=True)
    if product.get("asin"):
        embed.add_field(name="🏷️ ASIN", value=f"`{product['asin']}`", inline=True)
    embed.add_field(name="🔗 Link", value=f"[Ver na Amazon]({product['url']})", inline=False)
    embed.set_footer(text="Use !monitorar para acompanhar este produto")
    await ctx.send(embed=embed)


@bot.command(name="help", aliases=["ajuda"])
async def help_command(ctx):
    """Exibe a lista de comandos."""
    embed = discord.Embed(
        title="🤖 Bot Monitor de Preços — Amazon",
        description="Monitore preços na Amazon e receba alertas automáticos!",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name="📌 Comandos",
        value=(
            "`!monitorar <url/ASIN/nome>` — Adiciona produto ao monitoramento\n"
            "`!buscar <nome>` — Busca um produto sem monitorar\n"
            "`!lista` — Lista seus produtos monitorados\n"
            "`!verificar <id>` — Verifica o preço agora\n"
            "`!parar <id>` — Para o monitoramento\n"
            "`!help` — Esta mensagem"
        ),
        inline=False
    )
    embed.add_field(
        name="💡 Exemplos de uso",
        value=(
            "`!monitorar https://www.amazon.com.br/dp/B0CHX3QBCH`\n"
            "`!monitorar B0CHX3QBCH`\n"
            "`!monitorar iPhone 16 128gb`"
        ),
        inline=False
    )
    embed.add_field(
        name="⚙️ Como funciona",
        value=f"Verificação automática a cada **{CHECK_INTERVAL_MINUTES} minutos** via SerpAPI.",
        inline=False
    )
    embed.add_field(
        name="⚠️ Limite de buscas",
        value="Plano gratuito SerpAPI: **100 buscas/mês**. Cada verificação = 1 busca.",
        inline=False
    )
    embed.set_footer(text="Amazon Price Monitor Bot • Powered by SerpAPI")
    await ctx.send(embed=embed)

@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def price_check_loop():
    """Verifica preços de todos os produtos cadastrados."""
    logger.info("🔄 Iniciando ciclo de verificação...")
    all_products = db.get_all_products()

    if not all_products:
        logger.info("📭 Nenhum produto cadastrado.")
        return

    logger.info(f"📦 Verificando {len(all_products)} produto(s) (consome {len(all_products)} busca(s) SerpAPI)...")

    for product in all_products:
        try:
            result = await monitor.check_product(product)

            if result:
                old_price, new_price, diff = result
                user = await bot.fetch_user(int(product["user_id"]))

                sign = "📉" if diff < 0 else "📈"
                color = discord.Color.green() if diff < 0 else discord.Color.red()

                embed = discord.Embed(
                    title=f"{sign} Mudança de preço detectada!",
                    color=color,
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="📦 Produto", value=product["name"][:256], inline=False)
                embed.add_field(name="💰 Preço Antigo", value=f"R$ {old_price:.2f}", inline=True)
                embed.add_field(name="💰 Preço Novo", value=f"R$ {new_price:.2f}", inline=True)
                embed.add_field(name="📊 Diferença", value=f"R$ {diff:+.2f}", inline=True)
                embed.add_field(name="🔗 Link", value=f"[Ver na Amazon]({product['url']})", inline=False)
                embed.set_footer(text="Amazon Price Monitor • Notificacao via DM")

                try:
                    await user.send(embed=embed)
                    logger.info(f"DM enviada para {user}: {product['name'][:40]} | R$ {old_price:.2f} -> R$ {new_price:.2f}")
                except discord.Forbidden:
                    channel = bot.get_channel(int(product["channel_id"]))
                    if channel:
                        await channel.send(
                            f"{user.mention} ⚠️ Nao consegui te enviar DM. "
                            f"Ative em **Configuracoes > Privacidade > Permitir mensagens diretas**!\n",
                            embed=embed
                        )
                    logger.warning(f"DM bloqueada para {user}, notificacao enviada no canal.")

            await asyncio.sleep(3)

        except Exception as e:
            logger.error(f"❌ Erro ao verificar produto ID {product['id']}: {e}")

    logger.info("✅ Ciclo concluído.")


@price_check_loop.before_loop
async def before_loop():
    await bot.wait_until_ready()

if __name__ == "__main__":
    if not BOT_TOKEN or BOT_TOKEN == "SEU_TOKEN_AQUI":
        logger.error("❌ Token do Discord não configurado! Edite o config.py")
        exit(1)

    if not SERPAPI_KEY or SERPAPI_KEY == "SUA_CHAVE_SERPAPI_AQUI":
        logger.warning("⚠️  SERPAPI_KEY não configurada! O bot iniciará mas os comandos falharão.")

    logger.info("🚀 Iniciando bot...")
    bot.run(BOT_TOKEN)