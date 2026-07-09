#!/usr/bin/env python3
"""Genera una SECRET_KEY de Django. Pegar en el .env SIN comillas."""
import secrets
import string

chars = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"
print("".join(secrets.choice(chars) for _ in range(50)))
