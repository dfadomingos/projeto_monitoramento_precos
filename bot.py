import cloudscraper
import psycopg2
import os
import time
from datetime import datetime

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

def buscar_menor_preco_api(nome_produto):
    #url da API do Mercado Livre com o nome do produto
    url = f"https://api.mercadolibre.com/sites/MLB/search?q={nome_produto.replace(' ', '%20')}&condition=new"
    
    #criando o scraper para contornar o bloqueio 403 da Cloudflare
    scraper = cloudscraper.create_scraper()
    
    try:
        #usando o scraper para fazer a requisição GET à API
        response = scraper.get(url, timeout=20)
        
        if response.status_code != 200:
            print(f"⚠️ Bloqueio ou Erro API ({response.status_code})")
            return None

        #cloudscraper retorna um objeto compatível, então .json() funciona igual
        data = response.json()
        resultados = data.get('results', [])

        candidatos = []
        termos_busca = nome_produto.lower().split()

        for item in resultados:
            titulo = item.get('title', '').lower()
            preco = item.get('price')
            
            #validação de segurança
            if not all(termo in titulo for termo in termos_busca):
                continue

            if preco and preco > 100:
                candidatos.append({
                    "titulo": item.get('title'),
                    "preco": float(preco)
                })

        if candidatos:
            return min(candidatos, key=lambda x: x['preco'])
        
        return None

    except Exception as e:
        print(f"❌ Erro técnico: {e}")
        return None

def iniciar_monitoramento():
    if not DB_URL:
        print("❌ Erro: DB_URL não encontrada.")
        return
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        print(f"🚀 Monitoramento API + Bypass: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        for produto in lista_produtos:
            print(f"🔍 Buscando: {produto}")
            resultado = buscar_menor_preco_api(produto)
            
            if resultado:
                cur.execute(
                    "INSERT INTO historico_precos (produto_buscado, nome_produto_ml, preco) VALUES (%s, %s, %s)",
                    (produto, resultado['titulo'], resultado['preco'])
                )
                print(f"✅ R$ {resultado['preco']} | {resultado['titulo'][:30]}...")
            else:
                print(f"⚠️ Sem resultados válidos.")
            
            time.sleep(2) 

        conn.commit()
        cur.close()
        conn.close()
        print("\n✨ Processo Finalizado!")
        
    except Exception as e:
        print(f"❌ Erro Geral: {e}")

if __name__ == "__main__":
    iniciar_monitoramento()