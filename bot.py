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
    #realiza a busca diretamente na API pública do Mercado Livre.
    
    #MLB = Brasil | condition=new garante que buscaremos apenas itens novos
    url = f"https://api.mercadolibre.com/sites/MLB/search?q={nome_produto.replace(' ', '%20')}&condition=new"
    
    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            print(f"⚠️ Erro na API ({response.status_code}) para: {nome_produto}")
            return None

        data = response.json()
        resultados = data.get('results', [])
        
        candidatos = []
        #criando termos de busca para validar se o título do anúncio é relevante
        termos_busca = nome_produto.lower().split()

        for item in resultados:
            titulo = item.get('title', '').lower()
            preco = item.get('price')

            #validando se o título contém todas as palavras do nome do produto, garantindo relevância
            if not all(termo in titulo for termo in termos_busca):
                continue

            #filtro básico para evitar acessórios (capas, cabos) que aparecem na busca
            if preco and preco > 100:
                candidatos.append({
                    "titulo": item.get('title'),
                    "preco": float(preco)
                })

        #retorna o anúncio com o menor preço encontrado, ou None se nenhum válido for encontrado
        if candidatos:
            return min(candidatos, key=lambda x: x['preco'])
        
        return None
    except Exception as e:
        print(f"❌ Erro técnico ao processar {nome_produto}: {e}")
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