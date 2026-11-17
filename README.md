# OpenModel Chat

A ChatGPT-style web app where you pick **any OpenRouter model** from one interface and switch between models mid-conversation. Open source (MIT), Python, runs locally on Windows.

> **You bring your own OpenRouter API key.** Free-model availability, rate limits and uptime are controlled by OpenRouter and its providers, not by this project.

## Features

- Multi-model chat: pick a model from the sidebar, switch any time; the conversation is kept and you are warned that models may read earlier messages differently
- Streaming replies with a **Stop** button, **Regenerate**, and **Copy** per response
- Safe Markdown rendering, syntax-highlighted code with a **Copy code** button
- Conversation history in SQLite: new, rename, delete, search, load, clear, export to **TXT** and **Markdown**
- API key validation before the first chat; key held in memory only (or `.env`)
- Model availability indicator (checked live against OpenRouter), model descriptions, context length and input types when OpenRouter reports them
- Real metrics only: response time, and token usage when the provider returns it. Nothing is estimated
- Basic usage statistics, light/dark themes, responsive layout
- Add your own models from Settings; model list lives in `models/models.json`

## Included models

| Name | Model ID |
|---|---|
| NVIDIA Nemotron 3 Ultra | `nvidia/nemotron-3-ultra-550b-a55b:free` |
| NVIDIA Nemotron 3.5 Super VL | `nvidia/nemotron-3.5-super-vl:free` |
| Baidu ERNIE 5.5 Flash Preview | `baidu/ernie-5.5-flash-preview:free` |
| Thinking Machines Inkling 2 Small | `thinkingmachines/inkling-2-small:free` |
| Particle-1 | `particle-ai/particle-1:free` |

IDs can be retired or renamed by OpenRouter at any time. The app checks them against OpenRouter's live model list and shows a red/amber/green dot. If one is gone, edit `models/models.json` or add a replacement in **Settings -> Models**.

The app is text-only. Some models accept images, but this version does not send them.

## Screenshots

_Add screenshots here after your first run (for example `docs/screenshot-light.png`)._

## Install (Windows PowerShell, Python 3.11+)

```powershell
cd OpenModelChat
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\run.ps1
```

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

The browser opens at <http://127.0.0.1:8080>.

## API key setup

1. Create a key at <https://openrouter.ai/keys>.
2. Use **one** of:
   - In the app: sidebar -> **API key** -> paste -> **Validate and use**. It lives in memory until you close the app. Tick the checkbox to also save it to your local `.env`.
   - Edit `.env` and set `OPENROUTER_API_KEY=...`, then restart.
3. The key is never stored in SQLite, never logged, and `.env` is in `.gitignore`.

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | empty | Your key (optional if you paste it in the app) |
| `HOST` | `127.0.0.1` | Interface to listen on. Keep it local: the key is shared by everyone who can open the page |
| `PORT` | `8080` | Port |
| `REQUEST_TIMEOUT_SECONDS` | `90` | Network timeout |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API endpoint |

## Usage

1. Add your API key, choose a model in the sidebar, type a message, press **Enter** (Shift+Enter for a new line).
2. Switch models whenever you like; the next reply uses the new model.
3. Use the `...` menu on a conversation to rename, export or delete it. **Clear chat** empties the open one.
4. **Settings** has an optional system prompt, temperature, model management, and statistics.

## Project layout

```
app.py                  entry point
config.py               settings (secrets only from environment)
models/                 model_registry.py + models.json (the model list)
services/               openrouter_client, chat_service, model_service, errors, exporter, key_store
database/               chat_database.py (SQLite)
ui/                     sidebar, chat_interface, settings, page, theme, markdown_render
tests/                  unit tests
```

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
```

## Security and privacy

- Keys come from the environment or memory only; error text and logs are scrubbed of keys
- Model output is rendered with raw HTML escaped, `javascript:` links removed, remote images blocked (an image URL could leak data), and nothing is executed
- Messages go only to OpenRouter and the provider of the model you chose. Free models may log prompts, so read OpenRouter's privacy settings before sending sensitive data
- Conversations are stored locally in `data/chats.db`

## Troubleshooting

| Problem | Fix |
|---|---|
| "OpenRouter rejected your API key" | Re-copy the key, make sure it is active at openrouter.ai/keys |
| "Model is not available" / red dot | The ID was retired or has no provider. Pick another or edit `models/models.json` |
| "Rate limit reached" | Free models are limited. Wait, or switch models |
| "Insufficient credits" | Add credits or use a `:free` model |
| Empty response | Some models return only hidden reasoning. Retry or switch models |
| Port already in use | Change `PORT` in `.env` |
| `python` not found | Install Python 3.11+ and tick "Add to PATH" |
| Amber dot everywhere | The model list could not be fetched (offline). Chat may still work |

## License

MIT, see `LICENSE`.
