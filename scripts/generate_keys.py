#!/usr/bin/env python3
"""生成 JWT 签名密钥和 ServiceAccount 凭证。

用法:
    python scripts/generate_keys.py
    python scripts/generate_keys.py --client-id partner-acme
"""

import argparse
import secrets
import string


def generate_jwt_secret(length=32) -> str:
    return secrets.token_hex(length)


def generate_secret(length=24) -> str:
    chars = string.ascii_letters + string.digits
    return "sk-" + "".join(secrets.choice(chars) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(description="生成 JWT 密钥和 ServiceAccount 凭证")
    parser.add_argument("--client-id", default="", help="合作方 client_id（可选）")
    args = parser.parse_args()

    print("=" * 60)
    print("JWT_SECRET_KEY（粘贴到 .env）:")
    print("=" * 60)
    print(generate_jwt_secret())
    print()

    if args.client_id:
        secret = generate_secret()
        print("=" * 60)
        print("SERVICE_ACCOUNTS（粘贴到 .env，多个用逗号分隔）:")
        print("=" * 60)
        print(f"{args.client_id}:{secret}")
        print()
        print("=" * 60)
        print("发给合作方:")
        print("=" * 60)
        print(f"  client_id: {args.client_id}")
        print(f"  secret:    {secret}")


if __name__ == "__main__":
    main()
