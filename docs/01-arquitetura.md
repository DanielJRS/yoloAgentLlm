# Fase 1 - Analise de Arquitetura

## Frontend (`templates/` + `static/`)

O frontend esta majoritariamente na responsabilidade correta: exibe dados vindos do backend e envia mensagens do chat.

Achados positivos:

- `templates/index.html:19-50` define apenas a estrutura visual do dashboard: camera, eventos e chat.
- `static/dashboard.js:45-66` busca `/camera/status` e `/agent/status` e apenas atualiza badges, metricas e lista de eventos.
- `static/dashboard.js:77-99` faz validacao simples de UX (`trim`, mensagem vazia) e envia o payload para `/chat`; a regra principal permanece no backend.

Achados negativos:

- `static/dashboard.js:35-39` usa `innerHTML` para montar metadados do evento. Hoje os dados vêm do backend/YOLO, mas `label` e `event_time` ainda sao conteudo dinamico. Isso cria uma superficie desnecessaria de XSS caso algum dado externo ou manipulado chegue ao banco.
- `static/dashboard.js:94` exibe `e.message` vindo de falhas do `fetch`. Nao e grave, mas pode mostrar detalhes tecnicos ao operador.

Conclusao: o frontend nao contem regra de negocio relevante; ele e uma camada de apresentacao, com pequena melhoria recomendada para renderizacao segura.

## Backend/API (`app.py`)

O backend concentra a orquestracao HTTP e delega boa parte da logica aos servicos.

Achados positivos:

- `app.py:18-27` usa lifespan para inicializar banco, iniciar monitoramento e fechar recursos.
- `app.py:46-53` delega status da camera ao `monitor` e listagem de eventos ao repositorio.
- `app.py:84-95` delega status/chat ao `MonitoringAgent`.

Achados negativos:

- `app.py:64-81` contem a logica do streaming multipart diretamente na rota. Nao e um problema critico, mas deixa a rota mais "gorda" que as demais.
- `app.py:89-95` valida mensagem vazia, mas nao aplica nenhuma politica adicional de seguranca/abuso alem do limite Pydantic em `services/schemas.py:29-30`.
- Nao ha configuracao explicita de CORS, headers de seguranca ou autenticacao em `app.py`.

Conclusao: controllers estao relativamente magros, com excecao do gerador de streaming e ausencia de camada transversal de seguranca.

## Banco/Persistencia

O acesso ao SQLite esta bem isolado em um repositorio dedicado.

Achados positivos:

- `services/event_repository.py:30-38` centraliza conexao SQLite e `row_factory`.
- `services/event_repository.py:41-64` concentra schema, insert e select da tabela `events`.
- `services/event_repository.py:49-52` e `services/event_repository.py:59-62` usam parametros vinculados (`?`), reduzindo risco de injecao SQL.

Achados negativos:

- O schema vive como string global em `services/event_repository.py:19-27`, suficiente para a escala atual, mas tende a crescer quando novas tabelas forem adicionadas.
- A nova tabela de clima nao deve ser colocada de forma espalhada em outros modulos; precisa seguir o padrao de repositorio.

Conclusao: persistencia esta bem isolada para eventos; a evolucao natural e manter esse mesmo limite para snapshots externos.

## Camada de IA (YOLO + agente)

YOLO e LLM estao em modulos separados, mas o monitor mistura captura, inferencia, filtro e persistencia.

Achados positivos:

- `services/video_monitor.py:31-40` encapsula carregamento do YOLO e inicializacao do loop.
- `services/video_monitor.py:109-135` concentra inferencia e persistencia de eventos detectados.
- `services/monitoring_agent.py:10-23` deixa identidade e regras do agente explicitas.
- `services/monitoring_agent.py:65-83` isola memoria curta, contexto e chamada ao LLM.
- `services/ollama_client.py:14-48` separa cliente HTTP do Ollama da regra conversacional.

Achados negativos:

- `services/video_monitor.py:103-135` conhece muitos detalhes: JPEG live, chamada YOLO, classes alvo, cooldown, salvamento de captura e gravacao no banco. Isso e aceitavel para MVP, mas e o maior ponto de acoplamento interno.
- `services/monitoring_agent.py:33-43` monta o contexto de eventos dentro de metodo privado. Para integrar clima/scraping, e melhor expor um metodo de construcao de contexto que inclua novas fontes sem duplicar prompt.
- `services/monitoring_agent.py:69` injeta a mensagem do usuario diretamente na conversa do LLM; as regras reduzem alucinacao, mas nao ha delimitacao contra prompt injection.

Conclusao: ha separacao boa entre Ollama e agente, mas o contexto do agente deve ser preparado para receber dados externos de forma controlada.

## Integracoes externas (Ollama, camera/RTSP)

As integracoes existem, mas com niveis diferentes de abstracao.

Achados positivos:

- `services/ollama_client.py:16` define timeout no cliente HTTP.
- `services/ollama_client.py:21-27` tem checagem de disponibilidade do Ollama com tratamento de erro.
- `services/video_monitor.py:70-81` encapsula abertura da camera/stream.
- `services/video_monitor.py:83-98` tenta reconectar quando a camera falha.

Achados negativos:

- `services/ollama_client.py:36-41` tem tratamento de erro, mas o agente devolve detalhe tecnico ao usuario em `services/monitoring_agent.py:74-78`.
- A camera/RTSP e consumida diretamente via OpenCV em `services/video_monitor.py:74`, sem cliente proprio. Para este porte e aceitavel, mas torna dificil testar reconexao e timeouts.
- Nao existe ainda cliente externo dedicado para web scraping/API publica; isso precisa ser criado na Fase 4.

Conclusao: Ollama esta razoavelmente abstraido; camera esta acoplada ao monitor; dados externos devem entrar por cliente proprio.

## Acoplamento

Pontos principais:

- `services/video_monitor.py` acopla captura, inferencia, armazenamento de imagem e banco (`services/video_monitor.py:8-10`, `services/video_monitor.py:103-135`).
- `services/monitoring_agent.py` conhece diretamente o repositorio de eventos e o cliente Ollama (`services/monitoring_agent.py:5-6`, `services/monitoring_agent.py:65-72`).
- `app.py` importa singletons globais de servicos (`app.py:10-15`), simples para MVP, mas limita injecao de dependencias em testes.

## Recomendacoes

1. Renderizar eventos no frontend sem `innerHTML`, usando `textContent` para campos dinamicos.
2. Reduzir vazamento de erro tecnico do Ollama para o usuario final; manter detalhes apenas em log.
3. Criar uma funcao/metodo claro de contexto operacional do agente, incluindo eventos e dados externos sanitizados.
4. Implementar cliente HTTP externo separado (`external_data_client.py`) e servico de negocio/cache (`weather_service.py`).
5. Persistir snapshots externos por repositorio proprio ou modulo dedicado, mantendo SQL fora de rotas e UI.
6. Adicionar headers basicos de seguranca e politica CORS configuravel.
7. Manter `VideoMonitor` como esta nesta entrega, salvo ajustes pontuais, porque separar captura/inferencia/persistencia exigiria refatoracao maior que o escopo.

