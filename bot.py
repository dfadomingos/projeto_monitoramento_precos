import cloudscraper
from bs4 import BeautifulSoup
import psycopg2
import os
import time
from datetime import datetime

DB_URL = os.getenv("DB_URL")

#lista de produtos a serem monitorados
lista_produtos = [
    "iPhone 15 128gb",
    "Samsung Galaxy S24 256gb",
    "PlayStation 5 Slim",
    "Nintendo Switch OLED",
    "MacBook Air M2 8gb",
    "Acer Nitro 5",
    "AirPods Pro",
    "Echo Dot 5",
    "Kindle Paperwhite",
    "Samsung Galaxy Tab S9 FE",
    "Samsung a36 8gb 256gb"
]

def buscar_menor_preco(nome_produto):
    #realiza o scraping no Mercado Livre, filtrando anúncios patrocinados
    # e retornando o menor preço encontrado para o produto específico.
    
    url = f"https://lista.mercadolivre.com.br/{nome_produto.replace(' ', '-')}"

    #cloudscraper é utilizado para contornar proteções anti-bot (cloudflare)
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        #seletores que abrangem diferentes layouts da página do Mercado Livre
        resultados = soup.select('.ui-search-result__wrapper') or soup.select('.poly-card')
        
        candidatos = []
        for item in resultados:
            #ignorando anúncios patrocinados, evitando distorção nos preços
            if item.select_one('.ui-search-item__ad-label') or item.select_one('.poly-component__ad'):
                continue

            titulo_tag = item.select_one('.poly-component__title') or item.select_one('.ui-search-item__title')
            price_tag = item.select_one('.andes-money-amount__fraction')

            if titulo_tag and price_tag:
                titulo = titulo_tag.text.strip().lower()
                #validando se o título contém todas as palavras do nome do produto, garantindo relevância
                if not all(p in titulo for p in nome_produto.lower().split()):
                    continue

                #removendo formatação de preço e convertendo para float, considerando centavos
                valor = price_tag.text.replace('.', '').replace(',', '')
                cents_tag = item.select_one('.andes-money-amount__cents')
                centavos = cents_tag.text if cents_tag else "00"
                preco_final = float(f"{valor}.{centavos}")

                candidatos.append({"titulo": titulo.title(), "preco": preco_final})

        #retorna o anúncio com o menor preço encontrado, ou None se nenhum válido for encontrado
        return min(candidatos, key=lambda x: x['preco']) if candidatos else None
    except:
        return None

def iniciar_monitoramento():
    if not DB_URL:
        print("❌ Erro: Variável DB_URL não encontrada.")
        return
    
    #conexão com o banco de dados
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    for produto in lista_produtos:
        #buscando o menor preço para cada produto da lista e salvando no banco de dados
        print(f"🔍 Buscando: {produto}")
        resultado = buscar_menor_preco(produto)
        
        if resultado:
            cur.execute(
                "INSERT INTO historico_precos (produto_buscado, nome_produto_ml, preco) VALUES (%s, %s, %s)",
                (produto, resultado['titulo'], resultado['preco'])
            )
            print(f"✅ Salvo: {resultado['titulo']} - R$ {resultado['preco']}")
        else:
            print(f"⚠️ Não foi possível encontrar um preço válido para {produto}")
            
        #pausa de 5 segundos entre as buscas para evitar bloqueios por excesso de requisições
        time.sleep(5)

    conn.commit()
    cur.close()
    conn.close()
    print("Monitoramento diário concluído com sucesso!")

if __name__ == "__main__":
    iniciar_monitoramento()