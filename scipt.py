#!/usr/bin/env python3
"""
Zendesk → Shopify Order Note Sync (Append Mode)

Given a Zendesk ticket ID, this script:
  1. Fetches the latest private (internal) comment from the ticket.
  2. Extracts a Shopify order name like "A273302" from the comment body.
  3. Looks up that order in Shopify by `name`.
  4. Appends a formatted block to the Shopify order's `note` field:

     #<TICKET_ID> | <AGENT_NAME> | <DATE>

     <NOTE_TEXT>

     ---

Environment variables required:
  ZENDESK_SUBDOMAIN   (e.g. "aleena")
  ZENDESK_EMAIL       (e.g. "you@company.com")
  ZENDESK_API_TOKEN   (Zendesk API token)

  SHOPIFY_STORE       (e.g. "shopaleena" without .myshopify.com)
  SHOPIFY_ADMIN_TOKEN (Admin API access token)

Usage:
  python zendesk_to_shopify_note_sync.py 123456
"""

import os
import sys
import re
import requests
from datetime import datetime, timezone

# ===== Configuration from environment =====

ZENDESK_SUBDOMAIN   = os.getenv("ZENDESK_SUBDOMAIN", "")
ZENDESK_EMAIL       = os.getenv("ZENDESK_EMAIL", "")
ZENDESK_API_TOKEN   = os.getenv("ZENDESK_API_TOKEN", "")

SHOPIFY_STORE       = os.getenv("SHOPIFY_STORE", "")
SHOPIFY_ADMIN_TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN", "")

# Shopify API version – adjust if needed
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2024-01")


# ===== Helpers =====

def fail(msg, code=1):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def check_config():
    missing = []
    if not ZENDESK_SUBDOMAIN:   missing.append("ZENDESK_SUBDOMAIN")
    if not ZENDESK_EMAIL:       missing.append("ZENDESK_EMAIL")
    if not ZENDESK_API_TOKEN:   missing.append("ZENDESK_API_TOKEN")
    if not SHOPIFY_STORE:       missing.append("SHOPIFY_STORE")
    if not SHOPIFY_ADMIN_TOKEN: missing.append("SHOPIFY_ADMIN_TOKEN")

    if missing:
        fail("Missing environment variables: " + ", ".join(missing))


def zendesk_request(method, path, params=None):
    base = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"
    url = base + path
    auth = (f"{ZENDESK_EMAIL}/token", ZENDESK_API_TOKEN)
    headers = {"Content-Type": "application/json"}

    resp = requests.request(method, url, auth=auth, headers=headers, params=params)
    if not resp.ok:
        fail(f"Zendesk API {method} {path} failed: {resp.status_code} {resp.text}")
    return resp.json()


def shopify_request(method, path, json=None, params=None):
    base = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}"
    url = base + path
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ADMIN_TOKEN,
    }
    resp = requests.request(method, url, headers=headers, json=json, params=params)
    if not resp.ok:
        fail(f"Shopify API {method} {path} failed: {resp.status_code} {resp.text}")
    return resp.json()


# ===== Core logic =====

def get_latest_private_comment(ticket_id):
    """
    Return (comment, created_at_iso) for the latest private comment, or (None, None).
    """
    data = zendesk_request("GET", f"/tickets/{ticket_id}/comments.json", params={"sort_order": "desc"})
    comments = data.get("comments", [])
    for c in comments:
        if not c.get("public", True):
            # First private comment in desc order = latest private
            return c, c.get("created_at")
    return None, None


def get_zendesk_user_name(user_id):
    data = zendesk_request("GET", f"/users/{user_id}.json")
    user = data.get("user", {})
    return user.get("name") or f"User {user_id}"


def extract_shopify_order_name(note_text):
    """
    Extract order name like 'A273302' from the note text.
    Adjust regex if your format is different.
    """
    # Example Aleena format: A + 6 digits
    match = re.search(r"\bA\d{6}\b", note_text)
    if not match:
        return None
    return match.group(0)


def find_shopify_order_by_name(order_name):
    """
    Find Shopify order by its name (e.g. 'A273302').
    Returns the order dict or None.
    """
    data = shopify_request("GET", "/orders.json", params={"name": order_name})
    orders = data.get("orders", [])
    if not orders:
        return None
    return orders[0]


def build_note_block(ticket_id, agent_name, created_at, note_body):
    """
    Build the formatted block to append to Shopify.
    created_at is ISO string from Zendesk.
    """
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)

    date_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"#{ticket_id} | {agent_name} | {date_str}"
    block = f"{header}\n\n{note_body.strip()}\n\n---\n"
    return block


def append_note_to_shopify_order(order, note_block, dry_run=False):
    """
    Append note_block to the existing order.note.
    """
    order_id = order["id"]
    existing_note = order.get("note") or ""
    if existing_note.strip():
        new_note = existing_note.rstrip() + "\n\n" + note_block
    else:
        new_note = note_block

    if dry_run:
        print("[DRY RUN] Would update order note:")
        print("================================================")
        print(new_note)
        print("================================================")
        return

    payload = {
        "order": {
            "id": order_id,
            "note": new_note
        }
    }
    shopify_request("PUT", f"/orders/{order_id}.json", json=payload)
    print(f"[OK] Updated Shopify order {order.get('name')} (ID {order_id}) note.")


def sync_ticket_to_shopify_note(ticket_id, dry_run=False):
    print(f"[INFO] Syncing Zendesk ticket {ticket_id} → Shopify order note")

    # 1) Latest private comment
    comment, created_at = get_latest_private_comment(ticket_id)
    if not comment:
        fail(f"No private comments found for ticket {ticket_id}")

    note_body = comment.get("body", "").strip()
    if not note_body:
        fail("Latest private comment has empty body")

    author_id = comment.get("author_id")
    agent_name = get_zendesk_user_name(author_id)
    print(f"[INFO] Latest private comment by: {agent_name}")

    # 2) Extract order name
    order_name = extract_shopify_order_name(note_body)
    if not order_name:
        fail("Could not find order name like 'A123456' in the private note")

    print(f"[INFO] Detected Shopify order name: {order_name}")

    # 3) Find Shopify order
    order = find_shopify_order_by_name(order_name)
    if not order:
        fail(f"Shopify order with name {order_name} not found")

    print(f"[INFO] Found Shopify order ID: {order['id']}")

    # 4) Build block and append
    note_block = build_note_block(ticket_id, agent_name, created_at, note_body)
    append_note_to_shopify_order(order, note_block, dry_run=dry_run)


# ===== CLI entrypoint =====

def main():
    check_config()

    if len(sys.argv) < 2:
        print("Usage: python zendesk_to_shopify_note_sync.py <ticket_id> [--dry-run]")
        sys.exit(1)

    ticket_id = sys.argv[1]
    dry_run = "--dry-run" in sys.argv[2:]

    sync_ticket_to_shopify_note(ticket_id, dry_run=dry_run)


if __name__ == "__main__":
    main()
