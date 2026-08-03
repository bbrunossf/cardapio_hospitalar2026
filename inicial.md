# Sistema de Planejamento Nutricional Inteligente

## Visão Geral do Produto

O projeto consiste em uma plataforma voltada inicialmente para **nutrição hospitalar**, com potencial para evoluir para clínicas, restaurantes industriais e uso doméstico.

O objetivo principal é auxiliar nutricionistas e gestores na elaboração de cardápios, redução de desperdícios, otimização de custos e acompanhamento nutricional utilizando Inteligência Artificial, Pesquisa Operacional, Ciência de Dados e Visão Computacional.

A arquitetura foi pensada para ser altamente modular, permitindo substituir provedores de IA, modelos de otimização e bancos de dados sem alterar o restante da aplicação.

---

# Objetivos

* Automatizar atividades repetitivas dos nutricionistas.
* Reduzir desperdício alimentar.
* Diminuir custos das refeições.
* Melhorar a qualidade nutricional.
* Apoiar decisões baseadas em dados.
* Permitir personalização para diferentes instituições.
* Servir como laboratório de estudos em IA aplicada à Nutrição.

---

# Público-alvo

## Inicial

* Hospitais
* Clínicas
* Empresas de alimentação coletiva

## Futuro

* Nutricionistas autônomos
* Academias
* Personal trainers
* Usuários domésticos

---

# Arquitetura Geral

O sistema deverá ser dividido em módulos independentes.

```
             Usuário
                │
         Interface Streamlit
                │
        ---------------------
        │         │
        │         │
Banco SQL    Camada de Serviços
                  │
      -------------------------
      │      │      │
      IA   Solver   Analytics
      │      │      │
 GPT / Gemini /     Power BI
 LogMeal / etc.
```

---

# Funcionalidades previstas

---

## 1. Cadastro de alimentos

Cadastro completo contendo:

* composição nutricional
* grupo alimentar
* custo
* fornecedor
* sazonalidade
* embalagem
* rendimento
* fator de cocção
* fator de correção
* peso bruto
* peso líquido

Fontes possíveis:

* TACO
* IBGE
* USDA
* Open Food Facts
* alimentos próprios do hospital

---

## 2. Cadastro por fotografia

O usuário fotografa:

* embalagem
* tabela nutricional
* ingredientes

A IA realiza:

* OCR
* identificação do alimento
* preenchimento automático
* sugestão de categoria
* extração dos nutrientes

---

## 3. Reconhecimento de alimentos

Utilizando visão computacional.

Entrada:

* fotografia da bandeja

Saída:

* alimentos identificados
* quantidade aproximada
* peso estimado
* nutrientes estimados

Camada de abstração:

```
FoodRecognitionProvider
    GPT
    Gemini
    LogMeal
    Outros
```

Assim o modelo pode ser trocado sem alterar o restante do sistema.

---

## 4. Gerador automático de cardápios

Restrições possíveis:

* calorias
* proteínas
* carboidratos
* lipídios
* fibras
* sódio
* micronutrientes
* variedade
* sazonalidade
* disponibilidade
* custo
* estoque

Otimização utilizando:

* Programação Linear
* Programação Inteira (PuLP/CBC)
* heurísticas futuras

---

## 5. Simulação de cenários

Exemplos:

* reduzir custo em 10%
* aumentar proteínas
* substituir fornecedor
* trocar ingrediente
* eliminar alimento indisponível

---

## 6. Controle de estoque

Integração com ERP.

Capaz de:

* identificar excesso
* identificar falta
* sugerir substituições
* prever compras

---

## 7. Gestão de fornecedores

Cadastro de:

* preço histórico
* prazo
* qualidade
* sazonalidade
* disponibilidade

---

## 8. Substituição inteligente de alimentos

Utilizando embeddings.

Critérios:

* nutrientes
* sabor
* textura
* grupo alimentar
* custo
* aceitação

---

## 9. Planejamento semanal

Gerar automaticamente:

* café
* almoço
* jantar
* lanches

Minimizando repetição.

---

## 10. Controle de desperdício

Registro de:

* sobra limpa
* sobra suja
* resto ingestão

Dashboards mostrando:

* desperdício por setor
* desperdício por alimento
* desperdício por fornecedor

---

## 11. Indicadores

Exemplos:

* custo por refeição
* desperdício
* aceitação
* consumo médio
* índice de variedade
* índice nutricional
* utilização do estoque

---

## 12. Dashboard analítico

Power BI ou Streamlit.

Visualizações:

* evolução do desperdício
* evolução do custo
* consumo de nutrientes
* comparação entre setores
* sazonalidade

---

## 13. IA conversacional

Exemplos:

> Gere um cardápio com menos sódio.

> Quais alimentos posso substituir?

> Por que esse cardápio ficou caro?

> Como reduzir desperdício?

---

## 14. Explicabilidade

A IA deverá explicar:

* por que escolheu determinado alimento
* quais restrições estavam ativas
* quais foram relaxadas
* custo da decisão

---

## 15. Perfil dos pacientes

Cadastro de:

* patologias
* alergias
* preferências
* restrições religiosas
* textura
* consistência
* metas nutricionais

---

## 16. Histórico

Guardar todas as versões de:

* cardápios
* otimizações
* alterações
* decisões

---

## 17. Sistema de preferências

Aprender automaticamente:

* alimentos rejeitados
* alimentos aceitos
* padrões de consumo

---

## 18. API

Disponibilizar:

* consulta nutricional
* geração de cardápios
* cálculo nutricional
* otimização

---

# Funcionalidades sugeridas

## Gêmeo Digital da Produção

Simular virtualmente toda a operação da cozinha antes da execução:

* consumo de estoque
* tempo de preparo
* ocupação dos equipamentos
* filas
* gargalos
* custo previsto
* desperdício esperado

Isso permitiria testar mudanças de cardápio sem impacto operacional.

---

## Motor de Regras

Separar regras nutricionais do código.

Exemplo:

```
SE
Paciente = Diabético

ENTÃO

Açúcar <= X
```

Novas regras seriam adicionadas sem alterar o software.

---

## Banco de Conhecimento

Uma base RAG contendo:

* manuais
* POPs
* legislação
* protocolos clínicos
* receitas
* documentos internos

A IA responderia considerando apenas documentos aprovados.

---

## Predição de Aceitação

Modelo treinado utilizando histórico para prever:

* quais pratos terão maior aceitação
* quais gerarão maior desperdício

---

## Simulação Financeira

Antes de aprovar um cardápio:

```
Custo mensal

Impacto anual

Economia prevista

Comparação com histórico
```

---

## Marketplace de Receitas

Receitas reutilizáveis.

Cada receita teria:

* versão
* avaliações
* custo
* nutrientes
* tempo

---

## Otimização Multiobjetivo

Hoje o solver pode otimizar um objetivo principal (por exemplo, custo). Um avanço importante seria permitir otimização simultânea considerando:

* custo
* desperdício
* aceitação
* valor nutricional
* variedade

Com pesos configuráveis ou fronteiras de Pareto.

---

## Simulador de Eventos

Responder perguntas do tipo:

* "E se o fornecedor X atrasar?"
* "E se o preço do arroz subir 30%?"
* "E se dobrar o número de pacientes?"

Isso aumenta o valor do sistema para planejamento estratégico.

---

## Detecção de Anomalias

Aplicar modelos para identificar automaticamente:

* desperdício acima do esperado
* consumo fora do padrão
* compras incompatíveis com o histórico
* possíveis erros de cadastro ou lançamento.

---

## Aprendizado com Feedback Humano (Human-in-the-Loop)

Permitir que nutricionistas aprovem, rejeitem ou ajustem sugestões da IA. Esse feedback alimentaria um mecanismo de aprendizado para melhorar recomendações futuras, sem depender necessariamente de reentreinamento completo do modelo.

---

## Assistente para Desenvolvimento de Novas Dietas

A partir de objetivos clínicos e restrições, sugerir novas combinações de preparações, destacando possíveis conflitos nutricionais, impacto de custos e diferenças em relação às dietas já existentes.

---

# Agentes CrewAI

## 1. Product Owner Agent

Responsável por:

* organizar backlog
* escrever histórias
* definir prioridades
* quebrar tarefas

---

## 2. Software Architect Agent

Define:

* arquitetura
* padrões
* interfaces
* contratos

---

## 3. Backend Agent

Desenvolve:

* APIs
* serviços
* autenticação
* banco de dados

---

## 4. Frontend Agent

Responsável por:

* Streamlit
* UX
* dashboards

---

## 5. Database Agent

Cria:

* schema
* índices
* migrações
* otimizações SQL

---

## 6. Optimization Agent

Especialista em:

* PuLP
* CBC
* OR-Tools
* Pesquisa Operacional

Responsável por:

* modelagem matemática
* restrições
* funções objetivo

---

## 7. Computer Vision Agent

Integra:

* GPT Vision
* Gemini Vision
* LogMeal
* OCR

Também avalia novos provedores.

---

## 8. AI Integration Agent

Mantém a camada de abstração:

```
FoodRecognitionProvider

LLMProvider

EmbeddingProvider
```

Permitindo trocar fornecedores de IA sem alterar o restante da aplicação.

---

## 9. Data Engineering Agent

Responsável por:

* ETL
* ingestão
* limpeza
* atualização das bases nutricionais

---

## 10. Data Science Agent

Desenvolve modelos de:

* previsão
* classificação
* aceitação
* desperdício

---

## 11. Prompt Engineer Agent

Produz:

* prompts
* testes
* avaliação
* versionamento

---

## 12. QA Agent

Executa:

* testes unitários
* integração
* regressão
* validação das respostas da IA

---

## 13. Documentation Agent

Mantém automaticamente:

* Wiki
* documentação técnica
* diagramas
* changelog
* ADRs (Architecture Decision Records)

---

## 14. DevOps Agent

Gerencia:

* Docker
* CI/CD
* deploy
* monitoramento
* backups

---

## 15. Security & Compliance Agent

Verifica:

* LGPD
* controle de acesso
* criptografia
* auditoria
* gestão de segredos

---

## 16. Research Agent

Monitora continuamente:

* novas APIs de visão computacional
* modelos LLM
* artigos científicos em nutrição e otimização
* bases públicas de alimentos
* alterações na legislação aplicável

---

# Fluxo sugerido entre os agentes

```text
                 Product Owner
                        │
                        ▼
              Software Architect
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
 Database        Backend Agent     Frontend Agent
        │               │                │
        └───────────────┼────────────────┘
                        ▼
               AI Integration Agent
          ┌─────────────┼───────────────┐
          ▼             ▼               ▼
 Optimization   Computer Vision   Data Engineering
          │             │               │
          └─────────────┼───────────────┘
                        ▼
                 Data Science Agent
                        │
                        ▼
                    QA Agent
                        │
                        ▼
             Documentation Agent
                        │
                        ▼
                  DevOps Agent
                        │
                        ▼
          Security & Compliance Agent
```

## Observação estratégica

Pelas discussões anteriores, o projeto já possui características que vão além de um simples gerador de cardápios. A combinação de otimização matemática, visão computacional, aprendizado de máquina, integração com ERPs e explicabilidade aproxima a solução de uma plataforma de **Decision Intelligence** para serviços de alimentação. Essa visão mais ampla pode orientar a arquitetura desde o início, favorecendo módulos desacoplados, interfaces bem definidas (como `FoodRecognitionProvider`, `EmbeddingProvider` e `OptimizationProvider`) e facilitando a evolução para novos domínios, como clínicas, restaurantes corporativos e uso pessoal.
