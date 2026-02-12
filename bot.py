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
    url = f"https://lista.mercadolivre.com.br/{nome_produto.replace(' ', '-')}"
    scraper = cloudscraper.create_scraper()
    
    try:
        response = scraper.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- DEBUG: Verificando se a página foi carregada ---
        resultados = soup.select('.ui-search-result__wrapper') or \
                     soup.select('.poly-card') or \
                     soup.select('.ui-search-item__group') or \
                     soup.select('.ui-search-result')
        
        print(f"DEBUG: [{nome_produto}] Encontrei {len(resultados)} blocos de produtos.")

        candidatos = []
        termos_busca = [p.lower().replace(" ", "") for p in nome_produto.split()]

        for item in resultados:
            # Filtro de anúncios (patrocinados)
            if item.select_one('.ui-search-item__ad-label') or item.select_one('.poly-component__ad'):
                continue

            # Tenta múltiplos seletores para o título e preço
            titulo_tag = item.select_one('.poly-component__title') or \
                         item.select_one('.ui-search-item__title') or \
                         item.select_one('.ui-search-item__group h2') or \
                         item.find('h2')
            
            price_tag = item.select_one('.andes-money-amount__fraction')

            if titulo_tag and price_tag:
                titulo_original = titulo_tag.text.strip().lower()
                titulo_comparacao = titulo_original.replace(" ", "").replace("-", "")
                
                # Validação de nome
                if not all(p in titulo_comparacao for p in termos_busca):
                    continue

                # Extração de preço com limpeza profunda
                # Removemos pontos de milhar para não confundir o float
                valor_texto = price_tag.text.replace('.', '').replace(',', '')
                cents_tag = item.select_one('.andes-money-amount__cents')
                centavos = cents_tag.text if cents_tag else "00"
                
                try:
                    preco_final = float(f"{valor_texto}.{centavos}")
                except ValueError:
                    continue

                # Filtro de acessórios (evita lixo no banco)
                if any(acc in titulo_original for acc in ['capa', 'case', 'pelicula', 'carregador']):
                    continue

                candidatos.append({"titulo": titulo_original.title(), "preco": preco_final})

        if candidatos:
            vencedor = min(candidatos, key=lambda x: x['preco'])
            return vencedor
            
        return None
    except Exception as e:
        print(f"❌ Erro ao processar {nome_produto}: {e}")
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