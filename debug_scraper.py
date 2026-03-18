import requests
from bs4 import BeautifulSoup
import re
import json

URL = "https://www.mercadolivre.com.br/apple-iphone-16-128-gb-ultramarine-distribuidor-autorizado/p/MLB1040287800"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

print("=" * 60)
print("🔍 DIAGNÓSTICO DO SCRAPER - MERCADO LIVRE")
print("=" * 60)
print(f"\n📡 Acessando: {URL}\n")

resp = requests.get(URL, headers=HEADERS, timeout=15)
print(f"✅ Status HTTP: {resp.status_code}")
print(f"📄 Tamanho da resposta: {len(resp.text)} chars")

soup = BeautifulSoup(resp.text, "html.parser")

print("\n── TAG <title> ──────────────────────────────────────")
title = soup.find("title")
print(f"  {title.get_text(strip=True) if title else 'NÃO ENCONTRADO'}")

print("\n── META og:title ────────────────────────────────────")
og = soup.find("meta", {"property": "og:title"})
print(f"  {og['content'] if og else 'NÃO ENCONTRADO'}")

print("\n── META itemprop=price ──────────────────────────────")
mp = soup.find("meta", {"itemprop": "price"})
print(f"  {mp['content'] if mp else 'NÃO ENCONTRADO'}")

print("\n── TODAS AS TAGS <h1> ───────────────────────────────")
h1s = soup.find_all("h1")
if h1s:
    for h in h1s:
        print(f"  class={h.get('class')} | texto='{h.get_text(strip=True)[:80]}'")
else:
    print("  NÃO ENCONTRADO")

print("\n── JSON-LD (application/ld+json) ────────────────────")
scripts = soup.find_all("script", {"type": "application/ld+json"})
if scripts:
    for i, s in enumerate(scripts[:3]):
        try:
            data = json.loads(s.string or "")
            print(f"  [{i}] {json.dumps(data, ensure_ascii=False)[:200]}")
        except:
            print(f"  [{i}] inválido")
else:
    print("  NÃO ENCONTRADO")

print("\n── ELEMENTOS COM CLASSE CONTENDO 'price' ────────────")
for el in soup.find_all(class_=re.compile(r"price", re.I)):
    txt = el.get_text(strip=True)[:60]
    if txt:
        print(f"  tag={el.name} | class={el.get('class')} | texto='{txt}'")

print("\n── ELEMENTOS COM CLASSE CONTENDO 'andes' ────────────")
for el in soup.find_all(class_=re.compile(r"andes-money", re.I))[:5]:
    txt = el.get_text(strip=True)[:60]
    print(f"  tag={el.name} | class={el.get('class')} | texto='{txt}'")

print("\n── ELEMENTOS COM CLASSE CONTENDO 'poly' ─────────────")
for el in soup.find_all(class_=re.compile(r"poly", re.I))[:5]:
    txt = el.get_text(strip=True)[:60]
    if txt:
        print(f"  tag={el.name} | class={el.get('class')} | texto='{txt}'")

print("\n── PRIMEIROS 500 CHARS DO TEXTO DA PÁGINA ───────────")
print(soup.get_text(strip=True)[:500])

print("\n" + "=" * 60)
print("✅ Diagnóstico concluído. Envie o resultado para análise.")
print("=" * 60)