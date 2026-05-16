# Fase 0 - Reconhecimento

## Inventario de arquivos

| Caminho | Papel |
|---|---|
| `app.py` | Ponto de entrada FastAPI; registra rotas, monta arquivos estaticos/templates e inicia/para monitor de video e cliente Ollama no lifespan. |
| `requirements.txt` | Lista dependencias Python com versoes fixadas. |
| `detections.db` | Banco SQLite local usado para persistir eventos detectados. |
| `manual_agrovision_implantacao.pdf` | Material/manual de implantacao do projeto. |
| `yolov8n.pt` | Peso YOLO local na raiz, usado como fallback quando nao existe modelo em `models/`. |
| `services/__init__.py` | Marca `services` como pacote Python. |
| `services/config.py` | Carrega configuracoes a partir de `.env`/variaveis de ambiente e define paths do projeto. |
| `services/capture_store.py` | Salva capturas JPEG em `static/captures` e retorna caminho publico. |
| `services/event_repository.py` | Isola conexao SQLite, criacao da tabela `events` e operacoes de salvar/listar/contar eventos. |
| `services/monitoring_agent.py` | Define identidade/regras do agente, monta contexto de eventos e conversa com o Ollama. |
| `services/ollama_client.py` | Cliente HTTP assíncrono para Ollama (`/api/chat` e `/api/tags`). |
| `services/schemas.py` | Modelos Pydantic usados nas respostas/status/chat da API. |
| `services/video_monitor.py` | Loop de captura, inferencia YOLO, filtro de classes/confianca, cooldown e persistencia de eventos. |
| `templates/index.html` | Estrutura HTML do dashboard web. |
| `static/dashboard.css` | Estilos do dashboard. |
| `static/dashboard.js` | JavaScript do dashboard; busca status/eventos, envia chat e atualiza a interface. |
| `static/captures/capture_20260428_113058_302764.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113101_416770.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113212_503196.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113217_552272.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113233_737646.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113237_746634.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113259_673922.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113303_292062.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113341_175613.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113350_077099.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113353_157195.jpg` | Captura gerada por deteccao anterior. |
| `static/captures/capture_20260428_113516_989670.jpg` | Captura gerada por deteccao anterior. |

Arquivos ignorados nesta leitura arquitetural: `.git/` e `__pycache__/`, por serem metadados do Git e cache de execucao Python.

## Fluxo de dados principal

```text
CAMERA_SOURCE (.env ou webcam 0)
  -> services.video_monitor.VideoMonitor._loop()
  -> OpenCV le frame
  -> VideoMonitor._process_frame()
  -> YOLO detecta objetos
  -> filtro por target_classes + confianca minima + cooldown
  -> services.capture_store.save_capture() salva imagem
  -> services.event_repository.save_event() grava no SQLite
  -> /events e /agent/status expõem eventos recentes
  -> services.monitoring_agent.MonitoringAgent.chat()
  -> monta system prompt com identidade, regras e eventos recentes
  -> services.ollama_client.OllamaClient.chat()
  -> Ollama llama3 gera resposta
  -> /chat retorna resposta ao dashboard
```

## Mapeamento por camadas

| Camada | Arquivos |
|---|---|
| Frontend | `templates/index.html`, `static/dashboard.css`, `static/dashboard.js`, imagens em `static/captures/` |
| Backend/API | `app.py`, `services/schemas.py` |
| Banco/persistencia | `detections.db`, `services/event_repository.py` |
| Servicos internos | `services/config.py`, `services/capture_store.py`, `services/video_monitor.py` |
| IA/modelos | `services/video_monitor.py` (YOLO), `services/monitoring_agent.py` (agente), `services/ollama_client.py` (LLM), `yolov8n.pt` |
| Integracoes externas | `services/ollama_client.py` (Ollama local HTTP), `services/video_monitor.py` (camera local/RTSP/HTTP via OpenCV) |
| Documentacao | `manual_agrovision_implantacao.pdf`, `docs/00-reconhecimento.md` |

## Dependencias do `requirements.txt`

| Dependencia | Para que serve |
|---|---|
| `fastapi==0.115.0` | Framework web usado para criar rotas HTTP, modelos de resposta e lifecycle da aplicacao. |
| `uvicorn[standard]==0.30.6` | Servidor ASGI para executar a aplicacao FastAPI em desenvolvimento/producao simples. |
| `opencv-python==4.10.0.84` | Captura frames de camera/stream, codifica JPEG e salva capturas. |
| `ultralytics==8.3.0` | Biblioteca YOLO usada para carregar `yolov8n.pt` e executar deteccao de objetos. |
| `jinja2==3.1.4` | Motor de templates usado pelo FastAPI para renderizar `templates/index.html`. |
| `python-multipart==0.0.9` | Suporte a formularios multipart no ecossistema FastAPI; atualmente nao ha upload implementado. |
| `httpx==0.27.2` | Cliente HTTP assíncrono usado para falar com Ollama; tambem adequado para a futura coleta externa. |
| `python-dotenv==1.0.1` | Carrega variaveis de ambiente a partir de `.env`. |

