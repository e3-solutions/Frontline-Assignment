#!/usr/bin/env python3
"""Initialize or seed a disposable, local Supabase database.

Historical migrations remain unchanged. This installer supplies the missing
transition steps needed to replay them into an empty candidate sandbox.
"""

import argparse
import getpass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
ORG_ID = "00000000-0000-4000-8000-000000000001"


def run_sql(sql, args, password, *, capture=False):
    # Do not inherit PGHOSTADDR, PGSERVICE, PGOPTIONS, or other connection
    # overrides. No remote host/URL option is accepted by this installer.
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    env["PGPASSWORD"] = password
    env["PGCONNECT_TIMEOUT"] = "5"
    result = subprocess.run(
        ["psql", "-X", "-w", "-h", "127.0.0.1", "-p", str(args.port),
         "-U", "postgres", "-d", args.database, "-v", "ON_ERROR_STOP=1", "-At"],
        input=sql, text=True, env=env, capture_output=True,
    )
    if result.returncode:
        # SQL and connection strings contain no credentials; the password is
        # supplied only through the subprocess environment.
        raise RuntimeError(result.stderr.strip() or "psql failed")
    if capture:
        return result.stdout.strip()


def check_supabase(args, password):
    found = run_sql("""
        SELECT to_regclass('auth.users') IS NOT NULL
          AND to_regprocedure('auth.uid()') IS NOT NULL
          AND (SELECT count(*) = 3 FROM pg_roles
               WHERE rolname IN ('anon', 'authenticated', 'service_role'));
    """, args, password, capture=True)
    if found != "t":
        raise RuntimeError("Start a fresh local Supabase stack first; Auth tables/functions and API roles are required.")


def initialize(args, password):
    check_supabase(args, password)
    # Extension-owned objects (e.g. PostGIS spatial_ref_sys) may already exist.
    existing = run_sql("""
        SELECT c.relname AS name FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
          AND NOT EXISTS (SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                AND d.deptype = 'e')
        UNION ALL
        SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND NOT EXISTS (SELECT 1 FROM pg_depend d
            WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e')
        UNION ALL
        SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd')
          AND NOT EXISTS (SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid AND d.deptype = 'e');
    """, args, password, capture=True)
    if existing:
        raise RuntimeError("Refusing to initialize a nonempty public schema. Use a new disposable local stack.")

    files = sorted(
        list((ROOT / "web/supabase/migrations").glob("*.sql"))
        + list((ROOT / "supabase/migrations").glob("*.sql")),
        key=lambda path: path.name,
    )
    if len(files) != 40 or len({path.name for path in files}) != len(files):
        raise RuntimeError("Expected the 40 supplied migrations; review the installer before changing the migration set.")

    for path in files:
        if path.name.startswith("20260415000000_"):
            # PostgreSQL cannot change UUID load_id columns while the old
            # org-isolation policies depend on them. Replace those policies
            # below using call ownership, which survives the load transition.
            run_sql("""
                DROP POLICY org_isolation_select ON public.calls;
                DROP POLICY org_isolation_select ON public.negotiations;
            """, args, password)
        if path.name.startswith("20260430000000_"):
            # The final contract expects a separate load-number-keyed catalog.
            # Retain the empty historical table and release its PK index name
            # before the final migration's CREATE TABLE loads statement.
            run_sql("""
                ALTER TABLE public.loads RENAME TO loads_legacy;
                ALTER TABLE public.loads_legacy
                    RENAME CONSTRAINT loads_pkey TO loads_legacy_pkey;
            """, args, password)
        print(f"Applying {path.name}", flush=True)
        run_sql(path.read_text(), args, password)

    run_sql((ROOT / "scripts/local_database_access.sql").read_text(), args, password)
    print("Local candidate schema initialized. Run the seed command next.")


def seed(args, password):
    check_supabase(args, password)
    # The known marker is a policy created only by this local installer.
    marker = run_sql("""
        SELECT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
          AND tablename = 'loads' AND policyname = 'local_candidate_catalog_select');
    """, args, password, capture=True)
    if marker != "t":
        raise RuntimeError("Refusing to seed a database that was not initialized by this local installer.")
    for value in (args.phone_number, args.transfer_phone):
        if value is None:
            continue
        if not re.fullmatch(r"\+[0-9]{7,15}", value):
            raise RuntimeError("Phone numbers must use E.164 form, such as +12025550100.")
    user_id = str(UUID(args.auth_user_id)) if args.auth_user_id else None
    if user_id:
        exists = run_sql(f"SELECT EXISTS (SELECT 1 FROM auth.users WHERE id = '{user_id}'::uuid);",
                         args, password, capture=True)
        if exists != "t":
            raise RuntimeError("The Auth user does not exist. Create a local user in Supabase Studio first.")
        profile = run_sql(f"SELECT org_id FROM public.users WHERE user_id = '{user_id}'::uuid;",
                          args, password, capture=True)
        if profile and profile != ORG_ID:
            raise RuntimeError("The Auth user already belongs to a different organization; use a fresh local user.")
    sql = (ROOT / "scripts/local_database_seed.sql").read_text()
    # Values are fixed UUIDs or strictly validated E.164 numbers, never SQL.
    sql = sql.replace("__PHONE_NUMBER__", args.phone_number)
    sql = sql.replace("__TRANSFER_PHONE__", args.transfer_phone or "+12025550101")
    sql = sql.replace("__TRANSFER_UPDATE_PHONE__", f"'{args.transfer_phone}'" if args.transfer_phone else "NULL")
    if user_id:
        sql += f"""
            INSERT INTO public.users (user_id, full_name, org_id, role)
            VALUES ('{user_id}', 'Candidate Admin', '{ORG_ID}', 'admin')
            ON CONFLICT (user_id) DO NOTHING;
        """
    run_sql("BEGIN;\n" + sql + "\nCOMMIT;", args, password)
    print(f"Seeded Candidate Sandbox ({ORG_ID}), phone {args.phone_number}, load DEMO-1001 and two stops.")
    if user_id:
        print("Linked the existing local Auth user to the candidate organization.")
    else:
        print("No Auth user was created. Use seed --auth-user-id UUID after creating one in local Studio.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "seed"))
    parser.add_argument("--port", type=int, default=54322, help="Local Supabase database port (host is always 127.0.0.1)")
    parser.add_argument("--database", default="postgres", help="Name of the disposable local database")
    parser.add_argument("--password-stdin", action="store_true", help="Read the local password from stdin instead of prompting")
    parser.add_argument("--auth-user-id", help="Existing local Supabase Auth UUID to link during seed")
    parser.add_argument("--phone-number", default="+12025550100", help="Local seed's incoming bot number (replace with your development LiveKit SIP number)")
    parser.add_argument("--transfer-phone", help="Set the sample load's transfer destination; omitted values preserve existing routing")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if not re.fullmatch(r"[A-Za-z0-9_]+", args.database):
        parser.error("database must be a plain local database name")
    if args.action == "init" and args.auth_user_id:
        parser.error("--auth-user-id is only used with seed")
    if not shutil.which("psql"):
        parser.error("psql is required; install the PostgreSQL client")
    password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("Local database password (Supabase default: postgres): ")
    try:
        (initialize if args.action == "init" else seed)(args, password)
    except (RuntimeError, ValueError) as error:
        print(f"Setup stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
