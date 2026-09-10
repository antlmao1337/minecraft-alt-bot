import os
import io
import asyncio
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ALTENING_API_KEY = os.getenv("ALTENING_API_KEY")
LOCALTS_API_KEY = os.getenv("LOCALTS_API_KEY")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

LOCALTS_BASE = "https://localts.store"

# Helpers – TheAltening

async def generate_alt(session: aiohttp.ClientSession) -> dict:
    url = f"https://api.thealtening.com/v2/generate?key={ALTENING_API_KEY}&info=true"
    async with session.get(url, timeout=15) as resp:
        resp.raise_for_status()
        return await resp.json()

async def get_license(session: aiohttp.ClientSession) -> dict:
    url = f"https://api.thealtening.com/v2/license?key={ALTENING_API_KEY}"
    async with session.get(url, timeout=10) as resp:
        resp.raise_for_status()
        return await resp.json()

async def get_token_info(session: aiohttp.ClientSession, token: str) -> dict:
    url = f"https://api.thealtening.com/v2/info?key={ALTENING_API_KEY}&token={token}"
    async with session.get(url, timeout=10) as resp:
        resp.raise_for_status()
        return await resp.json()

async def authenticate_token(session: aiohttp.ClientSession, token: str) -> dict | None:
    payload = {
        "agent": {"name": "Minecraft", "version": 1},
        "username": token,
        "password": "anything",
        "requestUser": True,
    }
    try:
        async with session.post(
            "http://authserver.thealtening.com/authenticate",
            json=payload,
            timeout=10,
        ) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception:
        return None

def dominant_color_from_bytes(image_bytes: bytes) -> int:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        pixels = list(img.getdata())
        opaque = [(r, g, b) for r, g, b, a in pixels if a > 128]
        if not opaque:
            return 0x2B2D31
        r = sum(p[0] for p in opaque) // len(opaque)
        g = sum(p[1] for p in opaque) // len(opaque)
        b = sum(p[2] for p in opaque) // len(opaque)
        return (r << 16) + (g << 8) + b
    except Exception:
        return 0x2B2D31

async def get_skin_color(session: aiohttp.ClientSession, skin_hash: str | None) -> int:
    if not skin_hash:
        return 0x2B2D31
    url = f"https://cdn.thealtening.com/skins/body/{skin_hash}.png"
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return 0x2B2D31
            data = await resp.read()
            return await asyncio.to_thread(dominant_color_from_bytes, data)
    except Exception:
        return 0x2B2D31

# Helpers – Localts

def localts_headers() -> dict:
    return {"X-API-Key": LOCALTS_API_KEY} if LOCALTS_API_KEY else {}

async def localts_me(session: aiohttp.ClientSession) -> dict:
    async with session.get(
        f"{LOCALTS_BASE}/v1/me",
        headers=localts_headers(),
        timeout=10,
    ) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)

async def localts_products(session: aiohttp.ClientSession) -> dict:
    async with session.get(
        f"{LOCALTS_BASE}/v1/products",
        timeout=15,
    ) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)

async def localts_purchase(
    session: aiohttp.ClientSession, product_id: str, amount: int = 1
) -> dict:
    url = f"{LOCALTS_BASE}/v1/products/{product_id}/purchase?amount={amount}"
    async with session.post(
        url,
        headers=localts_headers(),
        timeout=20,
    ) as resp:
        data = await resp.json(content_type=None)
        if resp.status == 401:
            raise aiohttp.ClientResponseError(
                resp.request_info, resp.history, status=401, message="Unauthorized"
            )
        return data

async def localts_orders(
    session: aiohttp.ClientSession, page: int = 0, size: int = 25
) -> dict:
    url = f"{LOCALTS_BASE}/v1/orders?page={page}&size={size}"
    async with session.get(
        url,
        headers=localts_headers(),
        timeout=10,
    ) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)

async def localts_get_order(session: aiohttp.ClientSession, order_id: str) -> dict:
    url = f"{LOCALTS_BASE}/v1/orders/get-order?id={order_id}"
    async with session.get(
        url,
        headers=localts_headers(),
        timeout=10,
    ) as resp:
        data = await resp.json(content_type=None)
        if resp.status == 401:
            raise aiohttp.ClientResponseError(
                resp.request_info, resp.history, status=401, message="Unauthorized"
            )
        if resp.status == 403:
            raise aiohttp.ClientResponseError(
                resp.request_info, resp.history, status=403, message="Forbidden"
            )
        if resp.status == 404:
            raise aiohttp.ClientResponseError(
                resp.request_info, resp.history, status=404, message="Not Found"
            )
        return data
# Helpers – Minecraft

async def fetch_uuid(session: aiohttp.ClientSession, username: str) -> dict | None:
    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    async with session.get(url, timeout=8) as resp:
        if resp.status != 200:
            return None
        return await resp.json()

async def fetch_username(session: aiohttp.ClientSession, uuid: str) -> str | None:
    clean = uuid.replace("-", "")
    url = f"https://sessionserver.mojang.com/session/minecraft/profile/{clean}"
    async with session.get(url, timeout=8) as resp:
        if resp.status != 200:
            return None
        data = await resp.json()
        return data.get("name")

async def server_status(session: aiohttp.ClientSession, address: str) -> dict | None:
    url = f"https://api.mcsrvstat.us/3/{address}"
    async with session.get(url, timeout=10) as resp:
        if resp.status != 200:
            return None
        return await resp.json()

def format_uuid(raw: str) -> str:
    raw = raw.replace("-", "")
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

# Events

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print("Slash sync failed:", e)

# Help

@bot.tree.command(name="help", description="Show all commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Minecraft All-Purpose",
        description=(
            "> Utility bot for Minecraft accounts, servers, skins, and alts.\n"
            "> Built for clients, multiplayer, and general use."
        ),
        color=0x5865F2,
        timestamp=discord.utils.utcnow(),
    )

    embed.add_field(
        name="Alts (TheAltening)",
        value=(
            "```\n"
            "/generate      Generate a new alt\n"
            "/altinfo       Inspect an alt token\n"
            "/license       Check API key status\n"
            "!gen           Prefix alias for generate\n"
            "```"
        ),
        inline=False,
    )

    embed.add_field(
        name="Localts",
        value=(
            "```\n"
            "/lts_balance   Check Localts balance\n"
            "/lts_products  List available products\n"
            "/lts_buy       Purchase a product\n"
            "/lts_orders    List your orders\n"
            "/lts_order     Get order details / items\n"
            "```"
        ),
        inline=False,
    )

    embed.add_field(
        name="Players",
        value=(
            "```\n"
            "/uuid          Username → UUID\n"
            "/username      UUID → Username\n"
            "/skin          View head + body\n"
            "/premium       Check if name is premium\n"
            "```"
        ),
        inline=False,
    )

    embed.add_field(
        name="Servers",
        value=(
            "```\n"
            "/server        Full server status\n"
            "/ping          Quick online check\n"
            "```"
        ),
        inline=False,
    )

    embed.add_field(
        name="Extra",
        value=(
            "```\n"
            "/help          This menu\n"
            "/ports         Common Minecraft ports\n"
            "```"
        ),
        inline=False,
    )

    embed.set_footer(text="Minecraft All-Purpose")
    await interaction.response.send_message(embed=embed)

# Alt commands

@bot.tree.command(name="generate", description="Generate a new alt")
async def generate(interaction: discord.Interaction):
    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        try:
            alt = await generate_alt(session)
            if alt.get("limit"):
                await interaction.followup.send(
                    "> Daily generation limit reached on this API key.", ephemeral=True
                )
                return

            full_name = alt.get("username") or "Unknown"
            skin_hash = alt.get("skin")

            auth = await authenticate_token(session, alt["token"])
            if auth and auth.get("selectedProfile"):
                full_name = auth["selectedProfile"].get("name", full_name)

            color = await get_skin_color(session, skin_hash)

            embed = discord.Embed(
                title="Alt Generated",
                description=(
                    f"> **Username**\n`{full_name}`\n\n"
                    f"> **Token**\n`{alt['token']}`\n\n"
                    f"> **Password**\n`{alt.get('password', 'anything')}`"
                ),
                color=color,
                timestamp=discord.utils.utcnow(),
            )

            if skin_hash:
                embed.set_thumbnail(url=f"https://cdn.thealtening.com/skins/head/{skin_hash}.png")

            info = alt.get("info") or {}
            if info:
                lines = "\n".join(f"`{k}` → {v}" for k, v in info.items())
                embed.add_field(name="Account Info", value=lines[:1024], inline=False)

            embed.add_field(
                name="Status",
                value=f"Limit reached: `{alt.get('limit', False)}`",
                inline=False,
            )
            embed.set_footer(text="Minecraft All-Purpose • Alt")
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientResponseError as e:
            await interaction.followup.send(f"> API error `{e.status}`: {e.message}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"> Failed: `{e}`", ephemeral=True)

@bot.tree.command(name="license", description="Check alt API key / plan status")
async def license_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        try:
            data = await get_license(session)
            embed = discord.Embed(
                title="API License",
                description=(
                    f"> **User** `{data.get('username', 'N/A')}`\n"
                    f"> **Active** `{data.get('hasLicense', False)}`\n"
                    f"> **Plan** `{data.get('licenseType', 'N/A')}`\n"
                    f"> **Expires** `{data.get('expires', 'N/A')}`"
                ),
                color=0x57F287,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Minecraft All-Purpose")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"> Failed: `{e}`", ephemeral=True)

@bot.tree.command(name="altinfo", description="Inspect an alt token")
@app_commands.describe(token="Alt token (example@alt.com)")
async def altinfo(interaction: discord.Interaction, token: str):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        try:
            data = await get_token_info(session, token)
            embed = discord.Embed(
                title="Alt Token Info",
                description=(
                    f"> **Username** `{data.get('username', 'N/A')}`\n"
                    f"> **Expires** `{data.get('expires', 'N/A')}`"
                ),
                color=0xFEE75C,
                timestamp=discord.utils.utcnow(),
            )
            if data.get("skin"):
                embed.set_thumbnail(
                    url=f"https://cdn.thealtening.com/skins/head/{data['skin']}.png"
                )
            embed.set_footer(text="Minecraft All-Purpose")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"> Failed: `{e}`", ephemeral=True)

@bot.command(name="gen")
async def gen_prefix(ctx: commands.Context):
    """Prefix alias for /generate"""
    async with aiohttp.ClientSession() as session:
        try:
            alt = await generate_alt(session)
            if alt.get("limit"):
                await ctx.reply("> Daily generation limit reached.")
                return

            full_name = alt.get("username") or "Unknown"
            skin_hash = alt.get("skin")
            auth = await authenticate_token(session, alt["token"])
            if auth and auth.get("selectedProfile"):
                full_name = auth["selectedProfile"].get("name", full_name)

            color = await get_skin_color(session, skin_hash)

            embed = discord.Embed(
                title="Alt Generated",
                description=(
                    f"> **Username**\n`{full_name}`\n\n"
                    f"> **Token**\n`{alt['token']}`\n\n"
                    f"> **Password**\n`{alt.get('password', 'anything')}`"
                ),
                color=color,
                timestamp=discord.utils.utcnow(),
            )
            if skin_hash:
                embed.set_thumbnail(url=f"https://cdn.thealtening.com/skins/head/{skin_hash}.png")
            embed.set_footer(text="Minecraft All-Purpose • Alt")
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(f"> Failed: `{e}`")

# Localts commands
# Localts commands

@bot.tree.command(name="lts_balance", description="Check Localts account balance")
async def lts_balance(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not LOCALTS_API_KEY:
        await interaction.followup.send("> `LOCALTS_API_KEY` not set in .env", ephemeral=True)
        return

    async with aiohttp.ClientSession() as session:
        try:
            data = await localts_me(session)
            if not data.get("success"):
                await interaction.followup.send(
                    f"> Failed: `{data.get('error', 'unknown')}`", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="Localts Balance",
                description=(
                    f"> **Username**\n`{data.get('username', 'N/A')}`\n\n"
                    f"> **Balance**\n`{data.get('balance', 0)}` credits"
                ),
                color=0x57F287,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Minecraft All-Purpose • Localts")
            await interaction.followup.send(embed=embed)
        except aiohttp.ClientResponseError as e:
            await interaction.followup.send(f"> API error `{e.status}`: {e.message}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"> Failed: `{e}`", ephemeral=True)

@bot.tree.command(name="lts_products", description="List Localts products")
@app_commands.describe(category="Optional category filter (case-insensitive partial match)")
async def lts_products(interaction: discord.Interaction, category: str | None = None):
    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        try:
            data = await localts_products(session)
            if not data.get("success"):
                await interaction.followup.send(f"> Failed: `{data.get('error', 'unknown')}`")
                return

            products = data.get("products") or []
            if category:
                cat_lower = category.lower()
                products = [p for p in products if cat_lower in (p.get("category") or "").lower()]

            if not products:
                await interaction.followup.send("> No products found.")
                return

            products = products[:15]

            embed = discord.Embed(
                title="Localts Products",
                description=(
                    f"> Showing **{len(products)}** product(s)"
                    + (f" matching `{category}`" if category else "")
                    + "\n> Use `/lts_buy <id>` to purchase"
                ),
                color=0x5865F2,
                timestamp=discord.utils.utcnow(),
            )

            for p in products:
                name = p.get("name", "Unknown")
                pid = p.get("id", "?")
                price = p.get("priceInCredits", 0)
                stock = p.get("stock", 0)
                ptype = p.get("type", "?")
                cat = p.get("category", "?")
                tags = p.get("tags") or []
                discounts = p.get("quantityDiscounts") or {}

                stock_icon = "🟢" if stock > 10 else ("🟡" if stock > 0 else "🔴")

                lines = [
                    f"> **ID** `{pid}`",
                    f"> **Price** `{price}` credits",
                    f"> **Stock** {stock_icon} `{stock}`",
                    f"> **Type** `{ptype}` · **Category** `{cat}`",
                ]
                if tags:
                    lines.append(f"> **Tags** {', '.join(f'`{t}`' for t in tags[:6])}")
                if discounts:
                    tiers = ", ".join(
                        f"`{k}+` → `{v}%`"
                        for k, v in sorted(discounts.items(), key=lambda x: int(x[0]))
                    )
                    lines.append(f"> **Bulk** {tiers}")

                embed.add_field(
                    name=name[:256],
                    value="\n".join(lines),
                    inline=False,
                )

            embed.set_footer(text="Minecraft All-Purpose • Localts")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"> Failed: `{e}`")

@bot.tree.command(name="lts_buy", description="Purchase a Localts product")
@app_commands.describe(
    product_id="Product ID from /lts_products",
    amount="Quantity to buy (default 1)",
)
async def lts_buy(
    interaction: discord.Interaction, product_id: str, amount: app_commands.Range[int, 1, 100] = 1
):
    await interaction.response.defer(ephemeral=True)

    if not LOCALTS_API_KEY:
        await interaction.followup.send("> `LOCALTS_API_KEY` not set in .env", ephemeral=True)
        return

    async with aiohttp.ClientSession() as session:
        try:
            data = await localts_purchase(session, product_id, amount)
            if not data.get("success"):
                await interaction.followup.send(
                    f"> Purchase failed: `{data.get('error', 'unknown')}`",
                    ephemeral=True,
                )
                return

            order_id = data.get("orderId") or data.get("order_id") or "N/A"
            embed = discord.Embed(
                title="Purchase Successful",
                description=(
                    f"> **Product**\n`{product_id}`\n\n"
                    f"> **Amount**\n`{amount}`\n\n"
                    f"> **Order ID**\n`{order_id}`\n\n"
                    f"Retrieve items with `/lts_order {order_id}` once packaged."
                ),
                color=0x57F287,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Minecraft All-Purpose • Localts")
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientResponseError as e:
            await interaction.followup.send(f"> API error `{e.status}`: {e.message}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"> Failed: `{e}`", ephemeral=True)

@bot.tree.command(name="lts_orders", description="List your Localts orders")
@app_commands.describe(
    page="Zero-based page index (default 0)",
    size="Orders per page 1–100 (default 10)",
)
async def lts_orders(
    interaction: discord.Interaction,
    page: app_commands.Range[int, 0, 1000] = 0,
    size: app_commands.Range[int, 1, 100] = 10,
):
    await interaction.response.defer(ephemeral=True)

    if not LOCALTS_API_KEY:
        await interaction.followup.send("> `LOCALTS_API_KEY` not set in .env", ephemeral=True)
        return

    async with aiohttp.ClientSession() as session:
        try:
            data = await localts_orders(session, page=page, size=size)
            if not data.get("success"):
                await interaction.followup.send(
                    f"> Failed: `{data.get('error', 'unknown')}`", ephemeral=True
                )
                return

            orders = data.get("orders") or []
            total = data.get("totalElements", 0)
            total_pages = data.get("totalPages", 0)

            embed = discord.Embed(
                title="Localts Orders",
                description=(
                    f"> **Page** `{page}` / `{max(total_pages - 1, 0)}`\n"
                    f"> **Total** `{total}` order(s)"
                ),
                color=0xFEE75C,
                timestamp=discord.utils.utcnow(),
            )

            if not orders:
                embed.description += "\n\n> No orders on this page."
            else:
                for o in orders:
                    oid = o.get("id", "?")
                    pid = o.get("productId", "?")
                    ptype = o.get("productType", "?")
                    ts = o.get("timestamp")
                    time_str = "N/A"
                    if ts:
                        try:
                            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                            time_str = dt.strftime("%Y-%m-%d %H:%M UTC")
                        except Exception:
                            time_str = str(ts)

                    embed.add_field(
                        name=f"`{oid}`",
                        value=(
                            f"> **Product** `{pid}`\n"
                            f"> **Type** `{ptype}`\n"
                            f"> **Time** `{time_str}`"
                        ),
                        inline=False,
                    )

            embed.set_footer(text="Minecraft All-Purpose • Localts • /lts_order <id>")
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientResponseError as e:
            await interaction.followup.send(f"> API error `{e.status}`: {e.message}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"> Failed: `{e}`", ephemeral=True)

@bot.tree.command(name="lts_order", description="Get Localts order details / items")
@app_commands.describe(order_id="Order ID from /lts_orders or /lts_buy")
async def lts_order(interaction: discord.Interaction, order_id: str):
    await interaction.response.defer(ephemeral=True)

    if not LOCALTS_API_KEY:
        await interaction.followup.send("> `LOCALTS_API_KEY` not set in .env", ephemeral=True)
        return

    async with aiohttp.ClientSession() as session:
        try:
            data = await localts_get_order(session, order_id)
            if not data.get("success"):
                await interaction.followup.send(
                    f"> Failed: `{data.get('error', 'unknown')}`", ephemeral=True
                )
                return

            status = data.get("status", "UNKNOWN")
            product_name = data.get("product-name") or data.get("product_name") or "N/A"
            items = data.get("items") or []
            oid = data.get("order-id") or order_id

            color = {
                "PENDING": 0xFEE75C,
                "PACKAGING": 0x5865F2,
                "PACKAGED": 0x57F287,
            }.get(status, 0x2B2D31)

            status_icon = {
                "PENDING": "⏳",
                "PACKAGING": "📦",
                "PACKAGED": "✅",
            }.get(status, "❓")

            embed = discord.Embed(
                title=f"Order `{oid}`",
                description=(
                    f"> **Status** {status_icon} `{status}`\n"
                    f"> **Product** `{product_name}`"
                ),
                color=color,
                timestamp=discord.utils.utcnow(),
            )

            if status == "PACKAGED" and items:
                for i, item in enumerate(items, 1):
                    content = item.get("content", "")
                    display = content if len(content) <= 900 else content[:897] + "..."
                    embed.add_field(
                        name=f"Item {i} · `{item.get('id', '?')}`",
                        value=f"```\n{display}\n```",
                        inline=False,
                    )
            elif status != "PACKAGED":
                embed.add_field(
                    name="Note",
                    value="> Items appear once status is `PACKAGED`. Check again shortly.",
                    inline=False,
                )

            embed.set_footer(text="Minecraft All-Purpose • Localts")
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientResponseError as e:
            msg = {
                401: "Unauthorized (bad API key)",
                403: "Order does not belong to this API key",
                404: "Order not found",
            }.get(e.status, e.message)
            await interaction.followup.send(f"> API error `{e.status}`: {msg}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"> Failed: `{e}`", ephemeral=True)

# Player commands

@bot.tree.command(name="uuid", description="Convert username to UUID")
@app_commands.describe(username="Minecraft username")
async def uuid_cmd(interaction: discord.Interaction, username: str):
    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        data = await fetch_uuid(session, username)
        if not data:
            await interaction.followup.send(f"> Username `{username}` not found.")
            return

        uuid = data["id"]
        pretty = format_uuid(uuid)

        embed = discord.Embed(
            title=f"{data['name']}",
            description=(
                f"> **UUID**\n`{pretty}`\n\n"
                f"> **Raw**\n`{uuid}`"
            ),
            color=0x5865F2,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=f"https://mc-heads.net/avatar/{uuid}")
        embed.set_footer(text="Minecraft All-Purpose")
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="username", description="Convert UUID to username")
@app_commands.describe(uuid="Player UUID (with or without dashes)")
async def username_cmd(interaction: discord.Interaction, uuid: str):
    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        name = await fetch_username(session, uuid)
        if not name:
            await interaction.followup.send("> UUID not found or invalid.")
            return

        embed = discord.Embed(
            title="Username Lookup",
            description=(
                f"> **Username** `{name}`\n"
                f"> **UUID** `{uuid}`"
            ),
            color=0x5865F2,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=f"https://mc-heads.net/avatar/{uuid.replace('-', '')}")
        embed.set_footer(text="Minecraft All-Purpose")
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="skin", description="View a player's skin")
@app_commands.describe(username="Minecraft username")
async def skin_cmd(interaction: discord.Interaction, username: str):
    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        data = await fetch_uuid(session, username)
        if not data:
            await interaction.followup.send(f"> Username `{username}` not found.")
            return

        uuid = data["id"]
        embed = discord.Embed(
            title=f"Skin — {data['name']}",
            description=(
                f"> **Head** [link](https://mc-heads.net/avatar/{uuid})\n"
                f"> **Body** [link](https://mc-heads.net/body/{uuid})\n"
                f"> **Download** [skin.png](https://mc-heads.net/skin/{uuid})"
            ),
            color=0xEB459E,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_image(url=f"https://mc-heads.net/body/{uuid}")
        embed.set_thumbnail(url=f"https://mc-heads.net/avatar/{uuid}")
        embed.set_footer(text="Minecraft All-Purpose")
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="premium", description="Check if a username is premium / taken")
@app_commands.describe(username="Minecraft username to check")
async def premium_cmd(interaction: discord.Interaction, username: str):
    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        data = await fetch_uuid(session, username)
        if data:
            embed = discord.Embed(
                title="Premium Check",
                description=(
                    f"> **Username** `{data['name']}`\n"
                    f"> **Status** `Premium / Taken`\n"
                    f"> **UUID** `{format_uuid(data['id'])}`"
                ),
                color=0x57F287,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_thumbnail(url=f"https://mc-heads.net/avatar/{data['id']}")
        else:
            embed = discord.Embed(
                title="Premium Check",
                description=(
                    f"> **Username** `{username}`\n"
                    f"> **Status** `Available / Cracked / Not Premium`"
                ),
                color=0xED4245,
                timestamp=discord.utils.utcnow(),
            )
        embed.set_footer(text="Minecraft All-Purpose")
        await interaction.followup.send(embed=embed)

# Server commands

@bot.tree.command(name="server", description="Full server status")
@app_commands.describe(address="Server IP or domain")
async def server_cmd(interaction: discord.Interaction, address: str):
    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        data = await server_status(session, address)
        if not data:
            await interaction.followup.send("> Could not fetch server status.")
            return

        online = data.get("online", False)
        color = 0x57F287 if online else 0xED4245

        if online:
            players = data.get("players", {})
            version = data.get("version") or "Unknown"
            motd_list = data.get("motd", {}).get("clean") or []
            motd = "\n".join(motd_list) if isinstance(motd_list, list) else str(motd_list)

            desc = (
                f"> **Status** Online\n"
                f"> **Players** {players.get('online', '?')} / {players.get('max', '?')}\n"
                f"> **Version** {version}\n"
            )
            if motd:
                desc += f"\n> **MOTD**\n```{motd[:800]}```"
        else:
            desc = f"> **Status** Offline\n> **Address** `{address}`"

        embed = discord.Embed(
            title=f"Server — {address}",
            description=desc,
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="Minecraft All-Purpose • mcsrvstat.us")
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="ping", description="Quick online check")
@app_commands.describe(address="Server IP or domain")
async def ping_cmd(interaction: discord.Interaction, address: str):
    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        data = await server_status(session, address)
        if not data:
            await interaction.followup.send("> Could not reach status API.")
            return

        if data.get("online"):
            players = data.get("players", {})
            await interaction.followup.send(
                f"> **{address}** is **online**\n"
                f"> Players: `{players.get('online', '?')}/{players.get('max', '?')}`"
            )
        else:
            await interaction.followup.send(f"> **{address}** is **offline**")

# Extra utilities

@bot.tree.command(name="ports", description="Common Minecraft-related ports")
async def ports_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Common Ports",
        description=(
            "> Useful reference for servers, proxies, and clients.\n\n"
            "**Minecraft**\n"
            "```\n"
            "25565    Default Java server\n"
            "19132    Bedrock (UDP)\n"
            "25575    Default RCON\n"
            "```\n"
            "**Proxies / Tools**\n"
            "```\n"
            "25577    BungeeCord / Waterfall default\n"
            "25565    Velocity (often same)\n"
            "8080     Common web / panel\n"
            "```\n"
            "**Other**\n"
            "```\n"
            "22       SSH\n"
            "3306     MySQL\n"
            "6379     Redis\n"
            "```"
        ),
        color=0x5865F2,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text="Minecraft All-Purpose")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if not DISCORD_TOKEN or not ALTENING_API_KEY:
        raise SystemExit("Set DISCORD_TOKEN and ALTENING_API_KEY in .env")
    if not LOCALTS_API_KEY:
        print("Warning: LOCALTS_API_KEY not set — Localts commands will fail until configured")
    bot.run(DISCORD_TOKEN)
