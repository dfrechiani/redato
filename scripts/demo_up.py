#!/usr/bin/env python3
"""Sobe portal API + bot WhatsApp + frontend Next.js em background.

Mais robusto que `nohup &` em Makefile (que tinha problemas de
herança de TTY/stdin no macOS). Usa subprocess.Popen com stdout
redirecionado pra arquivos.

Uso:
    python scripts/demo_up.py            # sobe os 3
    python scripts/demo_up.py --stop     # derruba
    python scripts/demo_up.py --status   # mostra estado

PIDs em .demo-pids/{portal,bot,frontend}.pid.
Logs em .demo-pids/{portal,bot,frontend}.log.
"""
from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend" / "notamil-backend"
FRONTEND = REPO_ROOT / "redato_frontend"
PIDS_DIR = REPO_ROOT / ".demo-pids"

DB_NAME = os.environ.get("DB_NAME", "redato_portal_dev")
DB_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql://{os.environ.get('USER', 'user')}@localhost:5432/{DB_NAME}",
)
PORTAL_PORT = 8091
BOT_PORT = 8090
FRONT_PORT = 3010


def _spawn(name: str, *, cmd: list[str], cwd: Path,
           env_overrides: dict[str, str]) -> int:
    """Lança processo em background, salva PID + log. Retorna PID."""
    PIDS_DIR.mkdir(exist_ok=True)
    log_path = PIDS_DIR / f"{name}.log"
    pid_path = PIDS_DIR / f"{name}.pid"

    env = os.environ.copy()
    env.update(env_overrides)

    print(f"  → {name:<8s} : {' '.join(shlex.quote(c) for c in cmd)}")
    log = log_path.open("ab")
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdout=log, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_path.write_text(str(proc.pid))
    return proc.pid


def _read_pid(name: str) -> Optional[int]:
    p = PIDS_DIR / f"{name}.pid"
    if not p.exists():
        return None
    try:
        return int(p.read_text().strip())
    except ValueError:
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _wait_listening(port: int, timeout: int = 30) -> bool:
    """Polla TCP do localhost até alguém escutar. True se subiu, False se timeout."""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", port))
                return True
            except (ConnectionRefusedError, socket.timeout, OSError):
                time.sleep(0.5)
    return False


def cmd_up() -> int:
    print("▶ Subindo portal + bot + frontend (background)\n")

    # Portal API
    _spawn("portal",
        cmd=["uvicorn", "redato_backend.portal.portal_app:app",
             "--host", "127.0.0.1", "--port", str(PORTAL_PORT)],
        cwd=BACKEND,
        env_overrides={"DATABASE_URL": DB_URL},
    )
    # Bot WhatsApp
    _spawn("bot",
        cmd=["uvicorn", "redato_backend.whatsapp.app:app",
             "--host", "127.0.0.1", "--port", str(BOT_PORT)],
        cwd=BACKEND,
        env_overrides={"DATABASE_URL": DB_URL,
                       "TWILIO_VALIDATE_SIGNATURE": "0"},
    )
    # Frontend Next.js
    _spawn("frontend",
        cmd=["npx", "next", "dev", "-p", str(FRONT_PORT)],
        cwd=FRONTEND,
        env_overrides={
            "NEXT_PUBLIC_API_URL": f"http://localhost:{PORTAL_PORT}",
            "REDATO_SESSION_COOKIE": "redato_session",
        },
    )

    print("\n▶ Aguardando portal escutar…")
    if _wait_listening(PORTAL_PORT, timeout=20):
        print(f"  ✓ portal escutando :{PORTAL_PORT}")
    else:
        print(f"  ✗ portal NÃO subiu — veja .demo-pids/portal.log")

    print("▶ Aguardando bot escutar…")
    if _wait_listening(BOT_PORT, timeout=20):
        print(f"  ✓ bot escutando :{BOT_PORT}")
    else:
        print(f"  ✗ bot NÃO subiu — veja .demo-pids/bot.log")

    print("▶ Aguardando frontend (compila on-demand, ~10s)…")
    if _wait_listening(FRONT_PORT, timeout=60):
        print(f"  ✓ frontend escutando :{FRONT_PORT}")
    else:
        print(f"  ✗ frontend NÃO subiu — veja .demo-pids/frontend.log")
    return 0


def cmd_stop() -> int:
    nomes = ("portal", "bot", "frontend")
    print("▶ Derrubando processos…")
    for nome in nomes:
        pid = _read_pid(nome)
        if pid is None:
            continue
        if _alive(pid):
            try:
                # SIGTERM ao process group (incluindo filhos do uvicorn/next)
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                print(f"  ✓ {nome} (pid {pid}) parado")
            except ProcessLookupError:
                pass
        (PIDS_DIR / f"{nome}.pid").unlink(missing_ok=True)

    # Garantia adicional: derruba qualquer coisa nas 3 portas
    for port in (PORTAL_PORT, BOT_PORT, FRONT_PORT):
        try:
            out = subprocess.check_output(
                ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                text=True,
            ).strip()
            if out:
                for pid_str in out.split("\n"):
                    pid = int(pid_str)
                    print(f"  ✓ porta {port} (pid {pid}) derrubada")
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
        except subprocess.CalledProcessError:
            pass
    return 0


def cmd_status() -> int:
    print("▶ Status dos servers:\n")
    for nome, port in (
        ("portal", PORTAL_PORT), ("bot", BOT_PORT),
        ("frontend", FRONT_PORT),
    ):
        pid = _read_pid(nome)
        alive = pid is not None and _alive(pid)
        listening = _wait_listening(port, timeout=1)
        status = "✓ rodando" if (alive and listening) else "✗ não está rodando"
        print(f"  {nome:<10s} :{port}   {status}   pid={pid or '-'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stop", action="store_true", help="Derruba os 3")
    p.add_argument("--status", action="store_true", help="Mostra estado")
    args = p.parse_args()
    if args.stop:
        return cmd_stop()
    if args.status:
        return cmd_status()
    return cmd_up()


if __name__ == "__main__":
    sys.exit(main())
