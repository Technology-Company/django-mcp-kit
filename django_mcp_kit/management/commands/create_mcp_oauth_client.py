"""Create or update the OAuth client (DOT ``Application``) for an MCP connector.

Idempotent: re-running with the same ``--name`` updates the existing client. Defaults
to a public + PKCE client (what browser/native clients such as claude.ai use).

    python manage.py create_mcp_oauth_client https://claude.ai/api/mcp/auth_callback
    python manage.py create_mcp_oauth_client https://app/cb --name "My connector" --skip-consent
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from ...oauth_client import ensure_oauth_application


class Command(BaseCommand):
    help = "Create/update the OAuth client (DOT Application) for an MCP connector."

    def add_arguments(self, parser):
        parser.add_argument("redirect_uri", nargs="+", help="Allowed redirect URI(s).")
        parser.add_argument(
            "--name", default=None,
            help="Client name shown on the consent page "
                 "(default: DJANGO_MCP_KIT['OAUTH_APP_NAME']).")
        parser.add_argument(
            "--confidential", action="store_true",
            help="Confidential client with a secret (default: public + PKCE).")
        parser.add_argument(
            "--skip-consent", action="store_true",
            help="Auto-approve authorization (skip the consent page).")

    def handle(self, *args, **options):
        app, created = ensure_oauth_application(
            " ".join(options["redirect_uri"]),
            name=options["name"],
            public=not options["confidential"],
            skip_authorization=options["skip_consent"],
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} OAuth client {app.name!r}"))
        self.stdout.write(f"  Client ID:  {app.client_id}")
        if options["confidential"]:
            self.stdout.write(f"  Client secret: {app.client_secret}  (copy now; it is hashed at rest)")
        else:
            self.stdout.write("  Public client (PKCE) — no client secret.")
        self.stdout.write(
            f"  Consent: {'auto-approved' if options['skip_consent'] else 'prompted on first authorization'}")
