#!/usr/bin/env python3
"""Codifica o serviceAccount.json em base64 para uso em Vercel."""

import json
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVICE_ACCOUNT_PATH = ROOT / "serviceAccount.json"

if not SERVICE_ACCOUNT_PATH.exists():
    print(f"Erro: {SERVICE_ACCOUNT_PATH} não encontrado.")
    sys.exit(1)

with open(SERVICE_ACCOUNT_PATH, 'r') as f:
    json_str = f.read()

encoded = base64.b64encode(json_str.encode()).decode()

print("=" * 70)
print("FIREBASE_CREDENTIALS_JSON para Vercel:")
print("=" * 70)
print(encoded)
print("=" * 70)
print("\nCopie o valor acima e defina em:")
print("Vercel Dashboard → Project Settings → Environment Variables")
print("Variável: FIREBASE_CREDENTIALS_JSON")
print("\nVerifique o tamanho:")
print(f"Comprimento: {len(encoded)} caracteres")
