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
        resultados = soup.select('.ui-search-result__wrapper') or soup.select('.poly-card') or \
                soup.select('.ui-search-item__group')
        
        candidatos = []
        for item in resultados:
            #ignorando anúncios patrocinados, evitando distorção nos preços
            if item.select_one('.ui-search-item__ad-label') or item.select_one('.poly-component__ad'):
                continue

            titulo_tag = item.select_one('.poly-component__title') or item.select_one('.ui-search-item__title') or item.find('h2')
            price_tag = item.select_one('.andes-money-amount__fraction')

            if titulo_tag and price_tag:
                titulo = titulo_tag.text.strip().lower()
                
                #Removendo espaços para comparar "256gb" com "256 gb" corretamente
                titulo_normalizado = titulo.replace(" ", "")
                termos_busca = [p.lower().replace(" ", "") for p in nome_produto.split()]
                
                #validando se o título contém todas as palavras do nome do produto, garantindo relevância
                if not all(p in titulo_normalizado for p in termos_busca):
                    continue
                
                #filtro de acessórios 
                acessorios = ['capa', 'case', 'pelicula', 'suporte', 'carregador']
                if any(acc in titulo for acc in acessorios) and 'capa' not in nome_produto.lower():
                    continue

                #removendo formatação de preço e convertendo para float, considerando centavos
                valor = price_tag.text.replace('.', '').replace(',', '')
                cents_tag = item.select_one('.andes-money-amount__cents')
                centavos = cents_tag.text if cents_tag else "00"
                preco_final = float(f"{valor}.{centavos}")

                #trava de segurança de preço
                #evita que peças ou golpes entrem na média (Ex: iPhone por R$ 100)
                if ("iphone" in titulo or "samsung" in titulo) and preco_final < 400:
                    continue

                candidatos.append({"titulo": titulo.title(), "preco": preco_final})

        #retorna o anúncio com o menor preço encontrado, ou None se nenhum válido for encontrado
        return min(candidatos, key=lambda x: x['preco']) if candidatos else None
    except Exception as e:
        print(f"Erro técnico ao processar {nome_produto}: {e}")
        return None

def iniciar_monitoramento():
    if not DB_URL:
        print("❌ Erro: Variável DB_URL não encontrada.")
        return
    
    #conexão com o banco de dados
    try:
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
                print(f"✅ Salvo: {resultado['titulo'][:40]}... - R$ {resultado['preco']}")
            else:
                print(f"⚠️ Não foi possível encontrar um preço válido para {produto}")

            #pausa de 5 segundos entre as buscas para evitar bloqueios por excesso de requisições
            time.sleep(5)

        conn.commit()
        cur.close()
        conn.close()
        print("Monitoramento diário concluído com sucesso!")
    except Exception as e:
        print(f"❌ Erro na conexão com o banco: {e}")

if __name__ == "__main__":
    iniciar_monitoramento()