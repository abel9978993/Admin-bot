import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
import sqlite3
import asyncio
import os
import re


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("MEMBERCOUNT_TOKEN")

if not TOKEN:
    print("❌ MEMBERCOUNT_TOKEN no está configurado.")
    raise SystemExit(1)


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.presences = True


# =========================================================
# DATABASES
# =========================================================

PREFIX_DB = "prefixes.db"
MESSAGES_DB = "messages.db"
AFK_DB = "afk.db"
WARNINGS_DB = "warnings.db"


# =========================================================
# CONSTANTS
# =========================================================

MAX_WARNINGS = 3
WARNING_TIMEOUT_SECONDS = 60 * 60

# Discord permite un timeout máximo de 28 días
MAX_MUTE_SECONDS = 28 * 24 * 60 * 60


# =========================================================
# PREFIX DATABASE
# =========================================================

def init_prefix_db():
    with sqlite3.connect(PREFIX_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prefixes (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT NOT NULL
            )
        """)
        conn.commit()


def get_prefix(guild_id):
    with sqlite3.connect(PREFIX_DB) as conn:
        row = conn.execute(
            "SELECT prefix FROM prefixes WHERE guild_id = ?",
            (guild_id,)
        ).fetchone()

    return row[0] if row else "?"


def set_prefix(guild_id, prefix):
    with sqlite3.connect(PREFIX_DB) as conn:
        conn.execute("""
            INSERT INTO prefixes (guild_id, prefix)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET prefix = excluded.prefix
        """, (guild_id, prefix))
        conn.commit()


def get_bot_prefix(bot, message):
    if message.guild is None:
        return "?"

    return get_prefix(message.guild.id)


init_prefix_db()


# =========================================================
# MESSAGE STATS DATABASE
# =========================================================

def init_messages_db():
    with sqlite3.connect(MESSAGES_DB) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS message_adjustments (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                period TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reference_real INTEGER NOT NULL DEFAULT 0,
                period_start TEXT,
                PRIMARY KEY (guild_id, user_id, period)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS message_settings (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)

        conn.commit()


def is_message_counting_enabled(guild_id):
    with sqlite3.connect(MESSAGES_DB) as conn:
        row = conn.execute(
            "SELECT enabled FROM message_settings WHERE guild_id = ?",
            (guild_id,)
        ).fetchone()

    if row is None:
        return True

    return bool(row[0])


def set_message_counting(guild_id, enabled):
    with sqlite3.connect(MESSAGES_DB) as conn:
        conn.execute("""
            INSERT INTO message_settings (guild_id, enabled)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET enabled = excluded.enabled
        """, (guild_id, int(enabled)))
        conn.commit()


def record_message(guild_id, user_id, channel_id):
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(MESSAGES_DB) as conn:
        conn.execute("""
            INSERT INTO messages (
                guild_id,
                user_id,
                channel_id,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            guild_id,
            user_id,
            channel_id,
            now
        ))

        conn.commit()


def get_period_start(period):
    now = datetime.now(timezone.utc)

    if period == "today":
        return now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

    if period == "week":
        start = now - timedelta(days=now.weekday())

        return start.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

    if period == "month":
        return now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

    return None


def get_message_count(guild_id, user_id, period):
    with sqlite3.connect(MESSAGES_DB) as conn:

        if period == "total":
            row = conn.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE guild_id = ?
                AND user_id = ?
            """, (
                guild_id,
                user_id
            )).fetchone()

            real_count = row[0] if row else 0

        else:
            start = get_period_start(period)

            row = conn.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE guild_id = ?
                AND user_id = ?
                AND created_at >= ?
            """, (
                guild_id,
                user_id,
                start.isoformat()
            )).fetchone()

            real_count = row[0] if row else 0

        adjustment = conn.execute("""
            SELECT amount
            FROM message_adjustments
            WHERE guild_id = ?
            AND user_id = ?
            AND period = ?
        """, (
            guild_id,
            user_id,
            period
        )).fetchone()

        adjustment_amount = adjustment[0] if adjustment else 0

    return max(0, real_count + adjustment_amount)


def set_message_adjustment(guild_id, user_id, period, amount):
    with sqlite3.connect(MESSAGES_DB) as conn:

        conn.execute("""
            INSERT INTO message_adjustments (
                guild_id,
                user_id,
                period,
                amount,
                reference_real,
                period_start
            )
            VALUES (?, ?, ?, ?, 0, ?)
            ON CONFLICT(guild_id, user_id, period)
            DO UPDATE SET amount = excluded.amount
        """, (
            guild_id,
            user_id,
            period,
            amount,
            get_period_start(period).isoformat()
            if period != "total"
            else None
        ))

        conn.commit()


init_messages_db()


# =========================================================
# AFK DATABASE
# =========================================================

def init_afk_db():
    with sqlite3.connect(AFK_DB) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS afk (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                original_nick TEXT,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS afk_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                afk_user_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()


def set_afk(guild_id, user_id, reason, original_nick):
    with sqlite3.connect(AFK_DB) as conn:

        conn.execute("""
            INSERT OR REPLACE INTO afk (
                guild_id,
                user_id,
                reason,
                original_nick
            )
            VALUES (?, ?, ?, ?)
        """, (
            guild_id,
            user_id,
            reason,
            original_nick
        ))

        conn.commit()


def get_afk(guild_id, user_id):
    with sqlite3.connect(AFK_DB) as conn:

        return conn.execute("""
            SELECT reason, original_nick
            FROM afk
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        )).fetchone()


def remove_afk(guild_id, user_id):
    with sqlite3.connect(AFK_DB) as conn:

        row = conn.execute("""
            SELECT reason, original_nick
            FROM afk
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        )).fetchone()

        conn.execute("""
            DELETE FROM afk
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        ))

        conn.commit()

    return row


def save_afk_message(
    guild_id,
    afk_user_id,
    sender_id,
    message
):
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(AFK_DB) as conn:

        conn.execute("""
            INSERT INTO afk_messages (
                guild_id,
                afk_user_id,
                sender_id,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            guild_id,
            afk_user_id,
            sender_id,
            message,
            now
        ))

        conn.commit()


def get_afk_messages(guild_id, user_id):
    with sqlite3.connect(AFK_DB) as conn:

        rows = conn.execute("""
            SELECT sender_id, message, created_at
            FROM afk_messages
            WHERE guild_id = ?
            AND afk_user_id = ?
            ORDER BY id ASC
        """, (
            guild_id,
            user_id
        )).fetchall()

    return rows


def clear_afk_messages(guild_id, user_id):
    with sqlite3.connect(AFK_DB) as conn:

        conn.execute("""
            DELETE FROM afk_messages
            WHERE guild_id = ?
            AND afk_user_id = ?
        """, (
            guild_id,
            user_id
        ))

        conn.commit()


init_afk_db()


# =========================================================
# WARNINGS DATABASE
# =========================================================

def init_warnings_db():
    with sqlite3.connect(WARNINGS_DB) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()


def add_warning(
    guild_id,
    user_id,
    moderator_id,
    reason
):
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(WARNINGS_DB) as conn:

        conn.execute("""
            INSERT INTO warnings (
                guild_id,
                user_id,
                moderator_id,
                reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            guild_id,
            user_id,
            moderator_id,
            reason,
            now
        ))

        conn.commit()


def get_warning_count(guild_id, user_id):
    with sqlite3.connect(WARNINGS_DB) as conn:

        row = conn.execute("""
            SELECT COUNT(*)
            FROM warnings
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        )).fetchone()

    return row[0] if row else 0


def get_warnings(guild_id, user_id):
    with sqlite3.connect(WARNINGS_DB) as conn:

        return conn.execute("""
            SELECT moderator_id, reason, created_at
            FROM warnings
            WHERE guild_id = ?
            AND user_id = ?
            ORDER BY id DESC
        """, (
            guild_id,
            user_id
        )).fetchall()


def clear_warnings(guild_id, user_id):
    with sqlite3.connect(WARNINGS_DB) as conn:

        cursor = conn.execute("""
            DELETE FROM warnings
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        ))

        conn.commit()

    return cursor.rowcount


init_warnings_db()


# =========================================================
# TRANSLATION
# =========================================================

TRANSLATIONS = {

    "en": {

        "membercount_title": "Server Member Count",

        "afk_set": "You are now AFK.",
        "afk_reason": "Reason",
        "afk_back": "Welcome back, {username}! You are no longer AFK.",
        "afk_user": "{username} is currently AFK.",
        "afk_leave_message": "Leave a message",

        "stats_title": "Message Statistics",
        "today": "Today",
        "week": "This week",
        "month": "This month",
        "total": "Total",

        "stats_disabled":
            "Message statistics are currently disabled on this server.",

        "stats_enabled":
            "Message statistics have been enabled.",

        "stats_disabled_success":
            "Message statistics have been disabled.",

        "prefix_changed":
            "The server prefix has been changed to `{prefix}`.",

        "warning_added":
            "{target} has received a warning.\nWarnings: **{count}/3**\nReason: {reason}",

        "warning_none":
            "{target} has no warnings.",

        "warnings_title":
            "Warnings for {target}",

        "warnings_cleared":
            "Cleared **{count}** warning(s) from {target}.",

        "promoted":
            "{target} has been promoted.",

        "demoted":
            "{target} has been demoted.",

        "role_added":
            "Added the role {role} to {target}.",

        "role_removed":
            "Removed the role {role} from {target}.",

        "mute_success":
            "{target} has been muted for **{duration}**.\nReason: {reason}",

        "unmute_success":
            "{target} has been unmuted.",

        "mute_invalid_time":
            "Invalid duration. Examples: `10m`, `1h`, `1d`, `7d`, `28d`.",

        "mute_too_long":
            "The maximum mute duration is **28 days**.",

        "cannot_moderate":
            "I cannot moderate that member.",

        "cannot_self":
            "You cannot do that to yourself.",

        "bot_target":
            "You cannot use this command on a bot.",

    },

    "es": {

        "membercount_title": "Número de miembros",

        "afk_set": "Ahora estás AFK.",
        "afk_reason": "Motivo",
        "afk_back": "¡Bienvenido de nuevo, {username}! Ya no estás AFK.",
        "afk_user": "{username} está AFK.",
        "afk_leave_message": "Dejar un mensaje",

        "stats_title": "Estadísticas de mensajes",
        "today": "Hoy",
        "week": "Esta semana",
        "month": "Este mes",
        "total": "Total",

        "stats_disabled":
            "Las estadísticas de mensajes están desactivadas en este servidor.",

        "stats_enabled":
            "Las estadísticas de mensajes han sido activadas.",

        "stats_disabled_success":
            "Las estadísticas de mensajes han sido desactivadas.",

        "prefix_changed":
            "El prefijo del servidor ha cambiado a `{prefix}`.",

        "warning_added":
            "{target} ha recibido una advertencia.\nAdvertencias: **{count}/3**\nMotivo: {reason}",

        "warning_none":
            "{target} no tiene advertencias.",

        "warnings_title":
            "Advertencias de {target}",

        "warnings_cleared":
            "Se han eliminado **{count}** advertencia(s) de {target}.",

        "promoted":
            "{target} ha sido ascendido.",

        "demoted":
            "{target} ha sido degradado.",

        "role_added":
            "Se ha añadido el rol {role} a {target}.",

        "role_removed":
            "Se ha quitado el rol {role} de {target}.",

        "mute_success":
            "{target} ha sido muteado durante **{duration}**.\nMotivo: {reason}",

        "unmute_success":
            "{target} ya no está muteado.",

        "mute_invalid_time":
            "Duración no válida. Ejemplos: `10m`, `1h`, `1d`, `7d`, `28d`.",

        "mute_too_long":
            "La duración máxima del mute es de **28 días**.",

        "cannot_moderate":
            "No puedo moderar a ese miembro.",

        "cannot_self":
            "No puedes hacer eso contigo mismo.",

        "bot_target":
            "No puedes usar este comando contra un bot.",

    }
}


def get_language(guild):
    # English is the default server language
    return "en"


def t(user, key, **kwargs):
    language = "en"

    if hasattr(user, "guild") and user.guild:
        language = get_language(user.guild)

    text = TRANSLATIONS.get(
        language,
        TRANSLATIONS["en"]
    ).get(
        key,
        TRANSLATIONS["en"].get(key, key)
    )

    return text.format(**kwargs)


# =========================================================
# DURATION PARSER
# =========================================================

def parse_duration(duration):
    """
    Supported:
    10s
    10m
    1h
    1d
    1w
    """

    if not duration:
        return None

    duration = duration.lower().strip()

    match = re.fullmatch(
        r"(\d+)\s*(s|m|h|d|w)",
        duration
    )

    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 60 * 60 * 24,
        "w": 60 * 60 * 24 * 7
    }

    seconds = amount * multipliers[unit]

    if seconds <= 0:
        return None

    return seconds


def format_duration(seconds):
    if seconds % (7 * 24 * 60 * 60) == 0:
        return f"{seconds // (7 * 24 * 60 * 60)}w"

    if seconds % (24 * 60 * 60) == 0:
        return f"{seconds // (24 * 60 * 60)}d"

    if seconds % (60 * 60) == 0:
        return f"{seconds // (60 * 60)}h"

    if seconds % 60 == 0:
        return f"{seconds // 60}m"

    return f"{seconds}s"


# =========================================================
# AFK MESSAGE VIEW
# =========================================================

class AFKMessageModal(discord.ui.Modal, title="Leave a message"):

    message = discord.ui.TextInput(
        label="Your message",
        placeholder="Write your message...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(self, guild_id, afk_user_id):
        super().__init__()

        self.guild_id = guild_id
        self.afk_user_id = afk_user_id

    async def on_submit(self, interaction: discord.Interaction):

        save_afk_message(
            self.guild_id,
            self.afk_user_id,
            interaction.user.id,
            str(self.message.value)
        )

        await interaction.response.send_message(
            "Your message has been saved.",
            ephemeral=True
        )


class AFKMessageView(discord.ui.View):

    def __init__(self, guild_id, afk_user_id):
        super().__init__(timeout=300)

        self.guild_id = guild_id
        self.afk_user_id = afk_user_id

    @discord.ui.button(
        label="Leave a message",
        style=discord.ButtonStyle.primary
    )
    async def leave_message(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        modal = AFKMessageModal(
            self.guild_id,
            self.afk_user_id
        )

        await interaction.response.send_modal(modal)


# =========================================================
# BOT CLASS
# =========================================================

class MyBot(commands.Bot):

    async def setup_hook(self):

        print("🔄 Sincronizando comandos globales...")

        try:
            synced = await self.tree.sync()

            print(
                f"✅ {len(synced)} comandos globales sincronizados."
            )

        except Exception as e:

            print(
                f"❌ Error sincronizando comandos: {e}"
            )


bot = MyBot(
    command_prefix=get_bot_prefix,
    intents=intents,
    help_command=None
)


# =========================================================
# MEMBERCOUNT
# =========================================================

@bot.tree.command(
    name="membercount",
    description="Show the server member count"
)
async def slash_membercount(
    interaction: discord.Interaction
):

    guild = interaction.guild

    await interaction.response.send_message(
        f"👥 **{guild.name}**\n"
        f"Members: **{guild.member_count}**"
    )


@bot.command(name="membercount")
async def prefix_membercount(ctx):

    await ctx.send(
        f"👥 **{ctx.guild.name}**\n"
        f"Members: **{ctx.guild.member_count}**"
    )


# =========================================================
# BAN
# =========================================================

@bot.tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.checks.has_permissions(ban_members=True)
async def slash_ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if member == interaction.user:
        await interaction.response.send_message(
            t(interaction.user, "cannot_self"),
            ephemeral=True
        )
        return

    if member == interaction.guild.me:
        await interaction.response.send_message(
            t(interaction.user, "cannot_moderate"),
            ephemeral=True
        )
        return

    try:

        await member.ban(reason=reason)

        await interaction.response.send_message(
            f"🔨 {member.mention} has been banned.\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            t(interaction.user, "cannot_moderate"),
            ephemeral=True
        )


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def prefix_ban(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    if member == ctx.author:
        await ctx.send(
            t(ctx.author, "cannot_self")
        )
        return

    try:

        await member.ban(reason=reason)

        await ctx.send(
            f"🔨 {member.mention} has been banned.\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:

        await ctx.send(
            t(ctx.author, "cannot_moderate")
        )


# =========================================================
# KICK
# =========================================================

@bot.tree.command(
    name="kick",
    description="Kick a member"
)
@app_commands.checks.has_permissions(kick_members=True)
async def slash_kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if member == interaction.user:
        await interaction.response.send_message(
            t(interaction.user, "cannot_self"),
            ephemeral=True
        )
        return

    try:

        await member.kick(reason=reason)

        await interaction.response.send_message(
            f"👢 {member.mention} has been kicked.\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            t(interaction.user, "cannot_moderate"),
            ephemeral=True
        )


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def prefix_kick(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    if member == ctx.author:
        await ctx.send(
            t(ctx.author, "cannot_self")
        )
        return

    try:

        await member.kick(reason=reason)

        await ctx.send(
            f"👢 {member.mention} has been kicked.\n"
            f"Reason: {reason}"
        )

    except discord.Forbidden:

        await ctx.send(
            t(ctx.author, "cannot_moderate")
        )


# =========================================================
# UNBAN
# =========================================================

@bot.tree.command(
    name="unban",
    description="Unban a user by ID"
)
@app_commands.checks.has_permissions(ban_members=True)
async def slash_unban(
    interaction: discord.Interaction,
    user_id: str
):

    try:

        user = await bot.fetch_user(int(user_id))

        await interaction.guild.unban(user)

        await interaction.response.send_message(
            f"✅ {user} has been unbanned."
        )

    except (ValueError, discord.NotFound):

        await interaction.response.send_message(
            "❌ User not found.",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission to unban this user.",
            ephemeral=True
        )


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def prefix_unban(ctx, user_id: str):

    try:

        user = await bot.fetch_user(int(user_id))

        await ctx.guild.unban(user)

        await ctx.send(
            f"✅ {user} has been unbanned."
        )

    except (ValueError, discord.NotFound):

        await ctx.send(
            "❌ User not found."
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ I don't have permission to unban this user."
        )


# =========================================================
# SET NICK
# =========================================================

@bot.tree.command(
    name="setnick",
    description="Change a member's nickname"
)
@app_commands.checks.has_permissions(manage_nicknames=True)
async def slash_setnick(
    interaction: discord.Interaction,
    member: discord.Member,
    nickname: str
):

    try:

        await member.edit(
            nick=nickname,
            reason=f"Nickname changed by {interaction.user}"
        )

        await interaction.response.send_message(
            f"✅ Nickname changed for {member.mention}."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot change that nickname.",
            ephemeral=True
        )


@bot.command(name="setnick")
@commands.has_permissions(manage_nicknames=True)
async def prefix_setnick(
    ctx,
    member: discord.Member,
    *,
    nickname: str
):

    try:

        await member.edit(
            nick=nickname,
            reason=f"Nickname changed by {ctx.author}"
        )

        await ctx.send(
            f"✅ Nickname changed for {member.mention}."
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ I cannot change that nickname."
        )


@bot.command(name="nick")
async def prefix_nick(ctx):

    await ctx.send(
        f"Your current nickname is: "
        f"**{ctx.author.display_name}**"
    )


# =========================================================
# PURGE
# =========================================================

@bot.tree.command(
    name="purge",
    description="Delete messages"
)
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_purge(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 100]
):

    await interaction.response.defer(
        ephemeral=True
    )

    deleted = await interaction.channel.purge(
        limit=amount
    )

    await interaction.followup.send(
        f"🧹 Deleted **{len(deleted)}** messages.",
        ephemeral=True
    )


@bot.command(name="purge")
@commands.has_permissions(manage_messages=True)
async def prefix_purge(ctx, amount: int):

    if amount < 1 or amount > 100:

        await ctx.send(
            "❌ Choose a number between 1 and 100."
        )

        return

    deleted = await ctx.channel.purge(
        limit=amount + 1
    )

    msg = await ctx.send(
        f"🧹 Deleted **{len(deleted) - 1}** messages."
    )

    await asyncio.sleep(2)

    try:
        await msg.delete()
    except discord.NotFound:
        pass


# =========================================================
# PREFIX
# =========================================================

@bot.tree.command(
    name="prefix",
    description="Change the server prefix"
)
@app_commands.checks.has_permissions(administrator=True)
async def slash_prefix(
    interaction: discord.Interaction,
    prefix: str
):

    if len(prefix) > 5:

        await interaction.response.send_message(
            "❌ Prefix must be 5 characters or less.",
            ephemeral=True
        )

        return

    set_prefix(
        interaction.guild.id,
        prefix
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "prefix_changed",
            prefix=prefix
        )
    )


@bot.command(name="prefix")
@commands.has_permissions(administrator=True)
async def prefix_prefix(ctx, prefix: str):

    if len(prefix) > 5:

        await ctx.send(
            "❌ Prefix must be 5 characters or less."
        )

        return

    set_prefix(
        ctx.guild.id,
        prefix
    )

    await ctx.send(
        t(
            ctx.author,
            "prefix_changed",
            prefix=prefix
        )
    )


# =========================================================
# MESSAGE STATS
# =========================================================

async def send_stats(
    target,
    channel,
    requester
):

    guild_id = channel.guild.id

    if not is_message_counting_enabled(guild_id):

        await channel.send(
            t(
                requester,
                "stats_disabled"
            )
        )

        return

    today = get_message_count(
        guild_id,
        target.id,
        "today"
    )

    week = get_message_count(
        guild_id,
        target.id,
        "week"
    )

    month = get_message_count(
        guild_id,
        target.id,
        "month"
    )

    total = get_message_count(
        guild_id,
        target.id,
        "total"
    )

    embed = discord.Embed(
        title=t(
            requester,
            "stats_title"
        ),
        description=target.mention
    )

    embed.add_field(
        name=t(requester, "today"),
        value=f"**{today}**",
        inline=True
    )

    embed.add_field(
        name=t(requester, "week"),
        value=f"**{week}**",
        inline=True
    )

    embed.add_field(
        name=t(requester, "month"),
        value=f"**{month}**",
        inline=True
    )

    embed.add_field(
        name=t(requester, "total"),
        value=f"**{total}**",
        inline=False
    )

    await channel.send(
        embed=embed
    )


@bot.tree.command(
    name="am",
    description="View message statistics"
)
async def slash_am(
    interaction: discord.Interaction,
    member: discord.Member | None = None
):

    target = member or interaction.user

    await send_stats(
        target,
        interaction.channel,
        interaction.user
    )


@bot.command(name="am")
async def prefix_am(
    ctx,
    member: discord.Member | None = None
):

    target = member or ctx.author

    await send_stats(
        target,
        ctx.channel,
        ctx.author
    )


# =========================================================
# ASET
# =========================================================

period_choices = [
    app_commands.Choice(
        name="today",
        value="today"
    ),
    app_commands.Choice(
        name="week",
        value="week"
    ),
    app_commands.Choice(
        name="month",
        value="month"
    ),
    app_commands.Choice(
        name="total",
        value="total"
    )
]


@bot.tree.command(
    name="aset",
    description="Set message statistics"
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.choices(period=period_choices)
async def slash_aset(
    interaction: discord.Interaction,
    member: discord.Member,
    period: app_commands.Choice[str],
    amount: int
):

    set_message_adjustment(
        interaction.guild.id,
        member.id,
        period.value,
        amount
    )

    await interaction.response.send_message(
        f"✅ Set **{period.value}** messages for "
        f"{member.mention} to **{amount}**."
    )


@bot.command(name="aset")
@commands.has_permissions(administrator=True)
async def prefix_aset(
    ctx,
    member: discord.Member,
    period: str,
    amount: int
):

    period = period.lower()

    if period == "hoy":
        period = "today"

    elif period == "semana":
        period = "week"

    elif period == "mes":
        period = "month"

    if period not in (
        "today",
        "week",
        "month",
        "total"
    ):

        await ctx.send(
            "❌ Use: today, week, month or total."
        )

        return

    set_message_adjustment(
        ctx.guild.id,
        member.id,
        period,
        amount
    )

    await ctx.send(
        f"✅ Set **{period}** messages for "
        f"{member.mention} to **{amount}**."
    )


# =========================================================
# ENABLE / DISABLE MESSAGE STATS
# =========================================================

@bot.tree.command(
    name="aenable",
    description="Enable message statistics"
)
@app_commands.checks.has_permissions(administrator=True)
async def slash_aenable(
    interaction: discord.Interaction
):

    set_message_counting(
        interaction.guild.id,
        True
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "stats_enabled"
        )
    )


@bot.command(name="aenable")
@commands.has_permissions(administrator=True)
async def prefix_aenable(ctx):

    set_message_counting(
        ctx.guild.id,
        True
    )

    await ctx.send(
        t(
            ctx.author,
            "stats_enabled"
        )
    )


@bot.tree.command(
    name="adesable",
    description="Disable message statistics"
)
@app_commands.checks.has_permissions(administrator=True)
async def slash_adesable(
    interaction: discord.Interaction
):

    set_message_counting(
        interaction.guild.id,
        False
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "stats_disabled_success"
        )
    )


@bot.command(name="adesable")
@commands.has_permissions(administrator=True)
async def prefix_adesable(ctx):

    set_message_counting(
        ctx.guild.id,
        False
    )

    await ctx.send(
        t(
            ctx.author,
            "stats_disabled_success"
        )
    )


# =========================================================
# PROMOTE / DEMOTE
# =========================================================

@bot.tree.command(
    name="promote",
    description="Give the member the highest manageable role"
)
@app_commands.checks.has_permissions(manage_roles=True)
async def slash_promote(
    interaction: discord.Interaction,
    member: discord.Member
):

    roles = [
        role
        for role in interaction.guild.roles
        if role != interaction.guild.default_role
        and role < interaction.guild.me.top_role
        and not role.managed
    ]

    if not roles:

        await interaction.response.send_message(
            "❌ No manageable roles found.",
            ephemeral=True
        )

        return

    highest = roles[-1]

    try:

        await member.add_roles(
            highest,
            reason=f"Promoted by {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "promoted",
                target=member.mention
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot manage that role.",
            ephemeral=True
        )


@bot.command(name="promote")
@commands.has_permissions(manage_roles=True)
async def prefix_promote(
    ctx,
    member: discord.Member
):

    roles = [
        role
        for role in ctx.guild.roles
        if role != ctx.guild.default_role
        and role < ctx.guild.me.top_role
        and not role.managed
    ]

    if not roles:

        await ctx.send(
            "❌ No manageable roles found."
        )

        return

    highest = roles[-1]

    try:

        await member.add_roles(
            highest,
            reason=f"Promoted by {ctx.author}"
        )

        await ctx.send(
            t(
                ctx.author,
                "promoted",
                target=member.mention
            )
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ I cannot manage that role."
        )


@bot.tree.command(
    name="demote",
    description="Remove the highest manageable role"
)
@app_commands.checks.has_permissions(manage_roles=True)
async def slash_demote(
    interaction: discord.Interaction,
    member: discord.Member
):

    manageable = [
        role
        for role in member.roles
        if role != interaction.guild.default_role
        and role < interaction.guild.me.top_role
        and not role.managed
    ]

    if not manageable:

        await interaction.response.send_message(
            "❌ This member has no manageable roles.",
            ephemeral=True
        )

        return

    role = max(
        manageable,
        key=lambda r: r.position
    )

    try:

        await member.remove_roles(
            role,
            reason=f"Demoted by {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "demoted",
                target=member.mention
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot manage that role.",
            ephemeral=True
        )


@bot.command(name="demote")
@commands.has_permissions(manage_roles=True)
async def prefix_demote(
    ctx,
    member: discord.Member
):

    manageable = [
        role
        for role in member.roles
        if role != ctx.guild.default_role
        and role < ctx.guild.me.top_role
        and not role.managed
    ]

    if not manageable:

        await ctx.send(
            "❌ This member has no manageable roles."
        )

        return

    role = max(
        manageable,
        key=lambda r: r.position
    )

    try:

        await member.remove_roles(
            role,
            reason=f"Demoted by {ctx.author}"
        )

        await ctx.send(
            t(
                ctx.author,
                "demoted",
                target=member.mention
            )
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ I cannot manage that role."
        )


# =========================================================
# ROLE ADD / REMOVE
# =========================================================

role_group = app_commands.Group(
    name="role",
    description="Manage member roles"
)


@role_group.command(
    name="add",
    description="Add a role to a member"
)
@app_commands.checks.has_permissions(manage_roles=True)
async def slash_role_add(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ I cannot manage that role.",
            ephemeral=True
        )

        return

    try:

        await member.add_roles(
            role,
            reason=f"Role added by {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_added",
                role=role.mention,
                target=member.mention
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot manage that role.",
            ephemeral=True
        )


@role_group.command(
    name="remove",
    description="Remove a role from a member"
)
@app_commands.checks.has_permissions(manage_roles=True)
async def slash_role_remove(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ I cannot manage that role.",
            ephemeral=True
        )

        return

    try:

        await member.remove_roles(
            role,
            reason=f"Role removed by {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_removed",
                role=role.mention,
                target=member.mention
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot manage that role.",
            ephemeral=True
        )


bot.tree.add_command(role_group)


@bot.group(
    name="role",
    invoke_without_command=True
)
@commands.has_permissions(manage_roles=True)
async def prefix_role(ctx):

    await ctx.send(
        "Use `?role add @user @role` or "
        "`?role remove @user @role`."
    )


@prefix_role.command(name="add")
@commands.has_permissions(manage_roles=True)
async def prefix_role_add(
    ctx,
    member: discord.Member,
    role: discord.Role
):

    if role >= ctx.guild.me.top_role:

        await ctx.send(
            "❌ I cannot manage that role."
        )

        return

    try:

        await member.add_roles(
            role,
            reason=f"Role added by {ctx.author}"
        )

        await ctx.send(
            t(
                ctx.author,
                "role_added",
                role=role.mention,
                target=member.mention
            )
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ I cannot manage that role."
        )


@prefix_role.command(name="remove")
@commands.has_permissions(manage_roles=True)
async def prefix_role_remove(
    ctx,
    member: discord.Member,
    role: discord.Role
):

    if role >= ctx.guild.me.top_role:

        await ctx.send(
            "❌ I cannot manage that role."
        )

        return

    try:

        await member.remove_roles(
            role,
            reason=f"Role removed by {ctx.author}"
        )

        await ctx.send(
            t(
                ctx.author,
                "role_removed",
                role=role.mention,
                target=member.mention
            )
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ I cannot manage that role."
        )


# =========================================================
# WARN
# =========================================================

@bot.tree.command(
    name="warn",
    description="Warn a member"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def slash_warn(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if member == interaction.user:

        await interaction.response.send_message(
            t(
                interaction.user,
                "cannot_self"
            ),
            ephemeral=True
        )

        return

    if member.bot:

        await interaction.response.send_message(
            t(
                interaction.user,
                "bot_target"
            ),
            ephemeral=True
        )

        return

    add_warning(
        interaction.guild.id,
        member.id,
        interaction.user.id,
        reason
    )

    count = get_warning_count(
        interaction.guild.id,
        member.id
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "warning_added",
            target=member.mention,
            count=count,
            reason=reason
        )
    )

    if count >= MAX_WARNINGS:

        try:

            until = (
                discord.utils.utcnow()
                + timedelta(
                    seconds=WARNING_TIMEOUT_SECONDS
                )
            )

            await member.timeout(
                until,
                reason="Reached 3 warnings"
            )

            await interaction.followup.send(
                f"⏱️ {member.mention} has been timed out "
                f"for **1 hour** after reaching 3 warnings."
            )

        except discord.Forbidden:
            pass


@bot.command(name="warn")
@commands.has_permissions(moderate_members=True)
async def prefix_warn(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    if member == ctx.author:

        await ctx.send(
            t(
                ctx.author,
                "cannot_self"
            )
        )

        return

    if member.bot:

        await ctx.send(
            t(
                ctx.author,
                "bot_target"
            )
        )

        return

    add_warning(
        ctx.guild.id,
        member.id,
        ctx.author.id,
        reason
    )

    count = get_warning_count(
        ctx.guild.id,
        member.id
    )

    await ctx.send(
        t(
            ctx.author,
            "warning_added",
            target=member.mention,
            count=count,
            reason=reason
        )
    )

    if count >= MAX_WARNINGS:

        try:

            until = (
                discord.utils.utcnow()
                + timedelta(
                    seconds=WARNING_TIMEOUT_SECONDS
                )
            )

            await member.timeout(
                until,
                reason="Reached 3 warnings"
            )

            await ctx.send(
                f"⏱️ {member.mention} has been timed out "
                f"for **1 hour** after reaching 3 warnings."
            )

        except discord.Forbidden:
            pass


# =========================================================
# WARNINGS
# =========================================================

@bot.tree.command(
    name="warnings",
    description="View a member's warnings"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def slash_warnings(
    interaction: discord.Interaction,
    member: discord.Member
):

    warnings = get_warnings(
        interaction.guild.id,
        member.id
    )

    if not warnings:

        await interaction.response.send_message(
            t(
                interaction.user,
                "warning_none",
                target=member.mention
            )
        )

        return

    embed = discord.Embed(
        title=t(
            interaction.user,
            "warnings_title",
            target=member.display_name
        )
    )

    for index, warning in enumerate(
        warnings,
        start=1
    ):

        moderator_id, reason, created_at = warning

        embed.add_field(
            name=f"Warning #{index}",
            value=(
                f"**Reason:** {reason}\n"
                f"**Moderator:** <@{moderator_id}>\n"
                f"**Date:** {created_at}"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed
    )


@bot.command(name="warnings")
@commands.has_permissions(moderate_members=True)
async def prefix_warnings(
    ctx,
    member: discord.Member
):

    warnings = get_warnings(
        ctx.guild.id,
        member.id
    )

    if not warnings:

        await ctx.send(
            t(
                ctx.author,
                "warning_none",
                target=member.mention
            )
        )

        return

    embed = discord.Embed(
        title=t(
            ctx.author,
            "warnings_title",
            target=member.display_name
        )
    )

    for index, warning in enumerate(
        warnings,
        start=1
    ):

        moderator_id, reason, created_at = warning

        embed.add_field(
            name=f"Warning #{index}",
            value=(
                f"**Reason:** {reason}\n"
                f"**Moderator:** <@{moderator_id}>\n"
                f"**Date:** {created_at}"
            ),
            inline=False
        )

    await ctx.send(
        embed=embed
    )


# =========================================================
# CLEAR WARNINGS
# =========================================================

@bot.tree.command(
    name="clearwarns",
    description="Clear all warnings from a member"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def slash_clearwarns(
    interaction: discord.Interaction,
    member: discord.Member
):

    count = clear_warnings(
        interaction.guild.id,
        member.id
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "warnings_cleared",
            target=member.mention,
            count=count
        )
    )


@bot.command(name="clearwarns")
@commands.has_permissions(moderate_members=True)
async def prefix_clearwarns(
    ctx,
    member: discord.Member
):

    count = clear_warnings(
        ctx.guild.id,
        member.id
    )

    await ctx.send(
        t(
            ctx.author,
            "warnings_cleared",
            target=member.mention,
            count=count
        )
    )


# =========================================================
# MUTE
# =========================================================

@bot.tree.command(
    name="mute",
    description="Mute a member using Discord timeout"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def slash_mute(
    interaction: discord.Interaction,
    member: discord.Member,
    duration: str,
    reason: str = "No reason provided"
):

    if member == interaction.user:

        await interaction.response.send_message(
            t(
                interaction.user,
                "cannot_self"
            ),
            ephemeral=True
        )

        return

    if member.bot:

        await interaction.response.send_message(
            t(
                interaction.user,
                "bot_target"
            ),
            ephemeral=True
        )

        return

    if member == interaction.guild.me:

        await interaction.response.send_message(
            t(
                interaction.user,
                "cannot_moderate"
            ),
            ephemeral=True
        )

        return

    seconds = parse_duration(duration)

    if seconds is None:

        await interaction.response.send_message(
            t(
                interaction.user,
                "mute_invalid_time"
            ),
            ephemeral=True
        )

        return

    if seconds > MAX_MUTE_SECONDS:

        await interaction.response.send_message(
            t(
                interaction.user,
                "mute_too_long"
            ),
            ephemeral=True
        )

        return

    try:

        until = (
            discord.utils.utcnow()
            + timedelta(seconds=seconds)
        )

        await member.timeout(
            until,
            reason=reason
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "mute_success",
                target=member.mention,
                duration=format_duration(seconds),
                reason=reason
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            t(
                interaction.user,
                "cannot_moderate"
            ),
            ephemeral=True
        )


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def prefix_mute(
    ctx,
    member: discord.Member,
    duration: str,
    *,
    reason="No reason provided"
):

    if member == ctx.author:

        await ctx.send(
            t(
                ctx.author,
                "cannot_self"
            )
        )

        return

    if member.bot:

        await ctx.send(
            t(
                ctx.author,
                "bot_target"
            )
        )

        return

    if member == ctx.guild.me:

        await ctx.send(
            t(
                ctx.author,
                "cannot_moderate"
            )
        )

        return

    seconds = parse_duration(duration)

    if seconds is None:

        await ctx.send(
            t(
                ctx.author,
                "mute_invalid_time"
            )
        )

        return

    if seconds > MAX_MUTE_SECONDS:

        await ctx.send(
            t(
                ctx.author,
                "mute_too_long"
            )
        )

        return

    try:

        until = (
            discord.utils.utcnow()
            + timedelta(seconds=seconds)
        )

        await member.timeout(
            until,
            reason=reason
        )

        await ctx.send(
            t(
                ctx.author,
                "mute_success",
                target=member.mention,
                duration=format_duration(seconds),
                reason=reason
            )
        )

    except discord.Forbidden:

        await ctx.send(
            t(
                ctx.author,
                "cannot_moderate"
            )
        )


# =========================================================
# UNMUTE
# =========================================================

@bot.tree.command(
    name="unmute",
    description="Remove a member's timeout"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def slash_unmute(
    interaction: discord.Interaction,
    member: discord.Member
):

    try:

        await member.timeout(
            None,
            reason=f"Unmuted by {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "unmute_success",
                target=member.mention
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            t(
                interaction.user,
                "cannot_moderate"
            ),
            ephemeral=True
        )


@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def prefix_unmute(
    ctx,
    member: discord.Member
):

    try:

        await member.timeout(
            None,
            reason=f"Unmuted by {ctx.author}"
        )

        await ctx.send(
            t(
                ctx.author,
                "unmute_success",
                target=member.mention
            )
        )

    except discord.Forbidden:

        await ctx.send(
            t(
                ctx.author,
                "cannot_moderate"
            )
        )


# =========================================================
# AFK
# =========================================================

@bot.tree.command(
    name="afk",
    description="Set yourself as AFK"
)
async def slash_afk(
    interaction: discord.Interaction,
    reason: str
):

    member = interaction.user

    existing = get_afk(
        interaction.guild.id,
        member.id
    )

    if existing:

        await interaction.response.send_message(
            "You are already AFK.",
            ephemeral=True
        )

        return

    original_nick = member.nick

    set_afk(
        interaction.guild.id,
        member.id,
        reason,
        original_nick
    )

    try:

        if not member.display_name.startswith("[AFK]"):

            new_nick = f"[AFK] {member.display_name}"

            if len(new_nick) > 32:
                new_nick = new_nick[:32]

            await member.edit(
                nick=new_nick,
                reason="AFK"
            )

    except discord.Forbidden:
        pass

    await interaction.response.send_message(
        f"💤 {t(member, 'afk_set')}\n"
        f"**{t(member, 'afk_reason')}:** {reason}"
    )


@bot.command(name="afk")
async def prefix_afk(
    ctx,
    *,
    reason: str
):

    member = ctx.author

    existing = get_afk(
        ctx.guild.id,
        member.id
    )

    if existing:

        await ctx.send(
            "You are already AFK."
        )

        return

    original_nick = member.nick

    set_afk(
        ctx.guild.id,
        member.id,
        reason,
        original_nick
    )

    try:

        if not member.display_name.startswith("[AFK]"):

            new_nick = f"[AFK] {member.display_name}"

            if len(new_nick) > 32:
                new_nick = new_nick[:32]

            await member.edit(
                nick=new_nick,
                reason="AFK"
            )

    except discord.Forbidden:
        pass

    await ctx.send(
        f"💤 {t(member, 'afk_set')}\n"
        f"**{t(member, 'afk_reason')}:** {reason}"
    )


# =========================================================
# AFK DEACTIVATE
# =========================================================

async def deactivate_afk(
    message,
    afk_data
):

    reason, original_nick = afk_data

    removed = remove_afk(
        message.guild.id,
        message.author.id
    )

    if removed:

        try:

            await message.author.edit(
                nick=original_nick,
                reason="AFK ended"
            )

        except discord.Forbidden:
            pass

        rows = get_afk_messages(
            message.guild.id,
            message.author.id
        )

        for sender_id, stored_message, created_at in rows:

            try:

                sender = await bot.fetch_user(
                    sender_id
                )

                await message.author.send(
                    f"💬 **Message from {sender}:**\n"
                    f"{stored_message}"
                )

            except Exception:
                pass

        clear_afk_messages(
            message.guild.id,
            message.author.id
        )

        msg = await message.channel.send(
            t(
                message.author,
                "afk_back",
                username=message.author.mention
            )
        )

        await asyncio.sleep(2)

        try:
            await msg.delete()
        except discord.NotFound:
            pass


# =========================================================
# ON MESSAGE
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is None:

        await bot.process_commands(message)

        return

    # -----------------------------------------------------
    # Message statistics
    # -----------------------------------------------------

    if is_message_counting_enabled(
        message.guild.id
    ):

        record_message(
            message.guild.id,
            message.author.id,
            message.channel.id
        )

    # -----------------------------------------------------
    # Remove AFK when user speaks
    # -----------------------------------------------------

    afk_data = get_afk(
        message.guild.id,
        message.author.id
    )

    if afk_data:

        await deactivate_afk(
            message,
            afk_data
        )

    # -----------------------------------------------------
    # Detect mentions of AFK users
    # -----------------------------------------------------

    for mentioned in message.mentions:

        if mentioned.bot:
            continue

        afk_data = get_afk(
            message.guild.id,
            mentioned.id
        )

        if not afk_data:
            continue

        reason, original_nick = afk_data

        view = AFKMessageView(
            message.guild.id,
            mentioned.id
        )

        await message.channel.send(
            f"💤 {t(
                message.author,
                'afk_user',
                username=mentioned.mention
            )}\n"
            f"**{t(message.author, 'afk_reason')}:** {reason}",
            view=view
        )

    # -----------------------------------------------------
    # Commands
    # -----------------------------------------------------

    await bot.process_commands(message)


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🤖 Abel Moderation Bot")
    print(f"👤 Bot: {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"🌐 Servidores: {len(bot.guilds)}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print("📋 Comandos disponibles:")
    print("   /membercount")
    print("   /ban")
    print("   /kick")
    print("   /unban")
    print("   /setnick")
    print("   /nick")
    print("   /purge")
    print("   /prefix")
    print("   /am")
    print("   /aset")
    print("   /aenable")
    print("   /adesable")
    print("   /promote")
    print("   /demote")
    print("   /role add")
    print("   /role remove")
    print("   /warn")
    print("   /warnings")
    print("   /clearwarns")
    print("   /mute")
    print("   /unmute")
    print("   /afk")


# =========================================================
# ERROR HANDLERS
# =========================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.send(
            "❌ You don't have permission to use this command."
        )

        return

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.send(
            "❌ Missing required argument."
        )

        return

    if isinstance(
        error,
        commands.BadArgument
    ):

        await ctx.send(
            "❌ Invalid argument. Make sure you mentioned the correct user."
        )

        return

    print(
        f"❌ Command error: {error}"
    )


@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ You don't have permission "
            "to use this command."
        )

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

        return

    print(
        f"❌ Slash command error: {error}"
    )


# =========================================================
# START
# =========================================================

print("🚀 Starting Abel Moderation Bot...")

bot.run(TOKEN)