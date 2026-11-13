# PhantomGPT

Run on this device:

```sh
cd /storage/emulated/0/Download/PhantomGPT
sh start.sh
```

Open http://127.0.0.1:8000. Set `PORT` to change the port. The server binds to localhost because the app exposes workspace shell commands without authentication.

Configuration is loaded from `.env`. `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` configure chat and builder access. Optional provider keys enable their respective integrations. Data is stored in `phantomgpt.db` and `workspaces/`.

## Termux environment

Android shared storage cannot execute virtual environment binaries, so this installation uses `/data/data/com.termux/files/usr/tmp/phantomgpt-venv`. It inherits the device's compiled Python packages, including Pydantic. Recreate if temporary storage is cleared:

```sh
python -m venv --system-site-packages /data/data/com.termux/files/usr/tmp/phantomgpt-venv
/data/data/com.termux/files/usr/tmp/phantomgpt-venv/bin/python -m pip install pybind11
/data/data/com.termux/files/usr/tmp/phantomgpt-venv/bin/python -m pip install pillow==12.0.0 --no-build-isolation
/data/data/com.termux/files/usr/tmp/phantomgpt-venv/bin/python -m pip install -r requirements-termux.txt
```

Native builds require the Termux C and Rust toolchains and JPEG/zlib headers. `PHANTOM_PYTHON` overrides the interpreter used by `start.sh`.

The existing API key was retained in `.env`; example files contain no key. The configured model is `venice-uncensored-1-2`.

Node/npm use a local ICU 79 library extracted under `/data/data/com.termux/files/usr/tmp/phantomgpt-runtime`; `start.sh` sets the library path for the server and its builder subprocesses. To restore it after clearing temporary storage:

```sh
cd /data/data/com.termux/files/usr/tmp
apt download libicu
dpkg-deb -x libicu_79.1_aarch64.deb phantomgpt-runtime
```

The static UI needs no npm build. Node/npm/git are optional builder commands. Tor and Shadowsocks profiles additionally require the `tor` and `sslocal` executables; direct and existing HTTP/SOCKS proxies do not.

## Docker

Build with the supplied Dockerfile and publish port 8000 on localhost. Provide configuration with `--env-file .env` and mount persistent storage as needed.

## Verified installation

The homepage, status, tools, personas, builder models, network status, OpenAPI schema, and PDF export were checked. `pip check` passed. The provider accepted the configured API key for model discovery, but a live chat request returned HTTP 402 for insufficient USD or Diem balance. Fund that Venice account to enable chat and AI builder responses.

The server was started in the background; `server.log` contains output and `server.pid` records its process ID. Stop it with `kill "$(cat server.pid)"`; restart with `sh start.sh`. Android may stop background processes or clear temporary storage.
