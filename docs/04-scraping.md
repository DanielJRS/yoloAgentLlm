# Fase 4 - Camada de Web Scraping / Dados Externos

## Tema escolhido

Tema: previsao/condicao do tempo.

Esse dado enriquece o AgroVision porque ajuda a interpretar eventos detectados por YOLO no contexto operacional do campo. Exemplo concreto: se o sistema detecta movimentacao de pessoas ou maquinas e o clima indica chuva forte, o agente pode alertar que a operacao ocorre em condicao potencialmente ruim para colheita, pulverizacao ou deslocamento.

## Fonte escolhida

Fonte: Open-Meteo (`https://api.open-meteo.com/v1/forecast`).

Foi escolhida a opcao de API publica gratuita em vez de scraping HTML literal. A justificativa tecnica e que, quando o provedor oferece API publica sem chave, essa e a forma mais correta de coleta automatizada de dados da web: evita parser fragil de HTML, reduz carga desnecessaria no site e retorna JSON estruturado. Para o relatorio, a camada atende ao objetivo de "web scraping" como coleta automatizada de dado publico externo.

## Arquitetura do modulo

```text
Dashboard
  -> GET /external/weather
  -> app.py
  -> services.weather_service.WeatherService
      -> cache em memoria + TTL + limite por hora
      -> services.external_data_client.ExternalDataClient
          -> HTTP GET Open-Meteo com timeout, retries e backoff
      -> valida/parseia JSON em WeatherSnapshot
      -> services.weather_repository.save_weather_snapshot()
          -> SQLite tb_weather_snapshot

Chat do agente
  -> MonitoringAgent.chat()
  -> WeatherService.get_snapshot()
  -> MonitoringAgent.build_event_context(events, weather)
  -> Ollama recebe eventos recentes + clima atual externo no system prompt
```

## Arquivos principais

- `services/external_data_client.py`: cliente HTTP puro, sem regra de negocio; implementa `get_json` com timeout, retries e backoff.
- `services/weather_service.py`: regra de negocio de clima; decide quando atualizar, controla cache/rate limit, chama Open-Meteo e converte JSON em `WeatherSnapshot`.
- `services/weather_repository.py`: cria tabela `tb_weather_snapshot`, salva snapshots e recupera o ultimo valor cacheado em SQLite.
- `services/schemas.py`: adiciona modelo Pydantic `WeatherSnapshot`.
- `app.py`: inicializa tabela de clima, fecha cliente externo e expõe `/external/weather`.
- `services/monitoring_agent.py`: inclui o snapshot mais recente em `build_event_context`.
- `templates/index.html`, `static/dashboard.js`, `static/dashboard.css`: adicionam card pequeno de clima no dashboard.

## Integracao com agente, dashboard e banco

Agente:

- `MonitoringAgent.chat()` tenta obter `weather_service.get_snapshot()`.
- Se a fonte externa falhar, usa `weather_service.latest_cached()`.
- `build_event_context(events, weather)` adiciona fonte, timestamp, condicao, temperatura, umidade e vento ao contexto enviado ao Ollama.

Dashboard:

- `templates/index.html` ganhou a secao "Clima atual".
- `static/dashboard.js` consulta `/external/weather` ao carregar e depois a cada 10 minutos.
- Se clima nao estiver configurado ou a fonte falhar sem cache, o card mostra motivo amigavel em vez de quebrar a tela.

Banco:

- A tabela `tb_weather_snapshot` guarda historico com `collected_at`, `observed_at`, temperatura, umidade, vento, condicao, fonte, latitude e longitude.
- O snapshot salvo permite fallback quando a fonte externa estiver fora do ar.

## Tratamento de erro, rate limiting e cache

- Timeout HTTP: `ExternalDataClient.get_json(... timeout=8.0 ...)`.
- Retries: ate 2 novas tentativas com backoff exponencial (`0.5s`, `1.0s`).
- Cache em memoria: `WeatherService` mantem `_cached` e `_expires_at`.
- TTL: configuravel por `WEATHER_TTL_MINUTES`, padrao de 30 minutos.
- Limite por hora: configuravel por `WEATHER_MAX_CALLS_PER_HOUR`, padrao de 2 chamadas/hora.
- Fallback: se Open-Meteo falhar, o servico retorna o ultimo snapshot em memoria ou SQLite.
- Falha externa nao quebra sistema principal: `/external/weather` retorna JSON com `available: false` quando nao ha configuracao/cache; o agente segue respondendo com eventos e "nenhum snapshot disponivel".

## Configuracao

Variaveis de ambiente esperadas:

```env
WEATHER_LATITUDE=-23.5505
WEATHER_LONGITUDE=-46.6333
WEATHER_TTL_MINUTES=30
WEATHER_MAX_CALLS_PER_HOUR=2
WEATHER_USER_AGENT=AgroVisionAI/1.0 (contato: seu-email@example.com)
```

Latitude, longitude e User-Agent nao ficam fixos no codigo. Sem essas variaveis, a camada fica desabilitada de forma segura e informa o motivo no endpoint.

## Boas praticas aplicadas

- Cliente HTTP separado de regra de negocio.
- Dados externos convertidos para modelo Pydantic estruturado antes de entrar no agente.
- SQL parametrizado no repositorio de clima.
- User-Agent configuravel e identificavel.
- Cache/TTL para evitar chamadas repetidas.
- Rate limit simples para nao martelar a fonte.
- Fonte e timestamps entram no prompt para o agente citar contexto sem parecer dado inventado.

