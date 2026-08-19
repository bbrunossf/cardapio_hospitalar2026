import pandas as pd
import json
from openai import OpenAI
import time

# =================================================================
# CONFIGURAÇÕES
# =================================================================
API_KEY =  # Substitua pela sua chave da OpenAI
INPUT_FILE = "teste.xlsx"
OUTPUT_FILE = "alimentos_classificados.csv"
BATCH_SIZE = 20  # Tamanho sugerido para eficiência e segurança
MODEL = "gpt-4o-mini" # Modelo econômico e eficiente para classificação

# =================================================================
# INICIALIZAÇÃO DO CLIENTE
# =================================================================
client = OpenAI(api_key=API_KEY)

def carregar_dados():
    print(f"Lendo dados de {INPUT_FILE}...")
    
    # Lendo alimentos (A2:A280)
    # skiprows=1 pula a linha 1 (cabeçalho). usecols="A" pega apenas a primeira coluna.
    df_alimentos = pd.read_excel(INPUT_FILE, sheet_name='alimentos', header=None, skiprows=1, usecols="A")
    lista_alimentos = df_alimentos[0].dropna().tolist()
    
    # Lendo classificações (A2:A15)
    df_class = pd.read_excel(INPUT_FILE, sheet_name='class', header=None, skiprows=1, usecols="A")
    lista_classificacoes = df_class[0].dropna().tolist()
    
    # Remove eventuais cabeçalhos se o pandas leu a linha 2 como dados
    # (Caso o usuário tenha cabeçalho na linha 1 e dados a partir da 2)
    return lista_alimentos, lista_classificacoes

def classificar_lote(alimentos, categorias):
    prompt = f"""
    Você é um especialista em nutrição. 
    Sua tarefa é associar cada alimento da lista abaixo a exatamente UMA das categorias fornecidas.
    
    Categorias permitidas:
    {', '.join(categorias)}
    
    Alimentos para classificar:
    {', '.join(alimentos)}
    
    Retorne o resultado estritamente no formato JSON, sendo uma lista de objetos com as chaves "alimento" e "classificacao".
    Exemplo: [{{"alimento": "Maçã", "classificacao": "Frutas"}}]
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Você é um assistente útil que retorna apenas JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        conteudo = response.choices[0].message.content
        dados = json.loads(conteudo)
        
        # O modelo pode retornar o JSON com uma chave raiz (ex: {"alimentos": [...]})
        # ou diretamente a lista. Vamos extrair a lista de objetos.
        if isinstance(dados, list):
            return dados
        elif isinstance(dados, dict):
            for valor in dados.values():
                if isinstance(valor, list) and len(valor) > 0 and isinstance(valor[0], dict):
                    return valor
            if "alimento" in dados:
                return [dados]
        return []
    except Exception as e:
        print(f"Erro ao processar lote: {e}")
        return []

def main():
    try:
        alimentos, categorias = carregar_dados()
    except Exception as e:
        print(f"Erro ao ler o arquivo Excel: {e}")
        return

    print(f"Total de alimentos carregados: {len(alimentos)}")
    print(f"Categorias carregadas: {len(categorias)}")
    
    resultados_finais = []
    
    # Processamento em lotes para maior eficiência e controle de tokens
    for i in range(0, len(alimentos), BATCH_SIZE):
        lote = alimentos[i:i + BATCH_SIZE]
        print(f"Processando lote {i//BATCH_SIZE + 1} de {(len(alimentos)-1)//BATCH_SIZE + 1}...")
        
        resultado_lote = classificar_lote(lote, categorias)
        resultados_finais.extend(resultado_lote)
        
        # Pequena pausa para respeitar limites de taxa da API
        time.sleep(0.5)
    
    # Salvar resultados em CSV
    if resultados_finais:
        df_resultado = pd.DataFrame(resultados_finais)
        # utf-8-sig garante que o Excel abra o CSV corretamente com acentuação
        df_resultado.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"\nProcesso concluído com sucesso!")
        print(f"Resultado salvo em: {OUTPUT_FILE}")
    else:
        print("\nNenhum resultado foi gerado. Verifique sua chave de API e conexão.")

if __name__ == "__main__":
    main()
