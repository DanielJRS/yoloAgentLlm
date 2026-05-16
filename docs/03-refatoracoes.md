# Fase 3 - Refatoracoes

### Refatoracao 1: Renderizacao segura dos eventos

- Arquivo(s): `static/dashboard.js`
- O que o codigo fazia originalmente: montava os metadados de cada evento usando template string em `innerHTML`.
- Problema encontrado: campos dinamicos poderiam virar HTML executavel caso algum dado manipulado chegasse ao banco.
- O que foi alterado: cada campo passou a ser criado com `document.createElement` e preenchido via `textContent`.
- Por que a nova versao e melhor: reduz risco de XSS sem mudar a experiencia visual.

Antes:
```js
meta.innerHTML = `
  <div class="e-label">${e.label}</div>
  <div class="e-time">${e.event_time}</div>
  <div class="e-conf">conf ${Number(e.confidence).toFixed(2)}</div>
`;
```

Depois:
```js
const label = document.createElement("div");
label.className = "e-label";
label.textContent = e.label;
const time = document.createElement("div");
time.className = "e-time";
time.textContent = e.event_time;
const conf = document.createElement("div");
conf.className = "e-conf";
conf.textContent = `conf ${Number(e.confidence).toFixed(2)}`;
meta.append(label, time, conf);
```

### Refatoracao 2: Erro do Ollama sem vazamento tecnico

- Arquivo(s): `services/monitoring_agent.py`
- O que o codigo fazia originalmente: devolvia URL, modelo e detalhe da excecao do Ollama para o usuario.
- Problema encontrado: detalhes internos ajudam reconhecimento do ambiente e poluem a resposta do operador.
- O que foi alterado: o detalhe tecnico ficou no log e a resposta ao usuario passou a ser operacional e generica.
- Por que a nova versao e melhor: mantem diagnostico para desenvolvedor sem expor internals no dashboard.

Antes:
```python
except OllamaError as exc:
    return (
        "Não consegui falar com o Ollama agora. Verifique se o serviço "
        f"está rodando em {config.ollama_url} e se o modelo "
        f"'{config.ollama_model}' está instalado.\nDetalhe técnico: {exc}"
    )
```

Depois:
```python
except OllamaError as exc:
    logger.warning("ollama unavailable during agent chat: %s", exc)
    return (
        "Não consegui falar com o Ollama agora. Verifique se o serviço "
        "está rodando e se o modelo configurado está instalado."
    )
```

### Refatoracao 3: Delimitacao anti prompt injection

- Arquivo(s): `services/monitoring_agent.py`
- O que o codigo fazia originalmente: anexava a mensagem do usuario diretamente no array de mensagens do LLM.
- Problema encontrado: o LLM poderia tratar texto hostil como instrucao para substituir regras do sistema.
- O que foi alterado: foi adicionada regra explicita de entrada nao confiavel e um wrapper para delimitar a mensagem do operador.
- Por que a nova versao e melhor: nao elimina prompt injection, mas melhora a hierarquia de instrucoes e deixa claro que usuario nao altera identidade/regras.

Antes:
```python
messages.append({"role": "user", "content": user_message})
```

Depois:
```python
messages.append({"role": "user", "content": self._trusted_user_message(user_message)})
```

### Refatoracao 4: Contexto operacional do agente exposto

- Arquivo(s): `services/monitoring_agent.py`
- O que o codigo fazia originalmente: `_system_prompt` montava diretamente o bloco de eventos.
- Problema encontrado: a futura camada externa precisaria mexer no prompt inteiro para adicionar contexto.
- O que foi alterado: o bloco de eventos foi extraido para `build_event_context`.
- Por que a nova versao e melhor: cria um ponto claro para enriquecer o contexto com clima sem reescrever identidade e regras do agente.

Antes:
```python
def _system_prompt(self, events: list[Event]) -> str:
    rules_block = "\n".join(f"- {r}" for r in RULES)
    if events:
        lines = [
            f"- {e.event_time} | {e.label} (confiança {e.confidence:.2f})"
            for e in events
        ]
        events_block = "Eventos recentes (mais novo primeiro):\n" + "\n".join(lines)
    else:
        events_block = "Eventos recentes: nenhum evento registrado até o momento."
```

Depois:
```python
def build_event_context(self, events: list[Event]) -> str:
    if events:
        lines = [
            f"- {e.event_time} | {e.label} (confiança {e.confidence:.2f})"
            for e in events
        ]
        return "Eventos recentes (mais novo primeiro):\n" + "\n".join(lines)
    return "Eventos recentes: nenhum evento registrado até o momento."
```

### Refatoracao 5: Headers de seguranca e CORS configuravel

- Arquivo(s): `app.py`, `services/config.py`
- O que o codigo fazia originalmente: criava o app FastAPI sem headers de seguranca e sem politica CORS explicita.
- Problema encontrado: respostas do dashboard/API ficavam sem politicas basicas de navegador, e CORS nao era documentado/configuravel.
- O que foi alterado: adicionados headers `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`; CORS agora e ativado apenas se `CORS_ORIGINS` estiver configurado.
- Por que a nova versao e melhor: endurece o comportamento no navegador mantendo padrao fechado.

Antes:
```python
app = FastAPI(title="AgroVision AI", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=config.base_dir / "static"), name="static")
```

Depois:
```python
app = FastAPI(title="AgroVision AI", lifespan=lifespan)
if config.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=list(config.cors_origins), ...)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response
```

### Refatoracao 6: Mascaramento de credenciais da camera

- Arquivo(s): `services/video_monitor.py`
- O que o codigo fazia originalmente: logava a origem da camera usando truncamento simples.
- Problema encontrado: uma URL RTSP/HTTP com `usuario:senha@host` poderia aparecer parcialmente no log.
- O que foi alterado: adicionada `_safe_source_display`, que mascara usuario/senha antes de logar.
- Por que a nova versao e melhor: preserva informacao util de diagnostico sem expor credenciais.

Antes:
```python
logger.info("VideoMonitor started: source=%s", _short(config.camera_source))
```

Depois:
```python
logger.info("VideoMonitor started: source=%s", _safe_source_display(config.camera_source))
```

### Refatoracao 7: Normalizacao Pydantic do chat

- Arquivo(s): `services/schemas.py`, `app.py`
- O que o codigo fazia originalmente: o body aceitava `message` com limites de tamanho, e a rota fazia `strip`.
- Problema encontrado: a normalizacao de entrada ficava espalhada entre schema e controller.
- O que foi alterado: o schema `ChatRequest` passou a normalizar e recusar mensagem vazia apos `strip`.
- Por que a nova versao e melhor: mantem controller mais simples e centraliza contrato de entrada.

Antes:
```python
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
```

Depois:
```python
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @validator("message")
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("mensagem vazia")
        return normalized
```
