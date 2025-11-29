# Zendesk → Shopify Order Note Sync

A simple bridge that syncs **Zendesk internal notes** into a **Shopify order’s note field** —
automatically or on demand.

This tool lets your support team write private comments inside Zendesk (e.g., handling customer
updates, delivery notes, Ops instructions), and those notes get appended to the corresponding
Shopify order in a clean, structured format.

## 🚀 What This Script Does

Given a **Zendesk ticket ID** , the script:

1. Fetches the **latest internal/private note** from the ticket
2. Pulls the **agent name** and comment timestamp
3. Extracts the **Shopify order number** (e.g., A273302) from the note body
4. Finds the Shopify order by its name
5. **Appends** a formatted block to the order’s note field:

#### #<TICKET_ID> | <AGENT_NAME> | <DATE>

#### <NOTE_TEXT>

#### ---

This preserves existing notes, keeps everything chronological, and gives Ops/Finance/Delivery
teams a clean unified view of what happened.

## 🗂 Requirements


```
● Python 3.8+
● Access to Zendesk API (email + API token)
● Shopify Admin API access token (Admin API scopes: write_orders)
● Internet access from the environment running the script
```
## 🔧 Environment Variables

Set the following environment variables before using the script:

### Zendesk

```
Variable Description
ZENDESK_SUBDO
MAIN
Your Zendesk subdomain (example: aleena)
ZENDESK_EMAIL Agent/system^ email^ used^ for^ Zendesk^ API^
ZENDESK_API_TOKEN
Zendesk API token
```
### Shopify

```
Variable Description
SHOPIFY_STORE Shopify^ store^ name^ (without.myshopify.com)
SHOPIFY_ADMIN_TOKEN Admin^ API^ access^ token^
SHOPIFY_API_VERSION (optional)
Defaults to 2024-
```
Example:

export ZENDESK_SUBDOMAIN="aleena"
export ZENDESK_EMAIL="you@company.com"


export ZENDESK_API_TOKEN="xxxx"

export SHOPIFY_STORE="shopaleena"
export SHOPIFY_ADMIN_TOKEN="shpat_xxxx"

## ▶ Usage

### Dry run (recommended first)

Preview the final Shopify note content without updating the order:

python zendesk_to_shopify_note_sync.py 123456 --dry-run

### Actual sync

Updates Shopify:

python zendesk_to_shopify_note_sync.py 123456

## 🧠 How the Script Finds the Order

The script looks for order numbers inside the internal note using this pattern:

A

If your order format changes, update the regex here:

r"\bA\d{6}\b"

## 📦 Output Example

If the latest Zendesk private note is:


A273302 Customer wants to delay delivery to Monday and confirm
address.

The Shopify order note becomes:

#123456 | Ahmed Anwar | 2025-11-29 18:10 UTC

Customer wants to delay delivery to Monday and confirm address.

## 🔁 Making It Automatic (Optional)

If you want automatic syncing:

```
● Wrap the script in a small FastAPI/Flask server
● Add a Zendesk Trigger → HTTP Target
● Trigger whenever a Private Comment is added
```
I can generate the full server + instructions if you need it.

## 🧪 Error Handling

The script safely fails with explicit messages for:

```
● Missing env variables
● No internal comments
● No order number found
● Order not found in Shopify
● API errors on either side
```
