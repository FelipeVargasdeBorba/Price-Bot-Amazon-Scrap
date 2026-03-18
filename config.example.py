"""
config.example.py - Modelo de configuração
Copie este arquivo para config.py e preencha com suas chaves:
  cp config.example.py config.py
"""

# Token do bot Discord
# Obtenha em: https://discord.com/developers/applications
BOT_TOKEN = "SEU_TOKEN_AQUI"

# Chave da SerpAPI (100 buscas/mês grátis)
# Crie sua conta em: https://serpapi.com/users/sign_up
# Copie sua chave em: https://serpapi.com/manage-api-key
SERPAPI_KEY = "SUA_CHAVE_SERPAPI_AQUI"

# Intervalo de verificação em minutos
# Plano gratuito SerpAPI (100 buscas/mês): use 480 ou mais
# Plano pago (5000/mês): pode usar 30-60
CHECK_INTERVAL_MINUTES = 480

# Arquivos do sistema (não precisa alterar)
DATABASE_FILE = "products.db"
LOG_FILE = "bot.log"
REQUEST_TIMEOUT = 15
SCRAPER_HEADERS = {}
