import os
from dotenv import load_dotenv

load_dotenv()

# ---- LLM ----
API_KEY = os.getenv("LLM_API_KEY", "")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.venice.ai/api/v1")
MODEL = os.getenv("LLM_MODEL", "venice-uncensored-1-2")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.35"))
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "8"))
DB_PATH = os.getenv("DB_PATH", "phantomgpt.db")

# ---- intel providers ----
SHODAN_KEY = os.getenv("SHODAN_KEY", "")
CENSYS_ID = os.getenv("CENSYS_API_ID", "")
CENSYS_SECRET = os.getenv("CENSYS_API_SECRET", "")
DEHASHED_EMAIL = os.getenv("DEHASHED_EMAIL", "")
DEHASHED_KEY = os.getenv("DEHASHED_KEY", "")

# ---- recon behaviour ----
TOOLS_DEFAULT = os.getenv("TOOLS_DEFAULT", "1") == "1"
PREFLIGHT = os.getenv("PREFLIGHT", "1") == "1"
PREFLIGHT_BUDGET = int(os.getenv("PREFLIGHT_BUDGET", "12"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "900"))
HOST_RATE = float(os.getenv("HOST_RATE", "2"))
HOST_BURST = int(os.getenv("HOST_BURST", "4"))
SCOPE_ALLOW = [s.strip().lower() for s in os.getenv("SCOPE_ALLOW", "").split(",") if s.strip()]

# ---- builder ----
WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", "workspaces")
BUILDER_MODEL = os.getenv("BUILDER_MODEL", "venice-uncensored-1-2")
BUILDER_MODELS = [m.strip() for m in os.getenv("BUILDER_MODELS", "venice-uncensored-1-2").split(",") if m.strip()]
BUILDER_MAX_ROUNDS = int(os.getenv("BUILDER_MAX_ROUNDS", "12"))
EXEC_TIMEOUT = int(os.getenv("EXEC_TIMEOUT", "180"))
ALLOW_SHELL = os.getenv("ALLOW_SHELL", "1") == "1"

# ---- card checker ----
STRIPE_KEY = os.getenv("STRIPE_KEY", "")
BINLOOKUP = os.getenv("BINLOOKUP", "1") == "1"
CHECK_CONCURRENCY = int(os.getenv("CHECK_CONCURRENCY", "4"))
CHECK_DELAY = float(os.getenv("CHECK_DELAY", "0.35"))
MAX_CHECK = int(os.getenv("MAX_CHECK", "300"))

# ---- egress ----
SSLOCAL_BIN = os.getenv("SSLOCAL_BIN", "sslocal")
EGRESS_ROTATION = os.getenv("EGRESS_ROTATION", "sticky")
FAIL_CLOSED = os.getenv("FAIL_CLOSED", "1") == "1"
LEAK_TIMEOUT = int(os.getenv("LEAK_TIMEOUT", "12"))
SCRUB_WORKSPACES = os.getenv("SCRUB_WORKSPACES", "1") == "1"

# ---- tor / chaining ----
TOR_BIN = os.getenv("TOR_BIN", "tor")
TOR_SOCKS_BASE = int(os.getenv("TOR_SOCKS_BASE", "9050"))
TOR_CONTROL_BASE = int(os.getenv("TOR_CONTROL_BASE", "9150"))
TOR_BOOTSTRAP_TIMEOUT = int(os.getenv("TOR_BOOTSTRAP_TIMEOUT", "90"))
TOR_MAX_CIRCUIT_DIRTINESS = int(os.getenv("TOR_MAX_CIRCUIT_DIRTINESS", "600"))
CHAIN_PORT_BASE = int(os.getenv("CHAIN_PORT_BASE", "12000"))