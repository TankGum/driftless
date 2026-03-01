"""CLI provisioning script — spin up a new company container.

Usage:
    python scripts/provision.py \\
        --company "Công ty A" \\
        --subdomain cong-ty-a \\
        --token <BOT_TOKEN> \\
        --admin-username admin \\
        --admin-password secretpass \\
        --admin-telegram-id 123456

Requirements:
    - Docker + docker compose installed
    - nginx running on the host
    - .env file with SUPABASE_URL, SUPABASE_KEY, CLAUDE_API_KEY present
    - credentials.json present in project root
"""
import argparse
import os
import re
import secrets
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

import bcrypt

# Project root (one level up from scripts/)
ROOT = Path(__file__).parent.parent


def _slugify(text: str) -> str:
    """Convert Vietnamese/Unicode company name to ASCII slug."""
    import unicodedata
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text


def _generate_company_id(name: str) -> str:
    slug = _slugify(name)
    return slug[:40] if slug else "company"


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def _is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _find_free_port(start: int = 8100) -> int:
    port = start
    while not _is_port_free(port):
        port += 1
    return port


def _find_used_ports() -> set[int]:
    """Find ports already registered in Supabase companies table."""
    try:
        sys.path.insert(0, str(ROOT))
        from database.supabase import supabase
        result = supabase.table("companies").select("container_port").execute()
        return {row["container_port"] for row in result.data if row.get("container_port")}
    except Exception:
        return set()


def _read_env_value(key: str) -> str:
    """Read a value from the project .env file."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def _create_deployment_files(
    subdomain: str,
    company_id: str,
    token: str,
    port: int,
    auth_secret: str,
) -> Path:
    """Create deployments/{subdomain}/.env and docker-compose.yml."""
    deploy_dir = ROOT / "deployments" / subdomain
    deploy_dir.mkdir(parents=True, exist_ok=True)

    # .env from template
    template = (ROOT / ".env.template").read_text()
    env_content = template.replace("{{TELEGRAM_TOKEN}}", token)
    env_content = env_content.replace("{{SUPABASE_URL}}", _read_env_value("SUPABASE_URL"))
    env_content = env_content.replace("{{SUPABASE_KEY}}", _read_env_value("SUPABASE_KEY"))
    env_content = env_content.replace("{{CLAUDE_API_KEY}}", _read_env_value("CLAUDE_API_KEY"))
    env_content = env_content.replace("{{COMPANY_ID}}", company_id)
    env_content = env_content.replace("{{AUTH_SECRET}}", auth_secret)
    env_content = env_content.replace("{{PORT}}", str(port))
    (deploy_dir / ".env").write_text(env_content)

    # docker-compose.yml
    compose = textwrap.dedent(f"""\
        version: "3.9"
        services:
          driftless:
            image: driftless:latest
            container_name: driftless-{subdomain}
            restart: unless-stopped
            ports:
              - "{port}:8000"
            env_file:
              - .env
            volumes:
              - {ROOT}/credentials.json:/app/credentials.json:ro
        """)
    (deploy_dir / "docker-compose.yml").write_text(compose)

    return deploy_dir


def _find_docker_nginx() -> tuple[str, str] | tuple[None, None]:
    """Find a running nginx Docker container and its conf.d volume name.

    Returns (container_name, volume_name) or (None, None) if not found.
    """
    import json

    ps = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
        capture_output=True, text=True,
    )
    if ps.returncode != 0:
        return None, None

    container = None
    for line in ps.stdout.splitlines():
        # Match host port 80 (format: "0.0.0.0:80->..." or "[::]:80->...")
        if ":80->" in line:
            container = line.split("\t")[0]
            break

    if not container:
        return None, None

    inspect = subprocess.run(
        ["docker", "inspect", container, "--format", "{{json .Mounts}}"],
        capture_output=True, text=True,
    )
    if inspect.returncode != 0:
        return container, None

    mounts = json.loads(inspect.stdout)
    volume = next(
        (m["Name"] for m in mounts
         if m.get("Destination") == "/etc/nginx/conf.d" and m.get("Type") == "volume"),
        None,
    )
    return container, volume


def _write_nginx_conf(subdomain: str, port: int, base_domain: str = "driftless.vn") -> None:
    """Write nginx vhost config and reload nginx.

    Supports two modes:
    - Host nginx: writes directly to the conf.d directory on the host.
    - Docker nginx: writes to the Docker volume via a temporary alpine container.
    """
    server_name = f"{subdomain}.{base_domain}"
    template = (ROOT / "nginx" / "template.conf").read_text()

    # --- Mode 1: Host nginx ---
    candidates = [
        Path("/etc/nginx/conf.d"),
        Path("/usr/local/etc/nginx/servers"),
        Path("/opt/homebrew/etc/nginx/servers"),
    ]
    conf_dir = next((p for p in candidates if p.exists()), None)
    if conf_dir is not None:
        conf = (template
                .replace("{{SERVER_NAME}}", server_name)
                .replace("{{PORT}}", str(port))
                .replace("{{PROXY_HOST}}", "127.0.0.1"))
        conf_path = conf_dir / f"{subdomain}.conf"
        try:
            conf_path.write_text(conf)
            subprocess.run(["nginx", "-s", "reload"], check=True)
            print(f"  nginx config written → {conf_path}")
            return
        except PermissionError:
            print(f"  [WARN] No permission to write {conf_path}. Trying Docker nginx...")
        except subprocess.CalledProcessError as e:
            print(f"  [WARN] nginx reload failed: {e}")
            return

    # --- Mode 2: Docker nginx ---
    # Company containers expose ports on the host; nginx container reaches them via host.docker.internal
    nginx_container, conf_volume = _find_docker_nginx()
    if nginx_container and conf_volume:
        conf = (template
                .replace("{{SERVER_NAME}}", server_name)
                .replace("{{PORT}}", str(port))
                .replace("{{PROXY_HOST}}", "host.docker.internal"))
        # Write config to the volume via a temporary nginx:alpine container (volume is RW from outside)
        write_result = subprocess.run(
            ["docker", "run", "--rm", "-i",
             "-v", f"{conf_volume}:/conf",
             "nginx:alpine", "sh", "-c", f"cat > /conf/{subdomain}.conf"],
            input=conf, text=True, capture_output=True,
        )
        if write_result.returncode != 0:
            print(f"  [WARN] Failed to write to Docker volume: {write_result.stderr}")
            print("  Write this config manually:\n")
            print(conf)
            return
        reload_result = subprocess.run(
            ["docker", "exec", nginx_container, "nginx", "-s", "reload"],
            capture_output=True, text=True,
        )
        if reload_result.returncode != 0:
            print(f"  [WARN] nginx reload failed: {reload_result.stderr}")
        else:
            print(f"  nginx config written to volume '{conf_volume}' → reloaded '{nginx_container}'")
        return

    fallback_conf = (template
                     .replace("{{SERVER_NAME}}", server_name)
                     .replace("{{PORT}}", str(port))
                     .replace("{{PROXY_HOST}}", "127.0.0.1"))
    print("  [WARN] No nginx found (host or Docker). Write this config manually:\n")
    print(fallback_conf)


def provision(
    company_name: str,
    subdomain: str,
    token: str,
    admin_username: str,
    admin_password: str,
    admin_telegram_id: int,
    force: bool = False,
    base_domain: str = "driftless.vn",
) -> None:
    sys.path.insert(0, str(ROOT))
    from database.supabase import supabase

    # 1. Validate — subdomain must be unique
    existing = supabase.table("companies").select("company_id").eq("subdomain", subdomain).execute()
    if existing.data:
        if not force:
            print(f"[ERROR] Subdomain '{subdomain}' already in use. Use --force to overwrite.")
            sys.exit(1)
        old_company_id = existing.data[0]["company_id"]
        print(f"  [FORCE] Removing existing company '{old_company_id}' and its users...")
        supabase.table("users").delete().eq("company_id", old_company_id).execute()
        supabase.table("companies").delete().eq("company_id", old_company_id).execute()
        # Stop existing container — try compose down first (clean), then force-remove by name
        old_deploy_dir = ROOT / "deployments" / subdomain
        if (old_deploy_dir / "docker-compose.yml").exists():
            subprocess.run(
                ["docker", "compose", "-f", str(old_deploy_dir / "docker-compose.yml"), "down", "--remove-orphans"],
                capture_output=True,
            )
        subprocess.run(
            ["docker", "rm", "-f", f"driftless-{subdomain}"],
            capture_output=True,
        )

    # 2. Generate company_id
    company_id = _generate_company_id(company_name)
    # Ensure uniqueness
    check = supabase.table("companies").select("company_id").eq("company_id", company_id).execute()
    if check.data:
        company_id = f"{company_id}-{secrets.token_hex(3)}"

    # 3. Find free port (skip ports already in DB)
    used_ports = _find_used_ports()
    port = _find_free_port(8100)
    while port in used_ports:
        port += 1

    print(f"\nProvisioning company: {company_name}")
    print(f"  company_id : {company_id}")
    print(f"  subdomain  : {subdomain}")
    print(f"  port       : {port}")

    # 4. Insert company into Supabase
    supabase.table("companies").insert({
        "company_id": company_id,
        "name": company_name,
        "plan": "trial",
        "subdomain": subdomain,
        "container_name": f"driftless-{subdomain}",
        "container_port": port,
        "is_active": True,
    }).execute()
    print(f"  [DB] Company '{company_id}' created.")

    # 5. Insert admin user
    password_hash = _hash_password(admin_password)
    supabase.table("users").insert({
        "username": admin_username,
        "full_name": admin_username,
        "role": "admin",
        "company_id": company_id,
        "password_hash": password_hash,
        "telegram_id": admin_telegram_id if admin_telegram_id else None,
    }).execute()
    print(f"  [DB] Admin user '{admin_username}' created.")

    # 6 & 7. Create deployment files
    auth_secret = secrets.token_hex(32)
    deploy_dir = _create_deployment_files(subdomain, company_id, token, port, auth_secret)
    print(f"  [FILES] Deployment files written to {deploy_dir}")

    # 8. Start Docker container
    compose_path = deploy_dir / "docker-compose.yml"
    print("  [DOCKER] Building and starting container...")
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "up", "-d"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [WARN] docker compose failed:\n{result.stderr}")
    else:
        print("  [DOCKER] Container started.")

    # 9 & 10. Write nginx config and reload
    _write_nginx_conf(subdomain, port, base_domain)

    # 11. Summary
    print(f"""
✅ Provisioning complete!

  WebUI URL  : http://{subdomain}.{base_domain}
  Admin login: {admin_username} / (your password)
  Trial plan : 7 ngày / 50 queries

Để nâng cấp Pro:
  python scripts/upgrade_to_pro.py --company-id {company_id} --months 12
""")


def main():
    parser = argparse.ArgumentParser(description="Provision a new Driftless company instance")
    parser.add_argument("--company", required=True, help="Company display name")
    parser.add_argument("--subdomain", required=True, help="Subdomain slug (e.g. cong-ty-a)")
    parser.add_argument("--token", required=True, help="Telegram Bot Token")
    parser.add_argument("--admin-username", required=True, help="Admin WebUI username")
    parser.add_argument("--admin-password", required=True, help="Admin WebUI password (min 8 chars)")
    parser.add_argument("--admin-telegram-id", type=int, default=0, help="Admin Telegram user ID")
    parser.add_argument("--force", action="store_true", help="Overwrite existing subdomain (for re-provisioning)")
    parser.add_argument("--base-domain", default="driftless.vn",
                        help="Base domain (default: driftless.vn). Use lvh.me for local testing.")

    args = parser.parse_args()

    if len(args.admin_password) < 8:
        print("[ERROR] Admin password must be at least 8 characters.")
        sys.exit(1)

    subdomain = _slugify(args.subdomain)
    if not subdomain:
        print("[ERROR] Invalid subdomain.")
        sys.exit(1)

    provision(
        company_name=args.company,
        subdomain=subdomain,
        token=args.token,
        admin_username=args.admin_username,
        admin_password=args.admin_password,
        admin_telegram_id=args.admin_telegram_id,
        force=args.force,
        base_domain=args.base_domain,
    )


if __name__ == "__main__":
    main()
