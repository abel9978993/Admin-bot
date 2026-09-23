import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
import asyncio
from datetime import datetime, timezone, timedelta


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("MEMBERCOUNT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "❌ MEMBERCOUNT_TOKEN no está configurado."
    )

AFK_TIMEOUT_SECONDS = 60 * 60
MAX_WARNINGS = 3


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.presences = True


# =========================================================
# PREFIX DATABASE
# =========================================================

PREFIX_DB = "prefixes.db"

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


# =========================================================
# TRANSLATIONS
# =========================================================

TRANSLATIONS = {
    "en": {
        "membercount_title": "Member Count",
        "membercount_text": "This server has **{count} members**.",

        "no_permission": "❌ You don't have permission to use this command.",
        "user_not_found": "❌ User not found.",
        "cannot_self": "❌ You cannot use this command on yourself.",

        "banned": "🔨 {user} has been banned.",
        "kicked": "👢 {user} has been kicked.",
        "unbanned": "✅ User `{user}` has been unbanned.",

        "nickname_changed": "✅ {target}'s nickname has been changed to **{nickname}**.",
        "nickname_failed": "❌ I couldn't change that nickname.",

        "purged": "🧹 Deleted **{amount} messages**.",

        "prefix_changed": "✅ The server prefix is now `{prefix}`.",

        "stats_disabled": "❌ Message statistics are disabled in this server.",
        "stats_title": "📊 Message Statistics",
        "stats_for": "Statistics for {member}",
        "today": "Today",
        "week": "This week",
        "month": "This month",
        "total": "Total",
        "stats_set": "✅ {period} messages for {member} set to **{amount}**.",
        "stats_enabled": "✅ Message statistics have been enabled.",
        "stats_disabled_success": "✅ Message statistics have been disabled.",

        "promoted": "⬆️ {target} has been promoted.",
        "demoted": "⬇️ {target} has been demoted.",

        "role_added": "✅ Role {role} added to {member}.",
        "role_removed": "✅ Role {role} removed from {member}.",
        "role_failed": "❌ I couldn't modify that role.",

        "afk_enabled": "💤 You are now AFK.\n**Reason:** {reason}",
        "afk_mention": "💤 {member} is currently AFK.\n**Reason:** {reason}",
        "back": "👋 {username} is no longer AFK.",
        "afk_message_saved": "💌 Your message has been saved and will be delivered when {member} returns.",
        "afk_dm": "💌 **AFK message from {sender}** in **{server}**:\n{message}",

        "warn_added": "⚠️ {member} has received a warning.\n**Reason:** {reason}\n**Warnings:** {count}/{max}",
        "warn_timeout": "⏱️ {member} has reached **{max} warnings** and has been timed out for **1 hour**.",
        "warnings_title": "⚠️ Warnings",
        "warnings_for": "Warnings for {member}",
        "no_warnings": "✅ {member} has no warnings.",
        "warning_line": "**#{number}** — {reason}\nBy: {moderator}\n{date}",
        "warnings_cleared": "🧹 All warnings for {member} have been cleared.",
        "warning_invalid": "❌ The warning number is invalid.",

        "leave_message": "Leave a message",
        "message_modal_title": "Leave a message",
        "message_modal_label": "Your message",
        "message_modal_placeholder": "Write your message..."
    },

    "es": {
        "membercount_title": "Cantidad de miembros",
        "membercount_text": "Este servidor tiene **{count} miembros**.",

        "no_permission": "❌ No tienes permisos para usar este comando.",
        "user_not_found": "❌ Usuario no encontrado.",
        "cannot_self": "❌ No puedes usar este comando contigo mismo.",

        "banned": "🔨 {user} ha sido baneado.",
        "kicked": "👢 {user} ha sido expulsado.",
        "unbanned": "✅ El usuario `{user}` ha sido desbaneado.",

        "nickname_changed": "✅ El apodo de {target} ha sido cambiado a **{nickname}**.",
        "nickname_failed": "❌ No pude cambiar ese apodo.",

        "purged": "🧹 Se han eliminado **{amount} mensajes**.",

        "prefix_changed": "✅ El prefijo del servidor ahora es `{prefix}`.",

        "stats_disabled": "❌ Las estadísticas de mensajes están desactivadas en este servidor.",
        "stats_title": "📊 Estadísticas de mensajes",
        "stats_for": "Estadísticas de {member}",
        "today": "Hoy",
        "week": "Esta semana",
        "month": "Este mes",
        "total": "Total",
        "stats_set": "✅ Los mensajes de {period} de {member} se han establecido en **{amount}**.",
        "stats_enabled": "✅ Las estadísticas de mensajes han sido activadas.",
        "stats_disabled_success": "✅ Las estadísticas de mensajes han sido desactivadas.",

        "promoted": "⬆️ {target} ha sido ascendido.",
        "demoted": "⬇️ {target} ha sido degradado.",

        "role_added": "✅ El rol {role} ha sido añadido a {member}.",
        "role_removed": "✅ El rol {role} ha sido eliminado de {member}.",
        "role_failed": "❌ No pude modificar ese rol.",

        "afk_enabled": "💤 Ahora estás AFK.\n**Motivo:** {reason}",
        "afk_mention": "💤 {member} está AFK.\n**Motivo:** {reason}",
        "back": "👋 {username} ya no está AFK.",
        "afk_message_saved": "💌 Tu mensaje se ha guardado y será enviado cuando {member} vuelva.",
        "afk_dm": "💌 **Mensaje AFK de {sender}** en **{server}**:\n{message}",

        "warn_added": "⚠️ {member} ha recibido una advertencia.\n**Motivo:** {reason}\n**Warnings:** {count}/{max}",
        "warn_timeout": "⏱️ {member} ha llegado a **{max} warnings** y ha recibido un timeout de **1 hora**.",
        "warnings_title": "⚠️ Advertencias",
        "warnings_for": "Advertencias de {member}",
        "no_warnings": "✅ {member} no tiene advertencias.",
        "warning_line": "**#{number}** — {reason}\nPor: {moderator}\n{date}",
        "warnings_cleared": "🧹 Se han eliminado todas las advertencias de {member}.",
        "warning_invalid": "❌ El número de advertencia no es válido.",

        "leave_message": "Dejar un mensaje",
        "message_modal_title": "Dejar un mensaje",
        "message_modal_label": "Tu mensaje",
        "message_modal_placeholder": "Escribe tu mensaje..."
    }
}


def get_language(user):
    locale = getattr(user, "locale", None)

    if locale:
        locale = str(locale).lower()

        if locale.startswith("es"):
            return "es"

    return "en"


def t(user, key, **kwargs):
    language = get_language(user)

    text = TRANSLATIONS.get(
        language,
        TRANSLATIONS["en"]
    ).get(
        key,
        TRANSLATIONS["en"].get(key, key)
    )

    return text.format(**kwargs)


# =========================================================
# MESSAGE STATS DATABASE
# =========================================================

MESSAGES_DB = "messages.db"

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


def stats_enabled(guild_id):

    with sqlite3.connect(MESSAGES_DB) as conn:
        row = conn.execute(
            "SELECT enabled FROM message_settings WHERE guild_id = ?",
            (guild_id,)
        ).fetchone()

    if row is None:
        return True

    return bool(row[0])


def set_stats_enabled(guild_id, enabled):

    with sqlite3.connect(MESSAGES_DB) as conn:

        conn.execute("""
            INSERT INTO message_settings (guild_id, enabled)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET enabled = excluded.enabled
        """, (
            guild_id,
            1 if enabled else 0
        ))

        conn.commit()


def record_message(guild_id, user_id, channel_id):

    if not stats_enabled(guild_id):
        return

    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(MESSAGES_DB) as conn:

        conn.execute("""
            INSERT INTO messages
            (guild_id, user_id, channel_id, created_at)
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

        return datetime(
            now.year,
            now.month,
            now.day,
            tzinfo=timezone.utc
        )

    if period == "week":

        start = now - timedelta(
            days=now.weekday()
        )

        return datetime(
            start.year,
            start.month,
            start.day,
            tzinfo=timezone.utc
        )

    if period == "month":

        return datetime(
            now.year,
            now.month,
            1,
            tzinfo=timezone.utc
        )

    return None


def get_real_count(
    guild_id,
    user_id,
    period
):

    if period == "total":

        query = """
            SELECT COUNT(*)
            FROM messages
            WHERE guild_id = ?
            AND user_id = ?
        """

        params = (
            guild_id,
            user_id
        )

    else:

        start = get_period_start(
            period
        )

        query = """
            SELECT COUNT(*)
            FROM messages
            WHERE guild_id = ?
            AND user_id = ?
            AND created_at >= ?
        """

        params = (
            guild_id,
            user_id,
            start.isoformat()
        )

    with sqlite3.connect(MESSAGES_DB) as conn:

        row = conn.execute(
            query,
            params
        ).fetchone()

    return row[0] if row else 0


def get_adjustment(
    guild_id,
    user_id,
    period
):

    with sqlite3.connect(MESSAGES_DB) as conn:

        row = conn.execute("""
            SELECT amount, reference_real, period_start
            FROM message_adjustments
            WHERE guild_id = ?
            AND user_id = ?
            AND period = ?
        """, (
            guild_id,
            user_id,
            period
        )).fetchone()

    if not row:
        return 0

    amount, reference_real, saved_start = row

    if period != "total":

        current_start = get_period_start(
            period
        ).isoformat()

        if saved_start != current_start:
            return 0

    current_real = get_real_count(
        guild_id,
        user_id,
        period
    )

    return amount + (
        current_real - reference_real
    )


def set_adjustment(
    guild_id,
    user_id,
    period,
    amount
):

    real = get_real_count(
        guild_id,
        user_id,
        period
    )

    start = None

    if period != "total":

        start = get_period_start(
            period
        ).isoformat()

    with sqlite3.connect(MESSAGES_DB) as conn:

        conn.execute("""
            INSERT INTO message_adjustments
            (
                guild_id,
                user_id,
                period,
                amount,
                reference_real,
                period_start
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(guild_id, user_id, period)
            DO UPDATE SET
                amount = excluded.amount,
                reference_real = excluded.reference_real,
                period_start = excluded.period_start
        """, (
            guild_id,
            user_id,
            period,
            amount,
            real,
            start
        ))

        conn.commit()


# =========================================================
# WARNINGS DATABASE
# =========================================================

WARNINGS_DB = "warnings.db"

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

    now = datetime.now(
        timezone.utc
    ).isoformat()

    with sqlite3.connect(WARNINGS_DB) as conn:

        cursor = conn.execute("""
            INSERT INTO warnings
            (
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

        warning_id = cursor.lastrowid

        conn.commit()

    return warning_id


def get_warning_count(
    guild_id,
    user_id
):

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


def get_warnings(
    guild_id,
    user_id
):

    with sqlite3.connect(WARNINGS_DB) as conn:

        rows = conn.execute("""
            SELECT
                id,
                moderator_id,
                reason,
                created_at
            FROM warnings
            WHERE guild_id = ?
            AND user_id = ?
            ORDER BY id ASC
        """, (
            guild_id,
            user_id
        )).fetchall()

    return rows


def clear_warnings(
    guild_id,
    user_id
):

    with sqlite3.connect(WARNINGS_DB) as conn:

        conn.execute("""
            DELETE FROM warnings
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        ))

        conn.commit()


# =========================================================
# AFK DATABASE
# =========================================================

AFK_DB = "afk.db"

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


def get_afk(
    guild_id,
    user_id
):

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

    return row


def save_afk(
    guild_id,
    user_id,
    reason,
    original_nick
):

    with sqlite3.connect(AFK_DB) as conn:

        conn.execute("""
            INSERT INTO afk
            (
                guild_id,
                user_id,
                reason,
                original_nick
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET
                reason = excluded.reason,
                original_nick = excluded.original_nick
        """, (
            guild_id,
            user_id,
            reason,
            original_nick
        ))

        conn.commit()


def delete_afk(
    guild_id,
    user_id
):

    with sqlite3.connect(AFK_DB) as conn:

        conn.execute("""
            DELETE FROM afk
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id
        ))

        conn.commit()


def save_afk_message(
    guild_id,
    afk_user_id,
    sender_id,
    message
):

    now = datetime.now(
        timezone.utc
    ).isoformat()

    with sqlite3.connect(AFK_DB) as conn:

        conn.execute("""
            INSERT INTO afk_messages
            (
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


def get_afk_messages(
    guild_id,
    user_id
):

    with sqlite3.connect(AFK_DB) as conn:

        rows = conn.execute("""
            SELECT sender_id, message
            FROM afk_messages
            WHERE guild_id = ?
            AND afk_user_id = ?
            ORDER BY id ASC
        """, (
            guild_id,
            user_id
        )).fetchall()

    return rows


def delete_afk_messages(
    guild_id,
    user_id
):

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


# =========================================================
# AFK MODAL
# =========================================================

class AFKMessageModal(discord.ui.Modal):

    def __init__(
        self,
        guild_id,
        afk_user_id
    ):

        super().__init__(
            title="Leave a message"
        )

        self.guild_id = guild_id
        self.afk_user_id = afk_user_id

        self.message_input = discord.ui.TextInput(
            label="Your message",
            placeholder="Write your message...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )

        self.add_item(
            self.message_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        save_afk_message(
            self.guild_id,
            self.afk_user_id,
            interaction.user.id,
            str(self.message_input.value)
        )

        member = interaction.guild.get_member(
            self.afk_user_id
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "afk_message_saved",
                member=member.mention if member else "the user"
            ),
            ephemeral=True
        )


class AFKMessageView(discord.ui.View):

    def __init__(
        self,
        guild_id,
        afk_user_id
    ):

        super().__init__(
            timeout=3600
        )

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

        await interaction.response.send_modal(
            AFKMessageModal(
                self.guild_id,
                self.afk_user_id
            )
        )


# =========================================================
# BOT
# =========================================================

class MyBot(commands.Bot):

    async def setup_hook(self):

        print(
            "🔄 Sincronizando comandos globales..."
        )

        try:

            synced = await self.tree.sync()

            print(
                f"✅ {len(synced)} comandos globales sincronizados."
            )

            print(
                "📋 Comandos disponibles:"
            )

            for command in synced:

                print(
                    f"   /{command.name}"
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
# READY
# =========================================================

@bot.event
async def on_ready():

    print("")
    print("======================================")
    print("🤖 Abel Moderation Bot")
    print("======================================")
    print(f"👤 Bot: {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"🌐 Servidores: {len(bot.guilds)}")
    print("✅ Bot conectado correctamente.")
    print("======================================")
    print("")


# =========================================================
# MEMBERCOUNT
# =========================================================

@bot.command(name="membercount")
async def membercount_prefix(ctx):

    await ctx.send(
        t(
            ctx.author,
            "membercount_text",
            count=ctx.guild.member_count
        )
    )


@bot.tree.command(
    name="membercount",
    description="Show the server member count"
)
async def membercount_slash(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        t(
            interaction.user,
            "membercount_text",
            count=interaction.guild.member_count
        )
    )


# =========================================================
# BAN
# =========================================================

@bot.command(name="ban")
@commands.has_permissions(
    ban_members=True
)
async def ban_prefix(
    ctx,
    member: discord.Member,
    *,
    reason: str = "No reason provided"
):

    if member == ctx.author:

        await ctx.send(
            t(ctx.author, "cannot_self")
        )
        return

    try:

        await member.ban(
            reason=reason
        )

        await ctx.send(
            t(
                ctx.author,
                "banned",
                user=member.mention
            )
        )

    except Exception:

        await ctx.send(
            "❌ I couldn't ban that user."
        )


@bot.tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def ban_slash(
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

    try:

        await member.ban(
            reason=reason
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "banned",
                user=member.mention
            )
        )

    except Exception:

        await interaction.response.send_message(
            "❌ I couldn't ban that user.",
            ephemeral=True
        )


# =========================================================
# KICK
# =========================================================

@bot.command(name="kick")
@commands.has_permissions(
    kick_members=True
)
async def kick_prefix(
    ctx,
    member: discord.Member,
    *,
    reason: str = "No reason provided"
):

    if member == ctx.author:

        await ctx.send(
            t(ctx.author, "cannot_self")
        )
        return

    try:

        await member.kick(
            reason=reason
        )

        await ctx.send(
            t(
                ctx.author,
                "kicked",
                user=member.mention
            )
        )

    except Exception:

        await ctx.send(
            "❌ I couldn't kick that user."
        )


@bot.tree.command(
    name="kick",
    description="Kick a member"
)
@app_commands.checks.has_permissions(
    kick_members=True
)
async def kick_slash(
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

    try:

        await member.kick(
            reason=reason
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "kicked",
                user=member.mention
            )
        )

    except Exception:

        await interaction.response.send_message(
            "❌ I couldn't kick that user.",
            ephemeral=True
        )


# =========================================================
# UNBAN
# =========================================================

@bot.command(name="unban")
@commands.has_permissions(
    ban_members=True
)
async def unban_prefix(
    ctx,
    user_id: int
):

    try:

        user = await bot.fetch_user(
            user_id
        )

        await ctx.guild.unban(
            user
        )

        await ctx.send(
            t(
                ctx.author,
                "unbanned",
                user=user_id
            )
        )

    except Exception:

        await ctx.send(
            "❌ I couldn't unban that user."
        )


@bot.tree.command(
    name="unban",
    description="Unban a user by ID"
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def unban_slash(
    interaction: discord.Interaction,
    user_id: str
):

    try:

        user = await bot.fetch_user(
            int(user_id)
        )

        await interaction.guild.unban(
            user
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "unbanned",
                user=user_id
            )
        )

    except Exception:

        await interaction.response.send_message(
            "❌ I couldn't unban that user.",
            ephemeral=True
        )


# =========================================================
# SETNICK
# =========================================================

@bot.command(name="setnick")
@commands.has_permissions(
    manage_nicknames=True
)
async def setnick_prefix(
    ctx,
    member: discord.Member,
    *,
    nickname: str
):

    try:

        await member.edit(
            nick=nickname
        )

        await ctx.send(
            t(
                ctx.author,
                "nickname_changed",
                target=member.mention,
                nickname=nickname
            )
        )

    except Exception:

        await ctx.send(
            t(
                ctx.author,
                "nickname_failed"
            )
        )


@bot.tree.command(
    name="setnick",
    description="Change a member's nickname"
)
@app_commands.checks.has_permissions(
    manage_nicknames=True
)
async def setnick_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    nickname: str
):

    try:

        await member.edit(
            nick=nickname
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "nickname_changed",
                target=member.mention,
                nickname=nickname
            )
        )

    except Exception:

        await interaction.response.send_message(
            t(
                interaction.user,
                "nickname_failed"
            ),
            ephemeral=True
        )


# =========================================================
# NICK
# =========================================================

@bot.command(name="nick")
@commands.has_permissions(
    manage_nicknames=True
)
async def nick_prefix(
    ctx,
    member: discord.Member = None,
    *,
    nickname: str = None
):

    if member is None:
        member = ctx.author

    if nickname is None:

        await ctx.send(
            "Usage: ?nick @user nickname"
        )
        return

    try:

        await member.edit(
            nick=nickname
        )

        await ctx.send(
            t(
                ctx.author,
                "nickname_changed",
                target=member.mention,
                nickname=nickname
            )
        )

    except Exception:

        await ctx.send(
            t(
                ctx.author,
                "nickname_failed"
            )
        )


# =========================================================
# PURGE
# =========================================================

@bot.command(name="purge")
@commands.has_permissions(
    manage_messages=True
)
async def purge_prefix(
    ctx,
    amount: int
):

    if amount < 1 or amount > 100:

        await ctx.send(
            "❌ Amount must be between 1 and 100."
        )
        return

    deleted = await ctx.channel.purge(
        limit=amount + 1
    )

    msg = await ctx.send(
        t(
            ctx.author,
            "purged",
            amount=max(
                0,
                len(deleted) - 1
            )
        )
    )

    await asyncio.sleep(3)

    try:
        await msg.delete()
    except Exception:
        pass


@bot.tree.command(
    name="purge",
    description="Delete messages"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def purge_slash(
    interaction: discord.Interaction,
    amount: app_commands.Range[
        int,
        1,
        100
    ]
):

    deleted = await interaction.channel.purge(
        limit=amount
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "purged",
            amount=len(deleted)
        ),
        ephemeral=True
    )


# =========================================================
# PREFIX
# =========================================================

@bot.command(name="prefix")
@commands.has_permissions(
    manage_guild=True
)
async def prefix_prefix(
    ctx,
    new_prefix: str
):

    if len(new_prefix) > 5:

        await ctx.send(
            "❌ The prefix can be maximum 5 characters."
        )
        return

    set_prefix(
        ctx.guild.id,
        new_prefix
    )

    await ctx.send(
        t(
            ctx.author,
            "prefix_changed",
            prefix=new_prefix
        )
    )


@bot.tree.command(
    name="prefix",
    description="Change the server prefix"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def prefix_slash(
    interaction: discord.Interaction,
    new_prefix: str
):

    if len(new_prefix) > 5:

        await interaction.response.send_message(
            "❌ The prefix can be maximum 5 characters.",
            ephemeral=True
        )
        return

    set_prefix(
        interaction.guild.id,
        new_prefix
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "prefix_changed",
            prefix=new_prefix
        )
    )


# =========================================================
# AM
# =========================================================

@bot.command(name="am")
async def am_prefix(
    ctx,
    member: discord.Member = None
):

    if not stats_enabled(
        ctx.guild.id
    ):

        await ctx.send(
            t(
                ctx.author,
                "stats_disabled"
            )
        )
        return

    member = member or ctx.author

    today = get_adjustment(
        ctx.guild.id,
        member.id,
        "today"
    )

    week = get_adjustment(
        ctx.guild.id,
        member.id,
        "week"
    )

    month = get_adjustment(
        ctx.guild.id,
        member.id,
        "month"
    )

    total = get_adjustment(
        ctx.guild.id,
        member.id,
        "total"
    )

    embed = discord.Embed(
        title=t(
            ctx.author,
            "stats_title"
        ),
        description=t(
            ctx.author,
            "stats_for",
            member=member.mention
        )
    )

    embed.add_field(
        name=t(
            ctx.author,
            "today"
        ),
        value=f"**{today}**",
        inline=True
    )

    embed.add_field(
        name=t(
            ctx.author,
            "week"
        ),
        value=f"**{week}**",
        inline=True
    )

    embed.add_field(
        name=t(
            ctx.author,
            "month"
        ),
        value=f"**{month}**",
        inline=True
    )

    embed.add_field(
        name=t(
            ctx.author,
            "total"
        ),
        value=f"**{total}**",
        inline=False
    )

    await ctx.send(
        embed=embed
    )


@bot.tree.command(
    name="am",
    description="View message statistics"
)
async def am_slash(
    interaction: discord.Interaction,
    member: discord.Member | None = None
):

    if not stats_enabled(
        interaction.guild.id
    ):

        await interaction.response.send_message(
            t(
                interaction.user,
                "stats_disabled"
            ),
            ephemeral=True
        )
        return

    member = member or interaction.user

    today = get_adjustment(
        interaction.guild.id,
        member.id,
        "today"
    )

    week = get_adjustment(
        interaction.guild.id,
        member.id,
        "week"
    )

    month = get_adjustment(
        interaction.guild.id,
        member.id,
        "month"
    )

    total = get_adjustment(
        interaction.guild.id,
        member.id,
        "total"
    )

    embed = discord.Embed(
        title=t(
            interaction.user,
            "stats_title"
        ),
        description=t(
            interaction.user,
            "stats_for",
            member=member.mention
        )
    )

    embed.add_field(
        name=t(
            interaction.user,
            "today"
        ),
        value=f"**{today}**",
        inline=True
    )

    embed.add_field(
        name=t(
            interaction.user,
            "week"
        ),
        value=f"**{week}**",
        inline=True
    )

    embed.add_field(
        name=t(
            interaction.user,
            "month"
        ),
        value=f"**{month}**",
        inline=True
    )

    embed.add_field(
        name=t(
            interaction.user,
            "total"
        ),
        value=f"**{total}**",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# ASET
# =========================================================

PERIOD_CHOICES = [
    app_commands.Choice(
        name="Today",
        value="today"
    ),
    app_commands.Choice(
        name="This week",
        value="week"
    ),
    app_commands.Choice(
        name="This month",
        value="month"
    ),
    app_commands.Choice(
        name="Total",
        value="total"
    )
]


@bot.command(name="aset")
@commands.has_permissions(
    administrator=True
)
async def aset_prefix(
    ctx,
    period: str,
    amount: int,
    member: discord.Member = None
):

    aliases = {
        "hoy": "today",
        "semana": "week",
        "mes": "month"
    }

    period = aliases.get(
        period.lower(),
        period.lower()
    )

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

    if amount < 0:

        await ctx.send(
            "❌ Amount cannot be negative."
        )
        return

    member = member or ctx.author

    set_adjustment(
        ctx.guild.id,
        member.id,
        period,
        amount
    )

    period_name = {
        "today": t(
            ctx.author,
            "today"
        ),
        "week": t(
            ctx.author,
            "week"
        ),
        "month": t(
            ctx.author,
            "month"
        ),
        "total": t(
            ctx.author,
            "total"
        )
    }[period]

    await ctx.send(
        t(
            ctx.author,
            "stats_set",
            period=period_name,
            member=member.mention,
            amount=amount
        )
    )


@bot.tree.command(
    name="aset",
    description="Set message statistics"
)
@app_commands.checks.has_permissions(
    administrator=True
)
@app_commands.choices(
    period=PERIOD_CHOICES
)
async def aset_slash(
    interaction: discord.Interaction,
    period: app_commands.Choice[str],
    amount: app_commands.Range[
        int,
        0,
        1000000000
    ],
    member: discord.Member | None = None
):

    member = member or interaction.user

    set_adjustment(
        interaction.guild.id,
        member.id,
        period.value,
        amount
    )

    period_name = {
        "today": t(
            interaction.user,
            "today"
        ),
        "week": t(
            interaction.user,
            "week"
        ),
        "month": t(
            interaction.user,
            "month"
        ),
        "total": t(
            interaction.user,
            "total"
        )
    }[period.value]

    await interaction.response.send_message(
        t(
            interaction.user,
            "stats_set",
            period=period_name,
            member=member.mention,
            amount=amount
        )
    )


# =========================================================
# ENABLE / DISABLE STATS
# =========================================================

@bot.command(name="aenable")
@commands.has_permissions(
    administrator=True
)
async def aenable_prefix(ctx):

    set_stats_enabled(
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
    name="aenable",
    description="Enable message statistics"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def aenable_slash(
    interaction: discord.Interaction
):

    set_stats_enabled(
        interaction.guild.id,
        True
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "stats_enabled"
        )
    )


@bot.command(name="adesable")
@commands.has_permissions(
    administrator=True
)
async def adesable_prefix(ctx):

    set_stats_enabled(
        ctx.guild.id,
        False
    )

    await ctx.send(
        t(
            ctx.author,
            "stats_disabled_success"
        )
    )


@bot.tree.command(
    name="adesable",
    description="Disable message statistics"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def adesable_slash(
    interaction: discord.Interaction
):

    set_stats_enabled(
        interaction.guild.id,
        False
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "stats_disabled_success"
        )
    )


# =========================================================
# PROMOTE
# =========================================================

@bot.command(name="promote")
@commands.has_permissions(
    manage_roles=True
)
async def promote_prefix(
    ctx,
    member: discord.Member
):

    current = member.top_role

    available = [
        role
        for role in ctx.guild.roles
        if role.position > current.position
        and role < ctx.guild.me.top_role
        and role != ctx.guild.default_role
    ]

    if not available:

        await ctx.send(
            "❌ There is no higher role available."
        )
        return

    new_role = min(
        available,
        key=lambda role: role.position
    )

    try:

        await member.add_roles(
            new_role,
            reason=f"Promoted by {ctx.author}"
        )

        await ctx.send(
            t(
                ctx.author,
                "promoted",
                target=member.mention
            )
        )

    except Exception:

        await ctx.send(
            "❌ I couldn't promote that member."
        )


@bot.tree.command(
    name="promote",
    description="Promote a member"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def promote_slash(
    interaction: discord.Interaction,
    member: discord.Member
):

    current = member.top_role

    available = [
        role
        for role in interaction.guild.roles
        if role.position > current.position
        and role < interaction.guild.me.top_role
        and role != interaction.guild.default_role
    ]

    if not available:

        await interaction.response.send_message(
            "❌ There is no higher role available.",
            ephemeral=True
        )
        return

    new_role = min(
        available,
        key=lambda role: role.position
    )

    try:

        await member.add_roles(
            new_role,
            reason=f"Promoted by {interaction.user}"
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "promoted",
                target=member.mention
            )
        )

    except Exception:

        await interaction.response.send_message(
            "❌ I couldn't promote that member.",
            ephemeral=True
        )


# =========================================================
# DEMOTE
# =========================================================

@bot.command(name="demote")
@commands.has_permissions(
    manage_roles=True
)
async def demote_prefix(
    ctx,
    member: discord.Member
):

    manageable = [
        role
        for role in member.roles
        if role != ctx.guild.default_role
        and role < ctx.guild.me.top_role
    ]

    if not manageable:

        await ctx.send(
            "❌ This member has no manageable role."
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

    except Exception:

        await ctx.send(
            "❌ I couldn't demote that member."
        )


@bot.tree.command(
    name="demote",
    description="Demote a member"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def demote_slash(
    interaction: discord.Interaction,
    member: discord.Member
):

    manageable = [
        role
        for role in member.roles
        if role != interaction.guild.default_role
        and role < interaction.guild.me.top_role
    ]

    if not manageable:

        await interaction.response.send_message(
            "❌ This member has no manageable role.",
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

    except Exception:

        await interaction.response.send_message(
            "❌ I couldn't demote that member.",
            ephemeral=True
        )


# =========================================================
# ROLE
# =========================================================

role_group = app_commands.Group(
    name="role",
    description="Manage member roles"
)


@role_group.command(
    name="add",
    description="Add a role to a member"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def role_add_slash(
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
            role
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_added",
                role=role.mention,
                member=member.mention
            )
        )

    except Exception:

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_failed"
            ),
            ephemeral=True
        )


@role_group.command(
    name="remove",
    description="Remove a role from a member"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def role_remove_slash(
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
            role
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_removed",
                role=role.mention,
                member=member.mention
            )
        )

    except Exception:

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_failed"
            ),
            ephemeral=True
        )


bot.tree.add_command(
    role_group
)


@bot.group(
    name="role",
    invoke_without_command=True
)
@commands.has_permissions(
    manage_roles=True
)
async def role_prefix(ctx):

    await ctx.send(
        "Usage:\n"
        "`?role add @user @role`\n"
        "`?role remove @user @role`"
    )


@role_prefix.command(name="add")
@commands.has_permissions(
    manage_roles=True
)
async def role_add_prefix(
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
            role
        )

        await ctx.send(
            t(
                ctx.author,
                "role_added",
                role=role.mention,
                member=member.mention
            )
        )

    except Exception:

        await ctx.send(
            t(
                ctx.author,
                "role_failed"
            )
        )


@role_prefix.command(name="remove")
@commands.has_permissions(
    manage_roles=True
)
async def role_remove_prefix(
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
            role
        )

        await ctx.send(
            t(
                ctx.author,
                "role_removed",
                role=role.mention,
                member=member.mention
            )
        )

    except Exception:

        await ctx.send(
            t(
                ctx.author,
                "role_failed"
            )
        )


# =========================================================
# WARN
# =========================================================

@bot.command(name="warn")
@commands.has_permissions(
    moderate_members=True
)
async def warn_prefix(
    ctx,
    member: discord.Member,
    *,
    reason: str = "No reason provided"
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
            "❌ You cannot warn a bot."
        )
        return

    warning_id = add_warning(
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
            "warn_added",
            member=member.mention,
            reason=reason,
            count=count,
            max=MAX_WARNINGS
        )
    )

    if count >= MAX_WARNINGS:

        try:

            until = discord.utils.utcnow() + timedelta(
                seconds=AFK_TIMEOUT_SECONDS
            )

            await member.timeout(
                until,
                reason=f"Reached {MAX_WARNINGS} warnings"
            )

            await ctx.send(
                t(
                    ctx.author,
                    "warn_timeout",
                    member=member.mention,
                    max=MAX_WARNINGS
                )
            )

        except Exception as e:

            print(
                f"❌ Could not timeout warned user: {e}"
            )


@bot.tree.command(
    name="warn",
    description="Give a member a warning"
)
@app_commands.checks.has_permissions(
    moderate_members=True
)
async def warn_slash(
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
            "❌ You cannot warn a bot.",
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
            "warn_added",
            member=member.mention,
            reason=reason,
            count=count,
            max=MAX_WARNINGS
        )
    )

    if count >= MAX_WARNINGS:

        try:

            until = discord.utils.utcnow() + timedelta(
                seconds=AFK_TIMEOUT_SECONDS
            )

            await member.timeout(
                until,
                reason=f"Reached {MAX_WARNINGS} warnings"
            )

            await interaction.followup.send(
                t(
                    interaction.user,
                    "warn_timeout",
                    member=member.mention,
                    max=MAX_WARNINGS
                )
            )

        except Exception as e:

            print(
                f"❌ Could not timeout warned user: {e}"
            )


# =========================================================
# WARNINGS
# =========================================================

@bot.command(name="warnings")
async def warnings_prefix(
    ctx,
    member: discord.Member = None
):

    member = member or ctx.author

    rows = get_warnings(
        ctx.guild.id,
        member.id
    )

    if not rows:

        await ctx.send(
            t(
                ctx.author,
                "no_warnings",
                member=member.mention
            )
        )
        return

    embed = discord.Embed(
        title=t(
            ctx.author,
            "warnings_title"
        ),
        description=t(
            ctx.author,
            "warnings_for",
            member=member.mention
        )
    )

    for index, row in enumerate(
        rows,
        start=1
    ):

        warning_id, moderator_id, reason, created_at = row

        try:

            date = datetime.fromisoformat(
                created_at
            ).strftime(
                "%Y-%m-%d %H:%M UTC"
            )

        except Exception:

            date = created_at

        moderator = ctx.guild.get_member(
            moderator_id
        )

        moderator_name = (
            moderator.mention
            if moderator
            else f"<@{moderator_id}>"
        )

        embed.add_field(
            name=f"Warning #{index}",
            value=t(
                ctx.author,
                "warning_line",
                number=index,
                reason=reason,
                moderator=moderator_name,
                date=date
            ),
            inline=False
        )

    await ctx.send(
        embed=embed
    )


@bot.tree.command(
    name="warnings",
    description="View a member's warnings"
)
async def warnings_slash(
    interaction: discord.Interaction,
    member: discord.Member | None = None
):

    member = member or interaction.user

    rows = get_warnings(
        interaction.guild.id,
        member.id
    )

    if not rows:

        await interaction.response.send_message(
            t(
                interaction.user,
                "no_warnings",
                member=member.mention
            )
        )
        return

    embed = discord.Embed(
        title=t(
            interaction.user,
            "warnings_title"
        ),
        description=t(
            interaction.user,
            "warnings_for",
            member=member.mention
        )
    )

    for index, row in enumerate(
        rows,
        start=1
    ):

        warning_id, moderator_id, reason, created_at = row

        try:

            date = datetime.fromisoformat(
                created_at
            ).strftime(
                "%Y-%m-%d %H:%M UTC"
            )

        except Exception:

            date = created_at

        moderator = interaction.guild.get_member(
            moderator_id
        )

        moderator_name = (
            moderator.mention
            if moderator
            else f"<@{moderator_id}>"
        )

        embed.add_field(
            name=f"Warning #{index}",
            value=t(
                interaction.user,
                "warning_line",
                number=index,
                reason=reason,
                moderator=moderator_name,
                date=date
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# CLEAR WARNS
# =========================================================

@bot.command(name="clearwarns")
@commands.has_permissions(
    moderate_members=True
)
async def clearwarns_prefix(
    ctx,
    member: discord.Member
):

    clear_warnings(
        ctx.guild.id,
        member.id
    )

    await ctx.send(
        t(
            ctx.author,
            "warnings_cleared",
            member=member.mention
        )
    )


@bot.tree.command(
    name="clearwarns",
    description="Clear all warnings from a member"
)
@app_commands.checks.has_permissions(
    moderate_members=True
)
async def clearwarns_slash(
    interaction: discord.Interaction,
    member: discord.Member
):

    clear_warnings(
        interaction.guild.id,
        member.id
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "warnings_cleared",
            member=member.mention
        )
    )


# =========================================================
# AFK
# =========================================================

async def activate_afk(
    member: discord.Member,
    reason: str
):

    current = get_afk(
        member.guild.id,
        member.id
    )

    if current:

        save_afk(
            member.guild.id,
            member.id,
            reason,
            current[1]
        )

        return

    original_nick = member.nick

    save_afk(
        member.guild.id,
        member.id,
        reason,
        original_nick
    )

    display_name = member.display_name

    if not display_name.startswith("[AFK]"):

        display_name = (
            f"[AFK] {display_name}"
        )

    display_name = display_name[:32]

    try:

        await member.edit(
            nick=display_name,
            reason="AFK enabled"
        )

    except Exception:

        pass


async def deactivate_afk(
    member: discord.Member
):

    data = get_afk(
        member.guild.id,
        member.id
    )

    if not data:
        return []

    reason, original_nick = data

    pending_messages = get_afk_messages(
        member.guild.id,
        member.id
    )

    try:

        await member.edit(
            nick=original_nick,
            reason="AFK removed"
        )

    except Exception:

        pass

    delete_afk(
        member.guild.id,
        member.id
    )

    delete_afk_messages(
        member.guild.id,
        member.id
    )

    return pending_messages


@bot.command(name="afk")
async def afk_prefix(
    ctx,
    *,
    reason: str
):

    await activate_afk(
        ctx.author,
        reason
    )

    await ctx.send(
        t(
            ctx.author,
            "afk_enabled",
            reason=reason
        )
    )


@bot.tree.command(
    name="afk",
    description="Set your AFK status"
)
async def afk_slash(
    interaction: discord.Interaction,
    reason: str
):

    await activate_afk(
        interaction.user,
        reason
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "afk_enabled",
            reason=reason
        )
    )


# =========================================================
# ON MESSAGE
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is None:

        await bot.process_commands(
            message
        )

        return

    # -----------------------------------------
    # MESSAGE STATS
    # -----------------------------------------

    record_message(
        message.guild.id,
        message.author.id,
        message.channel.id
    )

    # -----------------------------------------
    # AFK RETURN
    # -----------------------------------------

    own_afk = get_afk(
        message.guild.id,
        message.author.id
    )

    if own_afk:

        pending_messages = await deactivate_afk(
            message.author
        )

        back_message = await message.channel.send(
            t(
                message.author,
                "back",
                username=message.author.mention
            )
        )

        # AFK return message stays for 2 seconds
        await asyncio.sleep(2)

        try:

            await back_message.delete()

        except Exception:

            pass

        # Send saved AFK messages by DM

        for sender_id, saved_message in pending_messages:

            sender = message.guild.get_member(
                sender_id
            )

            sender_name = (
                sender.display_name
                if sender
                else "Unknown user"
            )

            try:

                await message.author.send(
                    t(
                        message.author,
                        "afk_dm",
                        sender=sender_name,
                        server=message.guild.name,
                        message=saved_message
                    )
                )

            except Exception:

                pass

    # -----------------------------------------
    # AFK MENTIONS
    # -----------------------------------------

    for mentioned in message.mentions:

        if mentioned.bot:
            continue

        if mentioned.id == message.author.id:
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
            t(
                message.author,
                "afk_mention",
                member=mentioned.mention,
                reason=reason
            ),
            view=view
        )

    # -----------------------------------------
    # PREFIX COMMANDS
    # -----------------------------------------

    await bot.process_commands(
        message
    )


# =========================================================
# PREFIX ERRORS
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
            t(
                ctx.author,
                "no_permission"
            )
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
        commands.MemberNotFound
    ):

        await ctx.send(
            t(
                ctx.author,
                "user_not_found"
            )
        )
        return

    if isinstance(
        error,
        commands.BadArgument
    ):

        await ctx.send(
            "❌ Invalid argument."
        )
        return

    print(
        f"❌ Prefix command error: {error}"
    )


# =========================================================
# SLASH ERRORS
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = t(
            interaction.user,
            "no_permission"
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

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                "❌ An error occurred.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ An error occurred.",
                ephemeral=True
            )

    except Exception:

        pass


# =========================================================
# START
# =========================================================

print(
    "🚀 Starting Abel Moderation Bot..."
)

bot.run(TOKEN)