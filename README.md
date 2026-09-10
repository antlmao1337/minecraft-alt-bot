# Minecraft All-Purpose

A Discord bot focused on Minecraft utilities, account tools, and alt generation.

Supports both **TheAltening** and **Localts**, plus general player and server tools.

---

## Features

- **Alt Generation**
  - TheAltening: generate alts, inspect tokens, check license
  - Localts: balance, products, purchase, order history
  - Skin-based embed colors + head thumbnails (TheAltening)

- **Player Tools**
  - Username → UUID
  - UUID → Username
  - Skin viewer (head + body + download links)
  - Premium / availability check

- **Server Tools**
  - Full server status (players, version, MOTD)
  - Quick ping / online check
  - Common Minecraft & proxy ports reference

- **Clean UI**
  - Consistent embeds with blockquotes (`>`)
  - Organized help menu
  - Slash commands + `!gen` prefix alias

---

## Commands

### TheAltening
| Command | Description |
|---------|-------------|
| `/generate` | Generate a new TheAltening alt |
| `/altinfo <token>` | Inspect an alt token |
| `/license` | Check TheAltening API key / plan status |
| `!gen` | Prefix alias for `/generate` |

### Localts
| Command | Description |
|---------|-------------|
| `/lts_balance` | Check Localts balance |
| `/lts_products` | List available products |
| `/lts_buy` | Purchase a product |
| `/lts_orders` | List your orders |
| `/lts_order` | Get order details / items |

### Players
| Command | Description |
|---------|-------------|
| `/uuid <username>` | Get UUID from username |
| `/username <uuid>` | Get username from UUID |
| `/skin <username>` | View player skin (head + body) |
| `/premium <username>` | Check if a name is premium / taken |

### Servers
| Command | Description |
|---------|-------------|
| `/server <address>` | Full server status |
| `/ping <address>` | Quick online check + player count |
| `/ports` | Common Minecraft-related ports |

### General
| Command | Description |
|---------|-------------|
| `/help` | Show all commands |

---

## Setup

### Requirements
- Python 3.10+
- A Discord bot token
- TheAltening API key (plan with API access)
- Localts API key / credentials (as configured in the bot)

- Localts Implementation was done last minute, so it is very lazy. 
### Installation

```bash
git clone <your-repo-url>
cd <repo-folder>
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install discord.py aiohttp python-dotenv Pillow
