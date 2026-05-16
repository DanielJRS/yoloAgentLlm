# RELATORIO_INPUT - AgroVision AI

Este arquivo e auto-contido para servir de base ao relatorio final da atividade.

## 1. Resumo executivo do projeto

O AgroVision AI e um sistema de monitoramento por visao computacional para o agronegocio. Ele captura video de webcam, arquivo, HTTP ou RTSP, executa deteccao com YOLO, salva eventos em SQLite e permite que um operador converse com um agente que interpreta os eventos recentes usando Ollama/llama3. Nesta atividade, o sistema ganhou revisao critica, refatoracoes de seguranca e uma camada de dados externos de clima via Open-Meteo.

Stack tecnica:

| Tecnologia | Versao | Uso |
|---|---:|---|
| Python | 3.12 no ambiente local | Backend e servicos |
| FastAPI | 0.115.0 | API HTTP e dashboard |
| Uvicorn | 0.30.6 | Servidor ASGI |
| OpenCV | 4.10.0.84 | Captura/codificacao de video |
| Ultralytics YOLO | 8.3.0 | Deteccao de objetos |
| Jinja2 | 3.1.4 | Template HTML |
| httpx | 0.27.2 | Clientes HTTP para Ollama e Open-Meteo |
| python-dotenv | 1.0.1 | Variaveis de ambiente |
| SQLite | embutido no Python | Persistencia de eventos e clima |
| Ollama + llama3 | local | LLM do agente |

Fluxo de dados:

```text
Camera local/RTSP/HTTP
  -> OpenCV VideoCapture
  -> YOLO (ultralytics)
  -> filtro por classes alvo + confianca + cooldown
  -> captura JPG em static/captures
  -> SQLite tabela events
  -> FastAPI (/events, /agent/status, /video_feed)
  -> Dashboard web

Usuario no chat
  -> FastAPI /chat
  -> MonitoringAgent
  -> eventos recentes do SQLite
  -> WeatherService busca/cacheia Open-Meteo
  -> contexto: eventos + clima atual
  -> Ollama llama3
  -> resposta no dashboard

Open-Meteo
  -> ExternalDataClient (timeout/retry/backoff)
  -> WeatherService (cache/rate limit/parse)
  -> SQLite tb_weather_snapshot
  -> /external/weather + contexto do agente
```

## 2. Inventario de arquivos

| Caminho | Papel | Status | Camada |
|---|---|---|---|
| `app.py` | Rotas FastAPI, lifespan, headers, CORS, endpoint de clima | modificado nesta atividade | Backend/API |
| `requirements.txt` | Dependencias do projeto | existente | Configuracao |
| `detections.db` | Banco SQLite local | existente | Banco |
| `manual_agrovision_implantacao.pdf` | Manual do projeto | existente | Documentacao |
| `yolov8n.pt` | Peso YOLO | existente | IA/modelo |
| `services/config.py` | Configuracoes `.env` e paths | modificado nesta atividade | Configuracao |
| `services/capture_store.py` | Persistencia de capturas JPG | existente | Servico interno |
| `services/event_repository.py` | Repositorio SQLite de eventos | existente | Banco |
| `services/external_data_client.py` | Cliente HTTP generico para dados externos | criado nesta atividade | Integracao externa |
| `services/monitoring_agent.py` | Agente, memoria curta, prompt, contexto eventos/clima | modificado nesta atividade | IA/agente |
| `services/ollama_client.py` | Cliente HTTP do Ollama | existente | Integracao IA |
| `services/schemas.py` | Modelos Pydantic de API/chat/clima | modificado nesta atividade | Contratos |
| `services/video_monitor.py` | Captura, YOLO, eventos | modificado nesta atividade | IA/video |
| `services/weather_repository.py` | Repositorio SQLite de snapshots de clima | criado nesta atividade | Banco |
| `services/weather_service.py` | Cache/rate limit/parse de clima | criado nesta atividade | Servico externo |
| `templates/index.html` | Dashboard HTML | modificado nesta atividade | Frontend |
| `static/dashboard.css` | Estilos do dashboard | modificado nesta atividade | Frontend |
| `static/dashboard.js` | Fetch/render de status, eventos, chat e clima | modificado nesta atividade | Frontend |
| `static/captures/*.jpg` | Capturas geradas anteriormente | existente | Frontend/artefatos |
| `docs/00-reconhecimento.md` | Reconhecimento do projeto | criado nesta atividade | Documentacao |
| `docs/01-arquitetura.md` | Analise de arquitetura | criado nesta atividade | Documentacao |
| `docs/02-seguranca.md` | Analise de seguranca | criado nesta atividade | Documentacao |
| `docs/03-refatoracoes.md` | Registro das refatoracoes | criado nesta atividade | Documentacao |
| `docs/04-scraping.md` | Documentacao da camada externa | criado nesta atividade | Documentacao |
| `docs/RELATORIO_INPUT.md` | Base auto-contida do relatorio final | criado nesta atividade | Documentacao |

## 3. Analise de arquitetura

Frontend:

- Positivo: `templates/index.html` e `static/dashboard.js` atuam majoritariamente como apresentacao. A UI busca `/camera/status`, `/agent/status`, `/external/weather` e `/chat`, sem decidir regras de negocio.
- Problema original: `static/dashboard.js` usava `innerHTML` para renderizar evento, o que poderia permitir XSS se dados manipulados chegassem ao banco.
- Trecho atual representativo: `static/dashboard.js` cria campos com `textContent`, mantendo dados dinamicos como texto.

Backend/API:

- Positivo: `app.py:22-32` centraliza lifecycle: inicializa tabelas, inicia monitor, fecha clientes.
- Positivo: rotas delegam a servicos: camera em `monitor.status()`, eventos em `list_recent()`, chat em `agent.chat()`, clima em `weather_service.get_snapshot()`.
- Negativo residual: `/chat` continua aberto sem autenticacao (`app.py:123-126`). Para ambiente academico/local e aceitavel, mas em rede real exigiria token/autenticacao/rate limit.

Banco:

- Positivo: eventos ficam isolados em `services/event_repository.py`, com SQL parametrizado.
- Novo positivo: clima ganhou repositorio proprio em `services/weather_repository.py:35-69`, tambem com parametros vinculados no insert.
- Negativo residual: nao ha migrador formal; schemas usam `CREATE TABLE IF NOT EXISTS`, suficiente para MVP.

IA:

- Positivo: `services/ollama_client.py` separa HTTP do Ollama da regra do agente.
- Positivo: `services/monitoring_agent.py:36-63` agora monta contexto operacional com eventos e clima.
- Negativo residual: `services/video_monitor.py` ainda concentra captura, inferencia YOLO, cooldown, captura JPG e persistencia. Foi mantido assim por escopo, pois separar tudo exigiria refatoracao maior.

Integracoes:

- Ollama: cliente proprio com timeout e tratamento de erro.
- Camera/RTSP: OpenCV direto dentro do monitor, com reconexao.
- Open-Meteo: novo cliente externo generico (`services/external_data_client.py`) + servico de negocio (`services/weather_service.py`).

Scraping/dados externos:

- A fonte externa foi implementada como API publica JSON da Open-Meteo, preferida a scraping HTML por ser mais estavel, leve e respeitosa.

## 4. Analise de seguranca

| # | Risco | Severidade | Onde esta | Impacto | Mitigacao aplicada ou recomendacao |
|---|---|---|---|---|---|
| 1 | `/chat` aberto sem autenticacao | Media | `app.py:123-126` | Uso indevido do Ollama e consumo de recursos | Pendente: adicionar token/rate limit se exposto fora de localhost |
| 2 | Prompt injection | Media | `services/monitoring_agent.py:19-25`, `:65-71` | Usuario tenta ignorar regras e inventar deteccoes | Aplicado: regra anti-injecao e wrapper de mensagem nao confiavel |
| 3 | Vazamento de erro tecnico do Ollama | Media | `services/monitoring_agent.py:105-112` | Exposicao de URL/modelo/excecao interna | Aplicado: detalhe vai para log; usuario recebe mensagem generica |
| 4 | XSS via `innerHTML` | Media | `static/dashboard.js` | Dado manipulado poderia virar HTML/JS | Aplicado: render com `textContent` |
| 5 | Falta de headers de seguranca | Baixa | `app.py:48-54` | Menor endurecimento do navegador | Aplicado: `nosniff`, `same-origin`, `DENY` |
| 6 | CORS implicito | Baixa | `app.py:37-45`, `services/config.py:64` | Politica pouco documentada | Aplicado: `CORS_ORIGINS` opcional; fechado por padrao |
| 7 | Credenciais em URL de camera no log | Baixa | `services/video_monitor.py` | RTSP com usuario/senha poderia aparecer em log | Aplicado: `_safe_source_display` mascara credenciais |
| 8 | Entrada de chat pouco normalizada | Baixa | `services/schemas.py:41-49` | Espacos/vazio tratados no controller | Aplicado: schema Pydantic normaliza e recusa vazio |
| 9 | SQL injection | Baixa | `services/event_repository.py`, `services/weather_repository.py` | Manipulacao de SQL | Padrao parametrizado mantido |
| 10 | Conteudo externo contaminando prompt/banco | Media | `services/weather_service.py:99-116` | Fonte externa malformada poderia induzir resposta errada | Aplicado: parse estruturado em `WeatherSnapshot`, fonte e timestamps no contexto |
| 11 | Upload de arquivos | Baixa | Nao existe | Nao aplicavel | Recomendar validacao se feature for criada |

## 5. Refatoracoes aplicadas

Total: 7 refatoracoes documentadas em `docs/03-refatoracoes.md`.

1. Renderizacao segura dos eventos
   - Antes: `meta.innerHTML = ... ${e.label} ...`
   - Depois: `document.createElement` + `textContent`.
   - Beneficio: reduz XSS sem mudar UX.

2. Erro do Ollama sem vazamento tecnico
   - Antes: resposta continha `config.ollama_url`, modelo e excecao.
   - Depois: `logger.warning(...)` registra detalhe e usuario recebe mensagem generica.
   - Beneficio: melhora seguranca operacional.

3. Delimitacao anti prompt injection
   - Antes: `messages.append({"role": "user", "content": user_message})`.
   - Depois: `_trusted_user_message(user_message)` delimita entrada como nao confiavel.
   - Beneficio: reforca hierarquia de instrucoes.

4. Contexto operacional do agente exposto
   - Antes: `_system_prompt` montava tudo internamente.
   - Depois: `build_event_context(events, weather)` aceita clima.
   - Beneficio: extensivel sem reescrever o prompt inteiro.

5. Headers de seguranca e CORS configuravel
   - Antes: app sem middleware transversal.
   - Depois: headers e `CORS_ORIGINS`.
   - Beneficio: melhor comportamento em navegador e configuracao clara.

6. Mascaramento de credenciais da camera
   - Antes: log truncava fonte.
   - Depois: log mascara `usuario:senha@host`.
   - Beneficio: evita expor credenciais de RTSP/HTTP.

7. Normalizacao Pydantic do chat
   - Antes: rota fazia `strip`.
   - Depois: `ChatRequest` normaliza e valida.
   - Beneficio: contrato de entrada centralizado.

Resumo de alteracoes: 16 arquivos criados/modificados, 940 insercoes e 18 delecoes em relacao ao commit anterior a atividade.

## 6. Camada de scraping

Tema: clima atual, por relevancia direta ao agronegocio.

Fonte: Open-Meteo. Foi escolhida por ser publica, gratuita, sem chave, estruturada em JSON e mais robusta que scraping HTML. A decisao deve ser explicada como "coleta automatizada de dados publicos da web por API quando disponivel".

Arquitetura:

```text
app.py /external/weather
  -> WeatherService.get_snapshot()
     -> valida config WEATHER_LATITUDE/LONGITUDE/USER_AGENT
     -> cache TTL + limite por hora
     -> ExternalDataClient.get_json()
     -> Open-Meteo JSON
     -> WeatherSnapshot
     -> WeatherRepository.save_weather_snapshot()
```

Snippets representativos:

```python
# services/external_data_client.py
response = await self._client.get(url, params=params, headers=headers, timeout=timeout)
response.raise_for_status()
data = response.json()
```

```python
# services/weather_service.py
if not force_refresh and self._cached is not None and now < self._expires_at:
    return self._cached
```

```python
# services/monitoring_agent.py
weather = await weather_service.get_snapshot()
messages = [{"role": "system", "content": self._system_prompt(events, weather)}]
```

Integracao:

- Agente: clima entra em `build_event_context`, com fonte e timestamps.
- Dashboard: card "Clima atual" consulta `/external/weather`.
- Banco: snapshots salvos em `tb_weather_snapshot` para historico e fallback.

Tratamento de erro/cache:

- Timeout: 8 segundos.
- Retry: 2 tentativas extras com backoff exponencial.
- TTL: `WEATHER_TTL_MINUTES`, padrao 30 minutos.
- Rate limit: `WEATHER_MAX_CALLS_PER_HOUR`, padrao 2/hora.
- Fallback: ultimo snapshot em memoria ou SQLite.
- Sem configuracao/cache: rota retorna `{"available": false, "reason": "...", "snapshot": null}`.

Boas praticas:

- User-Agent configuravel por `WEATHER_USER_AGENT`.
- Dados externos estruturados em Pydantic antes do prompt.
- SQL parametrizado.
- Fonte e timestamp sempre presentes para evitar dado "magico" no LLM.

## 7. Evidencias

Arquivos criados/modificados:

- Criados: `docs/00-reconhecimento.md`, `docs/01-arquitetura.md`, `docs/02-seguranca.md`, `docs/03-refatoracoes.md`, `docs/04-scraping.md`, `docs/RELATORIO_INPUT.md`, `services/external_data_client.py`, `services/weather_repository.py`, `services/weather_service.py`.
- Modificados: `app.py`, `services/config.py`, `services/monitoring_agent.py`, `services/schemas.py`, `services/video_monitor.py`, `static/dashboard.js`, `static/dashboard.css`, `templates/index.html`.

Commits realizados:

```text
af74173 fase-0-reconhecimento
b490300 fase-1-arquitetura
f97e6e3 fase-2-seguranca
5f0e7b3 fase-3-refatoracoes
fcb50a9 fase-4-scraping
```

Comandos para rodar localmente:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama serve
ollama pull llama3
export WEATHER_LATITUDE=-23.5505
export WEATHER_LONGITUDE=-46.6333
export WEATHER_TTL_MINUTES=30
export WEATHER_MAX_CALLS_PER_HOUR=2
export WEATHER_USER_AGENT="AgroVisionAI/1.0 (contato: seu-email@example.com)"
uvicorn app:app --reload
```

URLs para teste:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/health
http://127.0.0.1:8000/external/weather
http://127.0.0.1:8000/agent/status
```

Verificacoes feitas:

- `python3 -m compileall app.py services` executou com sucesso, validando sintaxe dos arquivos Python.
- Uma tentativa de importacao real no ambiente global falhou porque `python-dotenv` nao estava instalado fora de um venv; isso e esperado neste container/local atual e e resolvido com `pip install -r requirements.txt`, pois `python-dotenv==1.0.1` esta no projeto.
- Com variaveis de clima ausentes, `/external/weather` foi projetado para nao quebrar o sistema: retorna indisponibilidade em JSON e o agente segue sem snapshot.

Comportamento esperado:

- Dashboard mostra camera, eventos, chat e um card de clima.
- Se clima estiver configurado, card exibe temperatura, condicao, umidade, vento e fonte Open-Meteo.
- Se Open-Meteo falhar depois de ja haver snapshot salvo, o ultimo valor persistido e usado.
- No chat, o agente considera eventos recentes e clima atual, mas nao deve inventar deteccoes.

## 8. Pendencias e proximos passos

- Adicionar autenticacao simples para `/chat` e endpoints administrativos se o app sair de localhost.
- Criar testes automatizados para `WeatherService`, repositorios e agente.
- Separar `VideoMonitor` em captura, inferencia e persistencia se o projeto crescer.
- Adicionar migracoes formais para SQLite.
- Persistir configuracoes operacionais de camera/clima via painel administrativo.
- Melhorar observabilidade com logs estruturados e metricas.

## 9. Conclusao tecnica

Antes da atividade, o AgroVision AI ja possuia uma base funcional: FastAPI, dashboard, YOLO, SQLite, agente e Ollama estavam conectados. Depois da revisao, o projeto ficou mais documentado, com riscos mapeados, entradas mais seguras, menos vazamento de detalhes internos e uma camada externa de clima integrada sem quebrar a arquitetura existente.

O principal aprendizado tecnico da revisao foi separar evolucao de reescrita. O projeto nao precisava ser reconstruido; precisava de ajustes cirurgicos nos pontos certos: fronteiras entre camadas, tratamento de erro, validacao, renderizacao segura e integracao externa com cache/fallback. Isso torna a entrega academica mais forte e tambem deixa o sistema mais facil de evoluir.

