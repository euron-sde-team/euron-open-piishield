"""The ``piishield`` command: serve, migrate and admin tasks in one entry point."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alembic.config import Config

    from piishield.core.config import Settings


def _settings() -> Settings:
    from piishield.core.config import get_settings

    return get_settings()


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "piishield.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        access_log=False,
        log_config=None,
        timeout_graceful_shutdown=30,
    )


def _alembic_config() -> Config:
    from pathlib import Path

    from alembic.config import Config

    # Resolved from the installed package, not a "src/..." relative path: the built
    # Docker image has no src/ tree, only the installed piishield package under
    # /opt/venv, and this must work from any cwd either way.
    migrations_dir = Path(__file__).parent / "migrations"
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", _settings().database_url.replace("+asyncpg", "+psycopg2"))
    return cfg


def _migrate(_: argparse.Namespace) -> None:
    from alembic import command

    command.upgrade(_alembic_config(), "head")
    print("migrations applied")


def _revision(args: argparse.Namespace) -> None:
    from alembic import command

    command.revision(_alembic_config(), message=args.message, autogenerate=True)


def _seed(_: argparse.Namespace) -> None:
    from piishield.demo.seed import run

    asyncio.run(run())


async def _create_admin_async(email: str, org_name: str, password: str) -> None:
    from sqlalchemy import select

    from piishield.core.db import Database, import_all_models
    from piishield.core.security import hash_password, password_problems
    from piishield.orgs.models import User

    if problems := password_problems(password):
        sys.exit("password needs " + ", ".join(problems))
    import_all_models()
    settings = _settings()
    db = Database(settings.database_url, pool_size=1, max_overflow=0)
    try:
        async with db.sessionmaker() as session:
            existing = await session.scalar(select(User).where(User.email == email.lower()))
            if existing is not None:
                existing.role = "owner"
                existing.vault_access = True
                existing.password_hash = hash_password(password)
                existing.disabled = False
                existing.session_version += 1
                await session.commit()
                print(f"updated {email} (owner)")
                return
        async with db.sessionmaker() as session:
            from piishield.auth.service import signup

            await signup(session, org_name, "Owner", email, password)
            print(f"created {email} (owner of {org_name})")
    finally:
        await db.dispose()


def _create_admin(args: argparse.Namespace) -> None:
    import getpass

    password = os.environ.get("PIISHIELD_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    asyncio.run(_create_admin_async(args.email, args.org, password))


def _openapi(_: argparse.Namespace) -> None:
    from piishield.openapi import spec, to_yaml

    sys.stdout.write(to_yaml(spec()))


def _server(
    sub: argparse._SubParsersAction[argparse.ArgumentParser], name: str, fn: object, help_: str
) -> None:
    p = sub.add_parser(name, help=help_)
    p.add_argument("--host", default="0.0.0.0")  # noqa: S104 containers listen on all interfaces
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    p.set_defaults(fn=fn)


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="piishield", description="Euron Open PIIShield")
    sub = parser.add_subparsers(dest="command", required=True)
    _server(sub, "serve", _serve, "the API")
    sub.add_parser("migrate", help="apply database migrations").set_defaults(fn=_migrate)
    p = sub.add_parser("revision", help="autogenerate a migration from the models")
    p.add_argument("-m", "--message", required=True)
    p.set_defaults(fn=_revision)
    sub.add_parser(
        "seed-demo", help="a demo company with projects, policies and findings"
    ).set_defaults(fn=_seed)
    sub.add_parser("openapi", help="print the OpenAPI document as YAML").set_defaults(fn=_openapi)
    p = sub.add_parser("create-admin", help="create an organization and its owner, or reset one")
    p.add_argument("--email", required=True)
    p.add_argument("--org", default="My Company")
    p.set_defaults(fn=_create_admin)
    args = parser.parse_args(argv)
    args.fn(args)
