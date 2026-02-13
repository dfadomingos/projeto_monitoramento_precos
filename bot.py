import cloudscraper  
import psycopg2
import os
import time
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv 
from tqdm import tqdm 

load_dotenv()
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

def buscar_menor_preco(scraper, nome_produto):
    #url da API do Mercado Livre com o nome do produto
    url = f"https://lista.mercadolivre.com.br/{nome_produto.replace(' ', '-')}_Condicion_Nuevo_NoIndex_True_OrderId_price_asc"
    
    
    try:
        response = scraper.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        #seletores em ordem de prioridade (Desktop > Mobile > Genérico)
        cards = soup.select('.ui-search-result__wrapper') or \
                soup.select('.poly-card') or \
                soup.select('li.ui-search-layout__item')

        candidatos = []
        termos_busca = [t.lower() for t in nome_produto.split()]

        for card in cards:
            #ignora anuncios patrocinados
            if card.select_one('.ui-search-item__ad-label') or card.select_one('.poly-component__ad'):
                continue

            #extração de Título
            titulo_tag = card.select_one('.poly-component__title') or \
                         card.select_one('.ui-search-item__title') or \
                         card.find('h2')
            
            #extração de Preço
            preco_tag = card.select_one('.andes-money-amount__fraction')

            if titulo_tag and preco_tag:
                titulo = titulo_tag.text.strip().lower()
                
                #normalização para comparação (remove espaços extras)
                titulo_clean = titulo.replace(" ", "")
                termos_clean = [t.replace(" ", "") for t in termos_busca]
                
                #verifica se todos os termos de busca estão presentes no título 
                if not all(termo in titulo_clean for termo in termos_clean):
                    continue
                
                #filtro para evitar acessórios indesejados
                if any(x in titulo for x in ['capa', 'case', 'pelicula', 'vidro', 'suporte']):
                    continue

                #conversão do preço para float 
                try:
                    valor = float(preco_tag.text.replace('.', '').replace(',', ''))
                    #filtro para evitar preços muito baixos (acessórios ou erros de scraping)
                    if valor > 100:
                        candidatos.append({'titulo': titulo.title(), 'preco': valor})
                except ValueError:
                    continue

        if candidatos:
            #retorna o item com menor preço da lista filtrada
            return min(candidatos, key=lambda x: x['preco'])
        
        return None

    except Exception as e:
        #retorna o erro para logar, mas não para o script
        return {"erro": str(e)}

def executar_monitoramento():
    print(f"\n🚀 INICIANDO MONITORAMENTO LOCAL: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("-" * 60)

    if not DB_URL:
        print("❌ ERRO CRÍTICO: Arquivo .env não encontrado ou DB_URL vazia.")
        return

    #inicializa o Scraper (Simulando Chrome Desktop)
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        sucessos = 0
        falhas = 0

        #loop com barra de progresso (tqdm)
        with tqdm(total=len(lista_produtos), desc="🔍 Coletando dados", unit="prod") as barra:
            for produto in lista_produtos:
                resultado = buscar_menor_preco(scraper, produto)
                
                if resultado and "titulo" in resultado:
                    cursor.execute(
                        "INSERT INTO historico_precos (produto_buscado, nome_produto_ml, preco) VALUES (%s, %s, %s)",
                        (produto, resultado['titulo'], resultado['preco'])
                    )
                    barra.write(f"✅ {produto}: R$ {resultado['preco']:,.2f}") 
                    sucessos += 1
                elif resultado and "erro" in resultado:
                    barra.write(f"❌ Erro em {produto}: {resultado['erro']}")
                    falhas += 1
                else:
                    barra.write(f"⚠️ {produto}: Nenhum preço válido encontrado.")
                    falhas += 1
                
                #atualiza a barra de progresso
                barra.update(1)
                
                # 
                time.sleep(2)  #delay para evitar bloqueios

        conn.commit()
        cursor.close()
        conn.close()
        
        print("-" * 60)
        print(f"🏁 FIM DO PROCESSO via Neon Cloud")
        print(f"📊 Sucessos: {sucessos} | Falhas: {falhas}")
        print("-" * 60)

    except Exception as e:
        print(f"❌ Erro fatal de conexão: {e}")

if __name__ == "__main__":
    executar_monitoramento()