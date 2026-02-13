import cloudscraper  
import psycopg2
import os
import time
from datetime import datetime
from bs4 import BeautifulSoup

DB_URL = os.getenv("DB_URL")

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

def buscar_menor_preco(nome_produto):
    #url da API do Mercado Livre com o nome do produto
    url = f"https://lista.mercadolivre.com.br/{nome_produto.replace(' ', '-')}_Condicion_Nuevo_NoIndex_True"
    
    #configura o scraper para agir como um Chrome no Desktop
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    try:
        response = scraper.get(url)
        
        #se cair no desafio do Cloudflare, o scraper resolve sozinho.
        #se passar direto, processamos o HTML.
        soup = BeautifulSoup(response.text, 'html.parser')
        
        #seletores genéricos que funcionam em Desktop e Mobile
        resultados = soup.select('.ui-search-result__wrapper') or \
                     soup.select('.poly-card') or \
                     soup.select('.ui-search-layout__item')

        candidatos = []
        termos_busca = nome_produto.lower().split()

        for item in resultados:
            #ignora patrocinados
            if item.select_one('.ui-search-item__ad-label') or item.select_one('.poly-component__ad'):
                continue

            #busca Título
            titulo_tag = item.select_one('.poly-component__title') or \
                         item.select_one('.ui-search-item__title') or \
                         item.find('h2')
            
            #busca Preço
            price_tag = item.select_one('.andes-money-amount__fraction')

            if titulo_tag and price_tag:
                titulo = titulo_tag.text.strip().lower()
                
                #validação de nome (segurança)
                if not all(termo in titulo for termo in termos_busca):
                    continue

                #limpeza do preço
                valor_texto = price_tag.text.replace('.', '').replace(',', '')
                try:
                    preco_final = float(valor_texto)
                except:
                    continue
                
                #filtro de preço mínimo (evita acessórios)
                if preco_final > 100:
                    candidatos.append({
                        "titulo": titulo.title(),
                        "preco": preco_final
                    })

        if candidatos:
            return min(candidatos, key=lambda x: x['preco'])
        
        return None

    except Exception as e:
        print(f"❌ Erro técnico: {e}")
        return None

def iniciar_monitoramento():
    if not DB_URL:
        print("❌ Erro: DB_URL não configurada.")
        return
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        print(f"🚀 Monitoramento (Web Scraping Seguro): {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        for produto in lista_produtos:
            print(f"🔍 Buscando: {produto}")
            resultado = buscar_menor_preco(produto)
            
            if resultado:
                cur.execute(
                    "INSERT INTO historico_precos (produto_buscado, nome_produto_ml, preco) VALUES (%s, %s, %s)",
                    (produto, resultado['titulo'], resultado['preco'])
                )
                print(f"✅ R$ {resultado['preco']} | {resultado['titulo'][:30]}...")
            else:
                print(f"⚠️ Não encontrado (possível bloqueio ou sem estoque).")
            
            time.sleep(3) 

        conn.commit()
        cur.close()
        conn.close()
        print("\n✨ Processo Finalizado!")
        
    except Exception as e:
        print(f"❌ Erro Geral: {e}")

if __name__ == "__main__":
    iniciar_monitoramento()