"""Manage the remote sudo password in Windows Credential Manager.

Usage: py credentials.py set hermes-server
       py credentials.py status hermes-server
       py credentials.py delete hermes-server
"""

import argparse
from getpass import getpass
import platform

import keyring

SERVICE = "hermes-setup-mcp-sudo"


def main():
    if platform.system() != "Windows":
        raise SystemExit("Run credentials.py in native Windows Python (not WSL).")
    from keyring.backends.Windows import WinVaultKeyring
    keyring.set_keyring(WinVaultKeyring())
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("set", "status", "delete"))
    parser.add_argument("host", help="Exact host alias in hosts.json")
    args = parser.parse_args()

    if args.action == "set":
        password = getpass(f"sudo password for {args.host} (input hidden): ")
        if not password or "\n" in password or "\r" in password:
            raise SystemExit("Empty password or newline not allowed")
        keyring.set_password(SERVICE, args.host, password)
        print("Credential stored for this Windows user. Password not printed.")
    elif args.action == "status":
        print("configured" if keyring.get_password(SERVICE, args.host) is not None else "missing")
    elif args.action == "delete":
        keyring.delete_password(SERVICE, args.host)
        print("Credential deleted")


if __name__ == "__main__":
    main()
