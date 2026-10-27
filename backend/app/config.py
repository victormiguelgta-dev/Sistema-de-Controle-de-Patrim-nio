"""Configurações lidas do ambiente e do arquivo backend/.env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # pasta backend/
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(os.getenv("PATRIMONIO_DATA_DIR", str(BASE_DIR / "data")))
        self.uploads_dir = self.data_dir / "uploads"
        self.database_url = os.getenv(
            "DATABASE_URL", f"sqlite:///{(self.data_dir / 'patrimonio.db').as_posix()}"
        )
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        # Plano gratuito tem limite de requisições por minuto: espera entre lotes.
        self.gemini_intervalo = float(os.getenv("GEMINI_INTERVALO_SEGUNDOS", "6"))
        self.gemini_max_chars = int(os.getenv("GEMINI_MAX_CHARS_POR_LOTE", "12000"))
        # Provedor da IA de importação: "ollama" (local, nada sai do computador) ou "gemini" (nuvem)
        self.ia_provedor = os.getenv("IA_PROVEDOR", "ollama").strip().lower()
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").strip().rstrip("/")
        self.ollama_modelo = os.getenv("OLLAMA_MODELO", "qwen2.5:7b").strip()
        # Modelos locais têm contexto menor: lotes de texto menores.
        self.ollama_max_chars = int(os.getenv("OLLAMA_MAX_CHARS_POR_LOTE", "5000"))
        self.ollama_contexto = int(os.getenv("OLLAMA_CONTEXTO", "8192"))
        self.ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT_SEGUNDOS", "600"))
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "100"))
        self.cors_origins = [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if o.strip()
        ]

    def preparar_pastas(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()


def salvar_env(chaves: dict[str, str]) -> None:
    """Atualiza (ou cria) linhas do backend/.env sem apagar as outras."""
    linhas: list[str] = []
    if ENV_FILE.exists():
        linhas = ENV_FILE.read_text(encoding="utf-8").splitlines()
    restantes = dict(chaves)
    novas: list[str] = []
    for linha in linhas:
        nome = linha.split("=", 1)[0].strip()
        if nome in restantes:
            novas.append(f"{nome}={restantes.pop(nome)}")
        else:
            novas.append(linha)
    for nome, valor in restantes.items():
        novas.append(f"{nome}={valor}")
    ENV_FILE.write_text("\n".join(novas) + "\n", encoding="utf-8")
