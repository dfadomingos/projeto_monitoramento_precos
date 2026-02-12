import cloudscraper
from bs4 import BeautifulSoup
import psycopg2
import os
import time
from datetime import datetime
import random

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

def buscar_menor_preco(nome_produto, scraper):
    #mudando para a URL mobile, que é mais leve e menos protegida por JS
    #adicionando filtros de 'apenas novos' e 'menor preço' direto na URL
    url = f"https://lista.mercadolivre.com.br/{nome_produto.replace(' ', '-')}_ItemTypeID_N_OrderId_price_asc"
    
    #definindo um user-agent mais simples, simulando um navegador mobile, para evitar bloqueios
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9',
        'Connection': 'keep-alive',
    }

    try:
        response = scraper.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        #se o título continuar vazio, tenta pegar de um meta tag ou h1
        titulo_detectado = soup.find('title').text.strip() if soup.find('title') else "Sem Título"
        
        #seletores de classe simplificados
        resultados = soup.select('.ui-search-result__wrapper') or \
                     soup.select('.poly-card') or \
                     soup.select('.ui-search-item') or \
                     soup.find_all('div', class_=lambda x: x and 'result' in x)
        
        print(f"DEBUG: [{nome_produto}] Título: {titulo_detectado} | Itens: {len(resultados)}")

        candidatos = []
        termos_busca = [p.lower().replace(" ", "") for p in nome_produto.split()]

        for item in resultados:
            #ignora patrocinados
            if "patrocinado" in item.text.lower() or item.select_one('.ui-search-item__ad-label'):
                continue

            #busca título e preço usando seletores mais genéricos
            titulo_tag = item.find('h2') or item.select_one('.ui-search-item__title')
            price_tag = item.select_one('.andes-money-amount__fraction')

            if titulo_tag and price_tag:
                titulo_original = titulo_tag.text.strip().lower()
                titulo_comparacao = titulo_original.replace(" ", "").replace("-", "")
                
                #validação de termos
                if not all(p in titulo_comparacao for p in termos_busca):
                    continue

                valor_texto = price_tag.text.replace('.', '').replace(',', '')
                cents_tag = item.select_one('.andes-money-amount__cents')
                centavos = cents_tag.text if cents_tag else "00"
                
                try:
                    preco_final = float(f"{valor_texto}.{centavos}")
                    #filtro de preço para evitar acessórios
                    if preco_final > 100: 
                        candidatos.append({"titulo": titulo_original.title(), "preco": preco_final})
                except:
                    continue

        return min(candidatos, key=lambda x: x['preco']) if candidatos else None
    except Exception as e:
        print(f"❌ Erro: {e}")
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