import requests
import re
import logging
from config import REQUEST_TIMEOUT, SERPAPI_KEY

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"


def get_product_info(query: str) -> dict | None:
    """
    Busca nome e menor preço de um produto na Amazon via SerpAPI.

    Aceita dois formatos:
      - Nome/busca:  "iPhone 16 128gb"
      - URL Amazon:  "https://www.amazon.com.br/dp/B0CHX3QBCH"
      - ASIN direto: "B0CHX3QBCH"

    Returns:
        dict com 'name', 'price', 'asin' e 'url', ou None em caso de falha
    """
    query = query.strip().strip("<>")

    asin = _extract_asin(query)

    if asin:
        logger.info(f"Buscando ASIN: {asin}")
        return _fetch_by_asin(asin)
    else:
        logger.info(f"Buscando por nome: {query[:60]}")
        return _search_by_name(query)


def _extract_asin(text: str) -> str | None:
    """
    Extrai o ASIN de uma URL da Amazon ou detecta se o texto é um ASIN.

    Formatos suportados:
      - https://www.amazon.com.br/dp/B0CHX3QBCH
      - https://www.amazon.com.br/gp/product/B0CHX3QBCH
      - B0CHX3QBCH (ASIN direto)
    """
    url_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", text, re.IGNORECASE)
    if url_match:
        return url_match.group(1).upper()

    asin_match = re.fullmatch(r"B[A-Z0-9]{9}", text.strip(), re.IGNORECASE)
    if asin_match:
        return text.strip().upper()

    return None

def _fetch_by_asin(asin: str) -> dict | None:
    """Busca dados de um produto específico pelo ASIN via SerpAPI."""
    params = {
        "engine": "amazon_product",
        "asin": asin,
        "amazon_domain": "amazon.com.br",
        "api_key": SERPAPI_KEY,
    }

    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=REQUEST_TIMEOUT)

        if resp.status_code == 401:
            raise ValueError("Chave da SerpAPI invalida. Verifique SERPAPI_KEY no config.py")
        if resp.status_code == 429:
            raise RuntimeError("Limite de buscas da SerpAPI atingido. Aguarde ou faca upgrade.")

        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise ValueError(f"SerpAPI: {data['error']}")

        product = data.get("product_results", {})
        if not product:
            logger.warning(f"Produto ASIN {asin} nao encontrado.")
            return None

        name = product.get("title", "").strip()
        price = _extract_price_from_product(product)

        if not name:
            logger.warning(f"Nome nao encontrado para ASIN {asin}")
            return None
        if price is None:
            logger.warning(f"Preco indisponivel para '{name[:50]}'")
            return None

        url = f"https://www.amazon.com.br/dp/{asin}"
        logger.info(f"Produto encontrado: {name[:60]} | R$ {price:.2f}")
        return {"name": name, "price": price, "asin": asin, "url": url}

    except (ValueError, RuntimeError):
        raise
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Falha de conexao com a SerpAPI.")
    except requests.exceptions.Timeout:
        raise TimeoutError("A SerpAPI demorou muito para responder.")
    except Exception as e:
        logger.error(f"Erro ao buscar ASIN {asin}: {e}")
        raise

def _search_by_name(query: str) -> dict | None:
    """Busca produtos na Amazon por nome. Retorna o primeiro com preco disponivel."""
    params = {
        "engine": "amazon",
        "k": query,
        "amazon_domain": "amazon.com.br",
        "api_key": SERPAPI_KEY,
    }

    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=REQUEST_TIMEOUT)

        if resp.status_code == 401:
            raise ValueError("Chave da SerpAPI invalida. Verifique SERPAPI_KEY no config.py")
        if resp.status_code == 429:
            raise RuntimeError("Limite de buscas da SerpAPI atingido.")

        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise ValueError(f"SerpAPI: {data['error']}")

        results = data.get("organic_results", [])
        if not results:
            logger.warning(f"Nenhum resultado para: {query}")
            return None

        for item in results[:5]:
            name = item.get("title", "").strip()
            if not name:
                continue

            price = _extract_price_from_result(item)
            if price is None:
                continue

            asin = item.get("asin", "")
            url = item.get("link") or (f"https://www.amazon.com.br/dp/{asin}" if asin else "")

            logger.info(f"Produto encontrado: {name[:60]} | R$ {price:.2f}")
            return {"name": name, "price": price, "asin": asin, "url": url}

        logger.warning(f"Nenhum resultado com preco disponivel para: {query}")
        return None

    except (ValueError, RuntimeError):
        raise
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Falha de conexao com a SerpAPI.")
    except requests.exceptions.Timeout:
        raise TimeoutError("A SerpAPI demorou muito para responder.")
    except Exception as e:
        logger.error(f"Erro na busca '{query}': {e}")
        raise

def _extract_price_from_product(product: dict) -> float | None:
    """Extrai preco de resultado amazon_product (varias chaves possiveis)."""
    for key in ("price", "buybox_winner", "new_price"):
        val = product.get(key)
        if isinstance(val, dict):
            val = val.get("value") or val.get("raw")
        if val is not None:
            parsed = _parse_price(str(val))
            if parsed:
                return parsed

    prices_list = product.get("prices", [])
    if prices_list:
        values = [_parse_price(str(p.get("value") or p.get("raw", ""))) for p in prices_list]
        values = [v for v in values if v]
        if values:
            return min(values)

    return None


def _extract_price_from_result(item: dict) -> float | None:
    """Extrai preco de resultado amazon search."""
    price_data = item.get("price")
    if price_data is not None:
        if isinstance(price_data, (int, float)):
            return float(price_data)
        if isinstance(price_data, dict):
            val = price_data.get("value") or price_data.get("raw", "")
            parsed = _parse_price(str(val))
            if parsed:
                return parsed
        parsed = _parse_price(str(price_data))
        if parsed:
            return parsed

    prices = item.get("prices", [])
    if prices:
        values = [_parse_price(str(p.get("value") or p.get("raw", ""))) for p in prices]
        values = [v for v in values if v]
        if values:
            return min(values)

    return None


def _parse_price(raw: str) -> float | None:
    """
    Converte string de preco para float.
    Suporta: 'R$ 1.299,90', '1299.90', '1,299.90'
    """
    if not raw:
        return None

    clean = re.sub(r"[R$\s]", "", raw).strip()

    if re.match(r"^\d{1,3}(\.\d{3})*,\d{2}$", clean):
        clean = clean.replace(".", "").replace(",", ".")
    elif re.match(r"^\d{1,3}(,\d{3})*\.\d{2}$", clean):
        clean = clean.replace(",", "")
    else:
        clean = re.sub(r"[^\d.]", "", clean)

    try:
        val = float(clean)
        return val if val >= 0.01 else None
    except ValueError:
        return None


def validate_amazon_url(url: str) -> bool:
    """Valida se a URL pertence a Amazon."""
    return "amazon.com" in url or "amzn.to" in url
