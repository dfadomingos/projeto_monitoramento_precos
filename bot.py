import requests
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

def buscar_menor_preco_api(nome_produto):
    url = f"https://api.mercadolibre.com/sites/MLB/search?q={nome_produto.replace(' ', '%20')}&condition=new"
    
    #definindo headers para simular um navegador e evitar bloqueios da API
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        #fazendo a requisição para a API do Mercado Livre
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            print(f"⚠️ Erro API ({response.status_code})")
            return None

        data = response.json()
        resultados = data.get('results', [])

        candidatos = []
        termos_busca = nome_produto.lower().split()

        for item in resultados:
            titulo = item.get('title', '').lower()
            preco = item.get('price')
            
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
        print("❌ Erro: Variável DB_URL não encontrada.")
        return
    
    #conexão com o banco de dados
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        print(f"🚀 Iniciando monitoramento via API: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        for produto in lista_produtos:
            #buscando o menor preço para cada produto da lista e salvando no banco de dados
            print(f"🔍 Analisando: {produto}")
            resultado = buscar_menor_preco_api(produto)
            
            if resultado:
                cur.execute(
                    "INSERT INTO historico_precos (produto_buscado, nome_produto_ml, preco) VALUES (%s, %s, %s)",
                    (produto, resultado['titulo'], resultado['preco'])
                )
                print(f"✅ Sucesso: R$ {resultado['preco']} | {resultado['titulo'][:40]}...")
            else:
                print(f"⚠️ Nenhum resultado válido encontrado para: {produto}")

            time.sleep(1)

        conn.commit()
        cur.close()
        conn.close()
        print("\n✨ Monitoramento concluído e dados salvos no Neon!")
        
    except Exception as e:
        print(f"❌ Erro na conexão ou banco: {e}")

if __name__ == "__main__":
    iniciar_monitoramento()