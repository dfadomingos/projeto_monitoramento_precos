import cloudscraper
from bs4 import BeautifulSoup
import psycopg2
import os
import time
from datetime import datetime

DB_URL = os.getenv("DB_URL")

#lista de produtos a serem monitorados
lista_produtos = [
    "iPhone 15",
    "Samsung Galaxy S24",
    "PlayStation 5 Slim",
    "Nintendo Switch OLED",
    "MacBook Air M2",
    "Acer Nitro 5",
    "AirPods Pro",
    "Echo Dot 5",
    "Kindle Paperwhite",
    "Samsung Galaxy Tab S9 FE",
    "Samsung a36 256gb"
]

import random

def buscar_menor_preco(nome_produto, scraper):
    #mudando o formato da url para tentar evitar bloqueios
    url = f"https://lista.mercadolivre.com.br/{nome_produto.replace(' ', '-')}_NoIndex_True"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }

    try:
        #usando o scraper para fazer a requisição, que já lida com Cloudflare e outros bloqueios
        response = scraper.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        #pegando o título da página para ajudar a identificar bloqueios ou redirecionamentos
        titulo_pagina = soup.title.text if soup.title else "Sem Título"
        
        #seletores mais genéricos para tentar pegar os resultados mesmo que a estrutura mude um pouco
        resultados = soup.select('.ui-search-result__wrapper') or \
                     soup.select('.poly-card') or \
                     soup.select('ol.ui-search-layout li') or \
                     soup.find_all('div', {'class': 'ui-search-result__content'})
        
        print(f"DEBUG: [{nome_produto}] Status: {response.status_code} | Título: {titulo_pagina} | Blocos: {len(resultados)}")

        #se não encontrar nada, vamos ver um pedaço do código para entender o bloqueio
        if len(resultados) == 0:
            print(f"DEBUG: Conteúdo parcial da página: {response.text[:200].strip()}")

        candidatos = []
        termos_busca = [p.lower().replace(" ", "") for p in nome_produto.split()]

        for item in resultados:
            if item.select_one('.ui-search-item__ad-label') or item.select_one('.poly-component__ad'):
                continue

            #tentativa robusta de pegar título e preço
            titulo_tag = item.select_one('h2') or item.select_one('.ui-search-item__title')
            price_tag = item.select_one('.andes-money-amount__fraction')

            if titulo_tag and price_tag:
                titulo_original = titulo_tag.text.strip().lower()
                titulo_comparacao = titulo_original.replace(" ", "").replace("-", "")
                
                if not all(p in titulo_comparacao for p in termos_busca):
                    continue

                valor_texto = price_tag.text.replace('.', '').replace(',', '')
                cents_tag = item.select_one('.andes-money-amount__cents')
                centavos = cents_tag.text if cents_tag else "00"
                
                try:
                    preco_final = float(f"{valor_texto}.{centavos}")
                    candidatos.append({"titulo": titulo_original.title(), "preco": preco_final})
                except:
                    continue

        return min(candidatos, key=lambda x: x['preco']) if candidatos else None
    except Exception as e:
        print(f"❌ Erro em {nome_produto}: {e}")
        return None

def iniciar_monitoramento():
    if not DB_URL:
        print("❌ Erro: Variável DB_URL não encontrada.")
        return
    
    #criando o scraper apenas uma vez para manter a sessão (cookies)
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},
        delay=10
    )
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    for produto in lista_produtos:
        print(f"🔍 Buscando: {produto}")
        resultado = buscar_menor_preco(produto, scraper)
        
        if resultado:
            cur.execute(
                "INSERT INTO historico_precos (produto_buscado, nome_produto_ml, preco) VALUES (%s, %s, %s)",
                (produto, resultado['titulo'], resultado['preco'])
            )
            print(f"✅ Salvo: {resultado['titulo'][:30]} - R$ {resultado['preco']}")
        
        #espera aleatória entre 8 e 15 segundos para evitar bloqueios por requisições rápidas
        tempo_espera = random.randint(8, 15)
        print(f"⏳ Aguardando {tempo_espera}s para a próxima busca...")
        time.sleep(tempo_espera)

    conn.commit()
    cur.close()
    conn.close()
    print("Monitoramento diário concluído com sucesso!")

if __name__ == "__main__":
    iniciar_monitoramento()