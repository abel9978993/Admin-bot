import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime, timezone, timedelta
import os


# ============================================================
# CONFIGURACIÓN
# ============================================================

TOKEN = os.getenv("MEMBERCOUNT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "❌ No se encontró MEMBERCOUNT_TOKEN. "
        "Añade esta variable en Railway o en las variables de entorno."
    )


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True


# ============================================================
# BASES DE DATOS
# ============================================================

PREFIX_DB = "prefixes.db"
MESSAGES_DB = "messages.db"
AFK_DB = "afk.db"


# ============================================================
# PREFIX
# ============================================================

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


# ============================================================
# MESSAGE DATABASE
# ============================================================

def init_message_db():
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


def is_message_tracking_enabled(guild_id):
    with sqlite3.connect(MESSAGES_DB) as conn:
        row = conn.execute(
            "SELECT enabled FROM message_settings WHERE guild_id = ?",
            (guild_id,)
        ).fetchone()

    if row is None:
        return True

    return bool(row[0])


def set_message_tracking(guild_id, enabled):
    with sqlite3.connect(MESSAGES_DB) as conn:
        conn.execute("""
            INSERT INTO message_settings (guild_id, enabled)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET enabled = excluded.enabled
        """, (guild_id, 1 if enabled else 0))

        conn.commit()


def save_message(guild_id, user_id, channel_id):
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


def get_real_count(guild_id, user_id, period):
    if period == "total":

        with sqlite3.connect(MESSAGES_DB) as conn:
            row = conn.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE guild_id = ?
                AND user_id = ?
            """, (
                guild_id,
                user_id
            )).fetchone()

        return row[0] if row else 0

    start = get_period_start(period)

    if start is None:
        return 0

    with sqlite3.connect(MESSAGES_DB) as conn:
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

    return row[0] if row else 0


def get_adjusted_count(guild_id, user_id, period):
    real_count = get_real_count(
        guild_id,
        user_id,
        period
    )

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

    if row is None:
        return real_count

    amount, reference_real, period_start = row

    if period != "total":

        current_start = get_period_start(period)

        if period_start != current_start.isoformat():
            return real_count

    difference = real_count - reference_real

    return amount + difference


def set_adjusted_count(guild_id, user_id, period, amount):
    real_count = get_real_count(
        guild_id,
        user_id,
        period
    )

    if period == "total":
        period_start = None
    else:
        period_start = get_period_start(period).isoformat()

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
            real_count,
            period_start
        ))

        conn.commit()


# ============================================================
# AFK DATABASE
# ============================================================

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

        conn.commit()


def set_afk(guild_id, user_id, reason, original_nick):
    with sqlite3.connect(AFK_DB) as conn:
        conn.execute("""
            INSERT INTO afk (
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


def get_afk(guild_id, user_id):
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


def remove_afk(guild_id, user_id):
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


# ============================================================
# BOT CLASS
# ============================================================

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
    intents=intents
)


commands_cleaned = False


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    global commands_cleaned

    print("=" * 50)
    print(f"✅ Bot conectado como {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"🌐 Servidores: {len(bot.guilds)}")
    print("=" * 50)

    if not commands_cleaned:

        print("🧹 Limpiando comandos antiguos de servidores...")

        for guild in bot.guilds:

            try:

                old_commands = await bot.tree.fetch_commands(
                    guild=guild
                )

                if old_commands:

                    bot.tree.clear_commands(
                        guild=guild
                    )

                    await bot.tree.sync(
                        guild=guild
                    )

                    print(
                        f"🧹 Comandos antiguos eliminados: "
                        f"{guild.name}"
                    )

            except Exception as e:

                print(
                    f"⚠️ Error limpiando {guild.name}: {e}"
                )

        commands_cleaned = True

        try:

            synced = await bot.tree.sync()

            print(
                f"🌐 {len(synced)} comandos globales activos."
            )

        except Exception as e:

            print(
                f"❌ Error sincronizando globales: {e}"
            )


# ============================================================
# AFK
# ============================================================

async def activate_afk(
    guild,
    member,
    reason
):

    existing = get_afk(
        guild.id,
        member.id
    )

    if existing:

        original_nick = existing[1]

    else:

        original_nick = member.nick

    new_nick = f"[AFK] {member.display_name}"

    if new_nick.startswith("[AFK] [AFK]"):
        new_nick = member.display_name

    # Guardamos el nickname original
    set_afk(
        guild.id,
        member.id,
        reason,
        original_nick
    )

    try:

        if guild.me.guild_permissions.manage_nicknames:

            if len(new_nick) > 32:
                new_nick = new_nick[:32]

            await member.edit(
                nick=new_nick,
                reason="AFK activado"
            )

    except discord.Forbidden:

        pass

    return True


async def deactivate_afk(
    guild,
    member
):

    data = get_afk(
        guild.id,
        member.id
    )

    if not data:
        return False

    reason, original_nick = data

    try:

        if guild.me.guild_permissions.manage_nicknames:

            await member.edit(
                nick=original_nick,
                reason="AFK eliminado al hablar"
            )

    except discord.Forbidden:

        pass

    remove_afk(
        guild.id,
        member.id
    )

    return True


# ============================================================
# AFK PREFIX
# ============================================================

@bot.command(name="afk")
async def afk_prefix(ctx, *, reason=None):

    if ctx.guild is None:
        return

    if not reason or not reason.strip():

        await ctx.send(
            "❌ Tienes que poner un motivo.\n"
            f"Ejemplo: `{get_prefix(ctx.guild.id)}afk Estoy ocupado`"
        )

        return

    await activate_afk(
        ctx.guild,
        ctx.author,
        reason.strip()
    )

    await ctx.send(
        f"💤 **AFK set** — {ctx.author.mention}\n"
        f"**Motivo:** {reason.strip()}"
    )


# ============================================================
# AFK SLASH
# ============================================================

@bot.tree.command(
    name="afk",
    description="Activa tu estado AFK"
)
@app_commands.describe(
    reason="El motivo por el que estás AFK"
)
async def afk_slash(
    interaction: discord.Interaction,
    reason: str
):

    if interaction.guild is None:
        return

    if not reason.strip():

        await interaction.response.send_message(
            "❌ Tienes que poner un motivo.",
            ephemeral=True
        )

        return

    member = interaction.user

    if not isinstance(member, discord.Member):

        member = interaction.guild.get_member(
            interaction.user.id
        )

    await activate_afk(
        interaction.guild,
        member,
        reason.strip()
    )

    await interaction.response.send_message(
        f"💤 **AFK set**\n"
        f"**Motivo:** {reason.strip()}"
    )


# ============================================================
# MEMBERCOUNT
# ============================================================

@bot.command(name="membercount")
async def membercount_prefix(ctx):

    if ctx.guild is None:
        return

    await ctx.send(
        f"👥 **{ctx.guild.name}** tiene "
        f"**{ctx.guild.member_count:,}** miembros."
    )


@bot.tree.command(
    name="membercount",
    description="Muestra el número de miembros del servidor"
)
async def membercount_slash(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        f"👥 **{interaction.guild.name}** tiene "
        f"**{interaction.guild.member_count:,}** miembros."
    )


# ============================================================
# BAN
# ============================================================

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_prefix(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    await member.ban(reason=reason)

    await ctx.send(
        f"🔨 **{member}** ha sido baneado.\n"
        f"**Razón:** {reason}"
    )


@bot.tree.command(
    name="ban",
    description="Banea a un miembro"
)
@app_commands.describe(
    member="Miembro que quieres banear",
    reason="Razón del baneo"
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def ban_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    await member.ban(reason=reason)

    await interaction.response.send_message(
        f"🔨 **{member}** ha sido baneado.\n"
        f"**Razón:** {reason}"
    )


# ============================================================
# KICK
# ============================================================

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_prefix(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    await member.kick(reason=reason)

    await ctx.send(
        f"👢 **{member}** ha sido expulsado.\n"
        f"**Razón:** {reason}"
    )


@bot.tree.command(
    name="kick",
    description="Expulsa a un miembro"
)
@app_commands.describe(
    member="Miembro que quieres expulsar",
    reason="Razón de la expulsión"
)
@app_commands.checks.has_permissions(
    kick_members=True
)
async def kick_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    await member.kick(reason=reason)

    await interaction.response.send_message(
        f"👢 **{member}** ha sido expulsado.\n"
        f"**Razón:** {reason}"
    )


# ============================================================
# UNBAN
# ============================================================

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_prefix(
    ctx,
    user_id: int
):

    try:

        user = await bot.fetch_user(user_id)

        await ctx.guild.unban(user)

        await ctx.send(
            f"🔓 **{user}** ha sido desbaneado."
        )

    except discord.NotFound:

        await ctx.send(
            "❌ Ese usuario no está baneado."
        )


@bot.tree.command(
    name="unban",
    description="Desbanea un usuario por ID"
)
@app_commands.describe(
    user_id="ID del usuario"
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

        await interaction.guild.unban(user)

        await interaction.response.send_message(
            f"🔓 **{user}** ha sido desbaneado."
        )

    except (ValueError, discord.NotFound):

        await interaction.response.send_message(
            "❌ Ese usuario no está baneado o la ID no es válida.",
            ephemeral=True
        )


# ============================================================
# SETNICK
# ============================================================

async def execute_setnick(
    ctx_or_interaction,
    target,
    nickname
):

    guild = (
        ctx_or_interaction.guild
    )

    actor = (
        ctx_or_interaction.author
        if isinstance(
            ctx_or_interaction,
            commands.Context
        )
        else ctx_or_interaction.user
    )

    if target.id != actor.id:

        if not actor.guild_permissions.manage_nicknames:

            message = (
                "❌ No tienes permiso para cambiar "
                "el nickname de otros usuarios."
            )

            if isinstance(
                ctx_or_interaction,
                commands.Context
            ):
                await ctx_or_interaction.send(message)
            else:
                await ctx_or_interaction.response.send_message(
                    message,
                    ephemeral=True
                )

            return

    if target.id == guild.owner_id:

        message = (
            "❌ No puedes cambiar el nickname "
            "del dueño del servidor."
        )

        if isinstance(
            ctx_or_interaction,
            commands.Context
        ):
            await ctx_or_interaction.send(message)
        else:
            await ctx_or_interaction.response.send_message(
                message,
                ephemeral=True
            )

        return

    bot_member = guild.me

    if target.top_role >= bot_member.top_role:

        message = (
            "❌ No puedo cambiar el nickname de ese usuario "
            "porque su rol está por encima o al mismo nivel que el mío."
        )

        if isinstance(
            ctx_or_interaction,
            commands.Context
        ):
            await ctx_or_interaction.send(message)
        else:
            await ctx_or_interaction.response.send_message(
                message,
                ephemeral=True
            )

        return

    if len(nickname) > 32:

        message = (
            "❌ El nickname no puede tener más de 32 caracteres."
        )

        if isinstance(
            ctx_or_interaction,
            commands.Context
        ):
            await ctx_or_interaction.send(message)
        else:
            await ctx_or_interaction.response.send_message(
                message,
                ephemeral=True
            )

        return

    try:

        await target.edit(
            nick=nickname,
            reason=f"Cambio de nickname por {actor}"
        )

        message = (
            f"✅ Nickname de **{target}** cambiado a "
            f"**{nickname}**."
        )

        if isinstance(
            ctx_or_interaction,
            commands.Context
        ):
            await ctx_or_interaction.send(message)
        else:
            await ctx_or_interaction.response.send_message(
                message
            )

    except discord.Forbidden:

        message = (
            "❌ No tengo permiso para cambiar ese nickname."
        )

        if isinstance(
            ctx_or_interaction,
            commands.Context
        ):
            await ctx_or_interaction.send(message)
        else:
            await ctx_or_interaction.response.send_message(
                message,
                ephemeral=True
            )


@bot.command(
    name="setnick",
    aliases=["nick"]
)
@commands.has_permissions(
    manage_nicknames=True
)
async def setnick_prefix(
    ctx,
    *args
):

    if not args:

        await ctx.send(
            f"❌ Uso: `{get_prefix(ctx.guild.id)}setnick @usuario nickname`"
        )

        return

    try:

        target = await commands.MemberConverter().convert(
            ctx,
            args[0]
        )

        nickname = " ".join(args[1:]).strip()

        if not nickname:

            await ctx.send(
                "❌ Tienes que poner el nuevo nickname."
            )

            return

    except commands.BadArgument:

        target = ctx.author
        nickname = " ".join(args).strip()

    await execute_setnick(
        ctx,
        target,
        nickname
    )


@bot.tree.command(
    name="setnick",
    description="Cambia el nickname de un usuario"
)
@app_commands.describe(
    member="Usuario",
    nickname="Nuevo nickname"
)
@app_commands.checks.has_permissions(
    manage_nicknames=True
)
async def setnick_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    nickname: str
):

    await execute_setnick(
        interaction,
        member,
        nickname
    )


# ============================================================
# PURGE
# ============================================================

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
            "❌ El número debe estar entre 1 y 100."
        )

        return

    deleted = await ctx.channel.purge(
        limit=amount + 1
    )

    msg = await ctx.send(
        f"🧹 Se eliminaron **{len(deleted) - 1}** mensajes."
    )

    await msg.delete(delay=3)


@bot.tree.command(
    name="purge",
    description="Elimina mensajes del canal"
)
@app_commands.describe(
    amount="Cantidad de mensajes"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def purge_slash(
    interaction: discord.Interaction,
    amount: int
):

    if amount < 1 or amount > 100:

        await interaction.response.send_message(
            "❌ El número debe estar entre 1 y 100.",
            ephemeral=True
        )

        return

    await interaction.channel.purge(
        limit=amount
    )

    await interaction.response.send_message(
        f"🧹 Se eliminaron **{amount}** mensajes.",
        ephemeral=True
    )


# ============================================================
# PREFIX
# ============================================================

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
            "❌ El prefix no puede tener más de 5 caracteres."
        )

        return

    set_prefix(
        ctx.guild.id,
        new_prefix
    )

    await ctx.send(
        f"✅ Prefix cambiado a `{new_prefix}`"
    )


@bot.tree.command(
    name="prefix",
    description="Cambia el prefix del servidor"
)
@app_commands.describe(
    new_prefix="Nuevo prefix"
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
            "❌ El prefix no puede tener más de 5 caracteres.",
            ephemeral=True
        )

        return

    set_prefix(
        interaction.guild.id,
        new_prefix
    )

    await interaction.response.send_message(
        f"✅ Prefix cambiado a `{new_prefix}`"
    )


# ============================================================
# MESSAGE STATS EMBED
# ============================================================

def create_am_embed(
    guild,
    member
):

    today = get_adjusted_count(
        guild.id,
        member.id,
        "today"
    )

    week = get_adjusted_count(
        guild.id,
        member.id,
        "week"
    )

    month = get_adjusted_count(
        guild.id,
        member.id,
        "month"
    )

    total = get_adjusted_count(
        guild.id,
        member.id,
        "total"
    )

    embed = discord.Embed(
        title=f"📊 Message Stats — {member.display_name}",
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(
        name="📅 Hoy",
        value=f"**{today:,}**",
        inline=True
    )

    embed.add_field(
        name="📆 Esta semana",
        value=f"**{week:,}**",
        inline=True
    )

    embed.add_field(
        name="🗓️ Este mes",
        value=f"**{month:,}**",
        inline=True
    )

    embed.add_field(
        name="📈 Total",
        value=f"**{total:,}**",
        inline=True
    )

    return embed


def create_disabled_am_embed(guild):

    prefix = get_prefix(
        guild.id
    )

    embed = discord.Embed(
        title="🛑 Conteo de mensajes desactivado",
        description=(
            "El sistema de conteo de mensajes "
            "**no está activado** en este servidor.\n\n"
            "Las estadísticas de mensajes no están disponibles "
            "mientras esta opción esté desactivada.\n\n"
            "Un administrador puede activarlo usando:\n"
            f"`{prefix}aenable`\n"
            "o\n"
            "`/aenable`"
        ),
        color=discord.Color.red()
    )

    return embed


# ============================================================
# AM PREFIX
# ============================================================

@bot.command(name="am")
async def am_prefix(
    ctx,
    member: discord.Member = None
):

    if ctx.guild is None:
        return

    if not is_message_tracking_enabled(
        ctx.guild.id
    ):

        await ctx.send(
            embed=create_disabled_am_embed(
                ctx.guild
            )
        )

        return

    if member is None:
        member = ctx.author

    await ctx.send(
        embed=create_am_embed(
            ctx.guild,
            member
        )
    )


# ============================================================
# AM SLASH
# ============================================================

@bot.tree.command(
    name="am",
    description="Muestra las estadísticas de mensajes"
)
@app_commands.describe(
    member="Usuario del que quieres ver las estadísticas"
)
async def am_slash(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    if not is_message_tracking_enabled(
        interaction.guild.id
    ):

        await interaction.response.send_message(
            embed=create_disabled_am_embed(
                interaction.guild
            ),
            ephemeral=True
        )

        return

    if member is None:
        member = interaction.user

    await interaction.response.send_message(
        embed=create_am_embed(
            interaction.guild,
            member
        )
    )


# ============================================================
# ASET
# ============================================================

PERIOD_TRANSLATIONS = {
    "hoy": "today",
    "today": "today",

    "semana": "week",
    "week": "week",

    "mes": "month",
    "month": "month",

    "total": "total"
}


@bot.command(name="aset")
@commands.has_permissions(
    administrator=True
)
async def aset_prefix(
    ctx,
    period: str,
    amount: int
):

    period_key = PERIOD_TRANSLATIONS.get(
        period.lower()
    )

    if period_key is None:

        await ctx.send(
            "❌ Periodo inválido.\n"
            "Usa: `hoy`, `semana`, `mes` o `total`."
        )

        return

    if amount < 0:

        await ctx.send(
            "❌ La cantidad no puede ser negativa."
        )

        return

    set_adjusted_count(
        ctx.guild.id,
        ctx.author.id,
        period_key,
        amount
    )

    await ctx.send(
        f"✅ Tus mensajes de **{period_key}** "
        f"han sido establecidos en **{amount:,}**."
    )


@bot.tree.command(
    name="aset",
    description="Establece las estadísticas de mensajes"
)
@app_commands.describe(
    period="Periodo",
    amount="Cantidad"
)
@app_commands.choices(
    period=[
        app_commands.Choice(
            name="Hoy",
            value="today"
        ),
        app_commands.Choice(
            name="Semana",
            value="week"
        ),
        app_commands.Choice(
            name="Mes",
            value="month"
        ),
        app_commands.Choice(
            name="Total",
            value="total"
        )
    ]
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def aset_slash(
    interaction: discord.Interaction,
    period: app_commands.Choice[str],
    amount: int
):

    if amount < 0:

        await interaction.response.send_message(
            "❌ La cantidad no puede ser negativa.",
            ephemeral=True
        )

        return

    set_adjusted_count(
        interaction.guild.id,
        interaction.user.id,
        period.value,
        amount
    )

    await interaction.response.send_message(
        f"✅ Tus mensajes de **{period.name}** "
        f"han sido establecidos en **{amount:,}**."
    )


# ============================================================
# AENABLE
# ============================================================

@bot.command(name="aenable")
@commands.has_permissions(
    administrator=True
)
async def aenable_prefix(ctx):

    set_message_tracking(
        ctx.guild.id,
        True
    )

    await ctx.send(
        "✅ **Message counting enabled.**\n"
        "Los nuevos mensajes volverán a contarse."
    )


@bot.tree.command(
    name="aenable",
    description="Activa el conteo de mensajes"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def aenable_slash(
    interaction: discord.Interaction
):

    set_message_tracking(
        interaction.guild.id,
        True
    )

    await interaction.response.send_message(
        "✅ **Message counting enabled.**\n"
        "Los nuevos mensajes volverán a contarse."
    )


# ============================================================
# ADESABLE
# ============================================================

@bot.command(name="adesable")
@commands.has_permissions(
    administrator=True
)
async def adesable_prefix(ctx):

    set_message_tracking(
        ctx.guild.id,
        False
    )

    await ctx.send(
        "🛑 **Message counting disabled.**\n"
        "Los nuevos mensajes ya no serán contados."
    )


@bot.tree.command(
    name="adesable",
    description="Desactiva el conteo de mensajes"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def adesable_slash(
    interaction: discord.Interaction
):

    set_message_tracking(
        interaction.guild.id,
        False
    )

    await interaction.response.send_message(
        "🛑 **Message counting disabled.**\n"
        "Los nuevos mensajes ya no serán contados."
    )


# ============================================================
# ROLES
# ============================================================

def get_manageable_roles(guild):

    bot_member = guild.me

    roles = []

    for role in guild.roles:

        if role.is_default():
            continue

        if role.managed:
            continue

        if role >= bot_member.top_role:
            continue

        roles.append(role)

    return roles


def get_promote_roles(
    guild,
    member
):

    roles = get_manageable_roles(
        guild
    )

    current = member.top_role

    return [
        role
        for role in roles
        if role > current
    ]


def get_demote_roles(
    guild,
    member
):

    roles = get_manageable_roles(
        guild
    )

    current = member.top_role

    return [
        role
        for role in roles
        if role < current
    ]


class RoleSelect(discord.ui.Select):

    def __init__(
        self,
        requester,
        target,
        mode
    ):

        self.requester = requester
        self.target = target
        self.mode = mode

        guild = target.guild

        if mode == "promote":
            roles = get_promote_roles(
                guild,
                target
            )
        else:
            roles = get_demote_roles(
                guild,
                target
            )

        roles = roles[:25]

        options = []

        for role in roles:

            options.append(
                discord.SelectOption(
                    label=role.name[:100],
                    value=str(role.id)
                )
            )

        super().__init__(
            placeholder=(
                "Select a role to promote"
                if mode == "promote"
                else "Select a role to demote"
            ),
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.user.id != self.requester.id:

            await interaction.response.send_message(
                "❌ Este menú no es para ti.",
                ephemeral=True
            )

            return

        role_id = int(
            self.values[0]
        )

        role = interaction.guild.get_role(
            role_id
        )

        if role is None:

            await interaction.response.send_message(
                "❌ Ese rol ya no existe.",
                ephemeral=True
            )

            return

        try:

            if self.target.top_role != interaction.guild.default_role:

                await self.target.remove_roles(
                    self.target.top_role
                )

            await self.target.add_roles(
                role
            )

            await interaction.response.edit_message(
                content=(
                    f"✅ {self.target.mention} "
                    f"ahora tiene el rol {role.mention}."
                ),
                view=None
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ No tengo permisos para gestionar ese rol.",
                ephemeral=True
            )


class RoleView(discord.ui.View):

    def __init__(
        self,
        requester,
        target,
        mode
    ):

        super().__init__(
            timeout=60
        )

        select = RoleSelect(
            requester,
            target,
            mode
        )

        self.add_item(select)


async def execute_role_change(
    interaction,
    target,
    mode
):

    actor = interaction.user

    if target.id == actor.id:

        await interaction.response.send_message(
            "❌ No puedes utilizar este comando contigo mismo.",
            ephemeral=True
        )

        return

    if target.id == interaction.guild.owner_id:

        await interaction.response.send_message(
            "❌ No puedes modificar al dueño del servidor.",
            ephemeral=True
        )

        return

    if mode == "promote":

        roles = get_promote_roles(
            interaction.guild,
            target
        )

    else:

        roles = get_demote_roles(
            interaction.guild,
            target
        )

    if not roles:

        await interaction.response.send_message(
            "❌ No hay roles disponibles.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        (
            "⬆️ Selecciona el rol al que quieres ascender al usuario."
            if mode == "promote"
            else
            "⬇️ Selecciona el rol al que quieres descender al usuario."
        ),
        view=RoleView(
            actor,
            target,
            mode
        ),
        ephemeral=True
    )


# ============================================================
# PROMOTE
# ============================================================

@bot.command(name="promote")
@commands.has_permissions(
    manage_roles=True
)
async def promote_prefix(
    ctx,
    member: discord.Member
):

    roles = get_promote_roles(
        ctx.guild,
        member
    )

    if not roles:

        await ctx.send(
            "❌ No hay roles disponibles para ascender a ese usuario."
        )

        return

    view = RoleView(
        ctx.author,
        member,
        "promote"
    )

    await ctx.send(
        f"⬆️ Selecciona el nuevo rol para {member.mention}.",
        view=view
    )


@bot.tree.command(
    name="promote",
    description="Asciende a un usuario"
)
@app_commands.describe(
    member="Usuario"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def promote_slash(
    interaction: discord.Interaction,
    member: discord.Member
):

    await execute_role_change(
        interaction,
        member,
        "promote"
    )


# ============================================================
# DEMOTE
# ============================================================

@bot.command(name="demote")
@commands.has_permissions(
    manage_roles=True
)
async def demote_prefix(
    ctx,
    member: discord.Member
):

    roles = get_demote_roles(
        ctx.guild,
        member
    )

    if not roles:

        await ctx.send(
            "❌ No hay roles disponibles para descender a ese usuario."
        )

        return

    view = RoleView(
        ctx.author,
        member,
        "demote"
    )

    await ctx.send(
        f"⬇️ Selecciona el nuevo rol para {member.mention}.",
        view=view
    )


@bot.tree.command(
    name="demote",
    description="Desciende a un usuario"
)
@app_commands.describe(
    member="Usuario"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def demote_slash(
    interaction: discord.Interaction,
    member: discord.Member
):

    await execute_role_change(
        interaction,
        member,
        "demote"
    )


# ============================================================
# ROLE GROUP
# ============================================================

role_group = app_commands.Group(
    name="role",
    description="Gestiona los roles"
)


@role_group.command(
    name="add",
    description="Añade un rol a un usuario"
)
@app_commands.describe(
    member="Usuario",
    role="Rol"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def role_add(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    if role.is_default() or role.managed:

        await interaction.response.send_message(
            "❌ No puedes gestionar ese rol.",
            ephemeral=True
        )

        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ Ese rol está por encima de mi rol.",
            ephemeral=True
        )

        return

    try:

        await member.add_roles(
            role
        )

        await interaction.response.send_message(
            f"✅ Se añadió {role.mention} a {member.mention}."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ No tengo permisos para añadir ese rol.",
            ephemeral=True
        )


@role_group.command(
    name="remove",
    description="Quita un rol a un usuario"
)
@app_commands.describe(
    member="Usuario",
    role="Rol"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def role_remove(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    if role.is_default() or role.managed:

        await interaction.response.send_message(
            "❌ No puedes gestionar ese rol.",
            ephemeral=True
        )

        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ Ese rol está por encima de mi rol.",
            ephemeral=True
        )

        return

    try:

        await member.remove_roles(
            role
        )

        await interaction.response.send_message(
            f"✅ Se quitó {role.mention} de {member.mention}."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ No tengo permisos para quitar ese rol.",
            ephemeral=True
        )


bot.tree.add_command(
    role_group
)


# ============================================================
# MESSAGE EVENTS
# ============================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is None:
        await bot.process_commands(message)
        return

    # --------------------------------------------------------
    # QUITAR AFK AL HABLAR
    # --------------------------------------------------------

    afk_data = get_afk(
        message.guild.id,
        message.author.id
    )

    if afk_data:

        current_prefix = get_prefix(
            message.guild.id
        )

        content = message.content.strip()

        afk_command = (
            content == f"{current_prefix}afk"
            or content.startswith(
                f"{current_prefix}afk "
            )
        )

        # Si no está usando el comando AFK,
        # hablar elimina el AFK.
        if not afk_command:

            removed = await deactivate_afk(
                message.guild,
                message.author
            )

            if removed:

                try:

                    await message.channel.send(
                        f"👋 {message.author.mention} "
                        f"ya no está AFK."
                    )

                except discord.Forbidden:

                    pass

    # --------------------------------------------------------
    # CONTADOR DE MENSAJES
    # --------------------------------------------------------

    if is_message_tracking_enabled(
        message.guild.id
    ):

        save_message(
            message.guild.id,
            message.author.id,
            message.channel.id
        )

    # --------------------------------------------------------
    # PREFIX COMMANDS
    # --------------------------------------------------------

    await bot.process_commands(
        message
    )


# ============================================================
# ERROR HANDLING PREFIX
# ============================================================

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
            "❌ No tienes permisos para usar este comando."
        )

        return

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.send(
            "❌ Faltan argumentos para este comando."
        )

        return

    if isinstance(
        error,
        commands.BadArgument
    ):

        await ctx.send(
            "❌ El argumento introducido no es válido."
        )

        return

    if isinstance(
        error,
        commands.NoPrivateMessage
    ):

        await ctx.send(
            "❌ Este comando solo funciona en servidores."
        )

        return

    print(
        f"❌ Error en comando {ctx.command}: {error}"
    )


# ============================================================
# ERROR HANDLING SLASH
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        if interaction.response.is_done():

            await interaction.followup.send(
                "❌ No tienes permisos para usar este comando.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ No tienes permisos para usar este comando.",
                ephemeral=True
            )

        return

    print(
        f"❌ Error en slash command: {error}"
    )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                "❌ Ha ocurrido un error.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ Ha ocurrido un error.",
                ephemeral=True
            )

    except Exception:

        pass


# ============================================================
# INICIALIZAR DATABASES
# ============================================================

init_prefix_db()
init_message_db()
init_afk_db()


# ============================================================
# START
# ============================================================

print("🚀 Iniciando bot...")
print("💾 Prefix database: OK")
print("📊 Message database: OK")
print("💤 AFK database: OK")
print("🌐 Slash commands: GLOBAL")
print("📅 Message stats: Hoy / Semana / Mes / Total")
print("💤 AFK: Activado")
print("▶️ Conectando a Discord...")


bot.run(TOKEN)