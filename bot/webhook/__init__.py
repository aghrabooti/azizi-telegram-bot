"""WSGI webhook runtime (only needed on cPanel/Passenger deployments)."""

from bot.webhook.app import application, create_app, runtime

__all__ = ["application", "create_app", "runtime"]
