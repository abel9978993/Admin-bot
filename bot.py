import os
import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands
from discord import app_commands


# =========================================================
# CONFIGURACIÓN
# =========================================================

TOKEN = os.getenv("MEMBERCOUNT_TOKEN")

if not TOKEN:
    raise RuntimeError("❌ Falta la variable MEMBERCOUNT_TOKEN")


intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True


# =========================================================
# BASE DE DATOS
# =========================================================

PREFIX_DB = "prefixes.db"
MESSAGE_DB = "messages.db"


# =========================================================
# BASE DE DATOS DE PREFIJOS
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

    if row:
        return row[0]

    return "?"


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
# BASE DE DATOS DE MENSAJES
# =========================================================

def init_message_db():
    with sqlite3.connect(MESSAGE_DB) as conn:

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


# =========================================================
# ACTIVAR / DESACTIVAR MENSAJES
# =========================================================

def is_message_tracking_enabled(guild_id):

    with sqlite3.connect(MESSAGE_DB) as conn:
        row = conn.execute(
            """
            SELECT enabled
            FROM message_settings
            WHERE guild_id = ?
            """,
            (guild_id,)
        ).fetchone()

    if row is None:
        return True

    return bool(row[0])


def set_message_tracking(guild_id, enabled):

    with sqlite3.connect(MESSAGE_DB) as conn:

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


# =========================================================
# FUNCIONES DE ESTADÍSTICAS
# =========================================================

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

    if period == "year":
        return now.replace(
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

    return None


def get_real_message_count(guild_id, user_id, period):

    now = datetime.now(timezone.utc)

    with sqlite3.connect(MESSAGE_DB) as conn:

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

    return row[0] if row else 0


def get_adjusted_count(guild_id, user_id, period):

    real_count = get_real_message_count(
        guild_id,
        user_id,
        period
    )

    with sqlite3.connect(MESSAGE_DB) as conn:

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
        return real_count

    amount, reference_real, saved_period_start = row

    if period != "total":

        current_period_start = get_period_start(period)

        if saved_period_start != current_period_start.isoformat():
            return real_count

    result = amount + (real_count - reference_real)

    return max(0, result)


def set_adjustment(guild_id, user_id, period, amount):

    real_count = get_real_message_count(
        guild_id,
        user_id,
        period
    )

    if period == "total":
        period_start = None
    else:
        period_start = get_period_start(
            period
        ).isoformat()

    with sqlite3.connect(MESSAGE_DB) as conn:

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
            real_count,
            period_start
        ))

        conn.commit()


# =========================================================
# BOT
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
    intents=intents
)


commands_cleaned = False


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    global commands_cleaned

    print("=" * 50)
    print(f"🤖 Bot conectado: {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"🌐 Servidores: {len(bot.guilds)}")
    print("✅ Abel MemberCount está listo.")
    print("=" * 50)

    if not commands_cleaned:

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
                        f"🧹 Comandos antiguos eliminados de {guild.name}"
                    )

            except Exception as e:

                print(
                    f"⚠️ No se pudieron limpiar "
                    f"los comandos de {guild.name}: {e}"
                )

        commands_cleaned = True

        try:

            synced = await bot.tree.sync()

            print(
                f"✅ {len(synced)} comandos globales activos."
            )

        except Exception as e:

            print(
                f"❌ Error sincronizando globales: {e}"
            )


# =========================================================
# CONTADOR DE MENSAJES
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is not None:

        if is_message_tracking_enabled(
            message.guild.id
        ):

            try:

                with sqlite3.connect(MESSAGE_DB) as conn:

                    conn.execute("""
                        INSERT INTO messages
                        (
                            guild_id,
                            user_id,
                            channel_id,
                            created_at
                        )
                        VALUES (?, ?, ?, ?)
                    """, (
                        message.guild.id,
                        message.author.id,
                        message.channel.id,
                        datetime.now(
                            timezone.utc
                        ).isoformat()
                    ))

                    conn.commit()

            except Exception as e:

                print(
                    f"❌ Error guardando mensaje: {e}"
                )

    await bot.process_commands(message)


# =========================================================
# MEMBERCOUNT
# =========================================================

@bot.command(name="membercount")
async def membercount_prefix(ctx):

    count = ctx.guild.member_count

    embed = discord.Embed(
        title="👥 Member Count",
        description=(
            f"Este servidor tiene **{count:,} miembros**."
        ),
        color=discord.Color.blurple()
    )

    await ctx.send(embed=embed)


@bot.tree.command(
    name="membercount",
    description="Muestra el número de miembros del servidor"
)
async def membercount_slash(
    interaction: discord.Interaction
):

    count = interaction.guild.member_count

    embed = discord.Embed(
        title="👥 Member Count",
        description=(
            f"Este servidor tiene **{count:,} miembros**."
        ),
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# AENABLE
# =========================================================

@bot.command(name="aenable")
@commands.has_permissions(administrator=True)
async def aenable_prefix(ctx):

    set_message_tracking(
        ctx.guild.id,
        True
    )

    embed = discord.Embed(
        title="✅ Message Tracking Activado",
        description=(
            "El contador de mensajes ha sido activado "
            "en este servidor.\n\n"
            "Los nuevos mensajes volverán a contabilizarse."
        ),
        color=discord.Color.green()
    )

    await ctx.send(embed=embed)


@bot.tree.command(
    name="aenable",
    description="Activa el contador de mensajes"
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

    embed = discord.Embed(
        title="✅ Message Tracking Activado",
        description=(
            "El contador de mensajes ha sido activado "
            "en este servidor.\n\n"
            "Los nuevos mensajes volverán a contabilizarse."
        ),
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# ADESABLE
# =========================================================

@bot.command(name="adesable")
@commands.has_permissions(administrator=True)
async def adesable_prefix(ctx):

    set_message_tracking(
        ctx.guild.id,
        False
    )

    embed = discord.Embed(
        title="🛑 Message Tracking Desactivado",
        description=(
            "El contador de mensajes ha sido desactivado "
            "en este servidor.\n\n"
            "Los nuevos mensajes ya no se contabilizarán."
        ),
        color=discord.Color.red()
    )

    await ctx.send(embed=embed)


@bot.tree.command(
    name="adesable",
    description="Desactiva el contador de mensajes"
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

    embed = discord.Embed(
        title="🛑 Message Tracking Desactivado",
        description=(
            "El contador de mensajes ha sido desactivado "
            "en este servidor.\n\n"
            "Los nuevos mensajes ya no se contabilizarán."
        ),
        color=discord.Color.red()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# AM
# =========================================================

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

    year = get_adjusted_count(
        guild.id,
        member.id,
        "year"
    )

    total = get_adjusted_count(
        guild.id,
        member.id,
        "total"
    )

    enabled = is_message_tracking_enabled(
        guild.id
    )

    status = (
        "🟢 Activo"
        if enabled
        else "🔴 Desactivado"
    )

    embed = discord.Embed(
        title=f"📊 Actividad de {member.display_name}",
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
        name="📚 Este año",
        value=f"**{year:,}**",
        inline=True
    )

    embed.add_field(
        name="📈 Total",
        value=f"**{total:,}**",
        inline=True
    )

    embed.add_field(
        name="⚙️ Contador",
        value=status,
        inline=True
    )

    return embed


@bot.command(name="am")
async def am_prefix(
    ctx,
    member: discord.Member = None
):

    if not is_message_tracking_enabled(
        ctx.guild.id
    ):

        await ctx.send(
            "🛑 El contador de mensajes está desactivado "
            "en este servidor."
        )

        return

    if member is None:
        member = ctx.author

    embed = create_am_embed(
        ctx.guild,
        member
    )

    await ctx.send(embed=embed)


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
            "🛑 El contador de mensajes está desactivado "
            "en este servidor.",
            ephemeral=True
        )

        return

    if member is None:
        member = interaction.user

    embed = create_am_embed(
        interaction.guild,
        member
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# ASET
# =========================================================

PERIOD_TRANSLATIONS = {
    "hoy": "today",
    "dia": "today",
    "día": "today",
    "today": "today",

    "semana": "week",
    "week": "week",

    "mes": "month",
    "month": "month",

    "total": "total"
}


@bot.command(name="aset")
@commands.has_permissions(administrator=True)
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
            "❌ Periodo inválido.\n\n"
            "Usa:\n"
            "`hoy`\n"
            "`semana`\n"
            "`mes`\n"
            "`total`"
        )

        return

    if amount < 0:

        await ctx.send(
            "❌ La cantidad no puede ser negativa."
        )

        return

    set_adjustment(
        ctx.guild.id,
        ctx.author.id,
        period_key,
        amount
    )

    await ctx.send(
        f"✅ Tu contador de **{period}** ahora empieza "
        f"en **{amount:,}** mensajes."
    )


@bot.tree.command(
    name="aset",
    description="Establece tu contador de mensajes"
)
@app_commands.describe(
    period="Periodo que quieres modificar",
    amount="Cantidad inicial"
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

    set_adjustment(
        interaction.guild.id,
        interaction.user.id,
        period.value,
        amount
    )

    await interaction.response.send_message(
        f"✅ Tu contador de **{period.name}** ahora empieza "
        f"en **{amount:,}** mensajes.",
        ephemeral=True
    )


# =========================================================
# BAN
# =========================================================

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_prefix(
    ctx,
    member: discord.Member,
    *,
    reason: str = "Sin razón"
):

    if member == ctx.guild.owner:

        await ctx.send(
            "❌ No puedes expulsar al dueño del servidor."
        )

        return

    await member.ban(reason=reason)

    await ctx.send(
        f"🔨 **{member}** ha sido baneado.\n"
        f"Razón: {reason}"
    )


@bot.tree.command(
    name="ban",
    description="Banea a un usuario"
)
@app_commands.describe(
    member="Usuario que quieres banear",
    reason="Razón del baneo"
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def ban_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "Sin razón"
):

    if member == interaction.guild.owner:

        await interaction.response.send_message(
            "❌ No puedes expulsar al dueño del servidor.",
            ephemeral=True
        )

        return

    await member.ban(reason=reason)

    await interaction.response.send_message(
        f"🔨 **{member}** ha sido baneado.\n"
        f"Razón: {reason}"
    )


# =========================================================
# KICK
# =========================================================

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_prefix(
    ctx,
    member: discord.Member,
    *,
    reason: str = "Sin razón"
):

    if member == ctx.guild.owner:

        await ctx.send(
            "❌ No puedes expulsar al dueño del servidor."
        )

        return

    await member.kick(reason=reason)

    await ctx.send(
        f"👢 **{member}** ha sido expulsado.\n"
        f"Razón: {reason}"
    )


@bot.tree.command(
    name="kick",
    description="Expulsa a un usuario"
)
@app_commands.describe(
    member="Usuario que quieres expulsar",
    reason="Razón de la expulsión"
)
@app_commands.checks.has_permissions(
    kick_members=True
)
async def kick_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "Sin razón"
):

    if member == interaction.guild.owner:

        await interaction.response.send_message(
            "❌ No puedes expulsar al dueño del servidor.",
            ephemeral=True
        )

        return

    await member.kick(reason=reason)

    await interaction.response.send_message(
        f"👢 **{member}** ha sido expulsado.\n"
        f"Razón: {reason}"
    )


# =========================================================
# UNBAN
# =========================================================

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_prefix(
    ctx,
    user_id: int
):

    try:

        user = await bot.fetch_user(
            user_id
        )

        await ctx.guild.unban(user)

        await ctx.send(
            f"✅ **{user}** ha sido desbaneado."
        )

    except Exception as e:

        await ctx.send(
            f"❌ No se pudo desbanear al usuario: {e}"
        )


@bot.tree.command(
    name="unban",
    description="Desbanea a un usuario"
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

        await interaction.guild.unban(
            user
        )

        await interaction.response.send_message(
            f"✅ **{user}** ha sido desbaneado."
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ No se pudo desbanear al usuario: {e}",
            ephemeral=True
        )


# =========================================================
# SETNICK / NICK
# =========================================================

async def execute_setnick(
    ctx,
    target,
    nickname
):

    if target == ctx.guild.owner:

        await ctx.send(
            "❌ No puedes cambiar el nickname del dueño."
        )

        return

    me = ctx.guild.me

    if me is None:

        await ctx.send(
            "❌ No puedo encontrar mi usuario en el servidor."
        )

        return

    if target.top_role >= me.top_role:

        await ctx.send(
            "❌ No puedo cambiar el nickname de ese usuario "
            "porque su rol más alto está al mismo nivel "
            "o por encima del mío."
        )

        return

    try:

        await target.edit(
            nick=nickname
        )

        await ctx.send(
            f"✅ Nickname cambiado correctamente a "
            f"**{target}**."
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ No tengo permiso para cambiar ese nickname."
        )

    except Exception as e:

        await ctx.send(
            f"❌ Error: {e}"
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
            f"❌ Uso:\n"
            f"`{get_prefix(ctx.guild.id)}setnick @usuario nickname`\n"
            f"`{get_prefix(ctx.guild.id)}setnick nickname`"
        )

        return

    target = None
    nickname = None

    try:

        target = await commands.MemberConverter().convert(
            ctx,
            args[0]
        )

        nickname = " ".join(
            args[1:]
        ).strip()

        if not nickname:

            await ctx.send(
                "❌ Escribe el nuevo nickname."
            )

            return

    except commands.BadArgument:

        target = ctx.author

        nickname = " ".join(
            args
        ).strip()

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

    if member == interaction.guild.owner:

        await interaction.response.send_message(
            "❌ No puedes cambiar el nickname del dueño.",
            ephemeral=True
        )

        return

    me = interaction.guild.me

    if me is None:

        await interaction.response.send_message(
            "❌ No puedo encontrar mi usuario.",
            ephemeral=True
        )

        return

    if member.top_role >= me.top_role:

        await interaction.response.send_message(
            "❌ No puedo cambiar el nickname de ese usuario "
            "porque su rol está al mismo nivel o por encima del mío.",
            ephemeral=True
        )

        return

    try:

        await member.edit(
            nick=nickname
        )

        await interaction.response.send_message(
            f"✅ Nickname cambiado correctamente a "
            f"**{member}**."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ No tengo permiso para cambiar ese nickname.",
            ephemeral=True
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
            "❌ La cantidad debe estar entre 1 y 100."
        )

        return

    deleted = await ctx.channel.purge(
        limit=amount + 1
    )

    msg = await ctx.send(
        f"🧹 Se eliminaron **{len(deleted) - 1} mensajes**."
    )

    await asyncio.sleep(3)

    try:
        await msg.delete()
    except:
        pass


@bot.tree.command(
    name="purge",
    description="Elimina mensajes del canal"
)
@app_commands.describe(
    amount="Cantidad de mensajes a eliminar"
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
            "❌ La cantidad debe estar entre 1 y 100.",
            ephemeral=True
        )

        return

    await interaction.response.defer(
        ephemeral=True
    )

    deleted = await interaction.channel.purge(
        limit=amount
    )

    await interaction.followup.send(
        f"🧹 Se eliminaron **{len(deleted)} mensajes**.",
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
            "❌ El prefijo no puede tener más de 5 caracteres."
        )

        return

    set_prefix(
        ctx.guild.id,
        new_prefix
    )

    await ctx.send(
        f"✅ El nuevo prefijo es `{new_prefix}`"
    )


@bot.tree.command(
    name="prefix",
    description="Cambia el prefijo del bot"
)
@app_commands.describe(
    new_prefix="Nuevo prefijo"
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
            "❌ El prefijo no puede tener más de 5 caracteres.",
            ephemeral=True
        )

        return

    set_prefix(
        interaction.guild.id,
        new_prefix
    )

    await interaction.response.send_message(
        f"✅ El nuevo prefijo es `{new_prefix}`",
        ephemeral=True
    )


# =========================================================
# ROLES
# =========================================================

def get_manageable_roles(
    guild,
    member,
    promote=True
):

    bot_member = guild.me

    if bot_member is None:
        return []

    bot_top_role = bot_member.top_role

    roles = []

    for role in guild.roles:

        if role.is_default():
            continue

        if role.managed:
            continue

        if role >= bot_top_role:
            continue

        if promote:

            if role > member.top_role:
                roles.append(role)

        else:

            if role < member.top_role:
                roles.append(role)

    roles.sort(
        key=lambda r: r.position,
        reverse=True
    )

    return roles


# =========================================================
# SELECT DE ROLES
# =========================================================

class RoleSelect(discord.ui.Select):

    def __init__(
        self,
        target_member,
        roles,
        promote
    ):

        self.target_member = target_member
        self.promote = promote

        options = []

        for role in roles[:25]:

            options.append(
                discord.SelectOption(
                    label=role.name[:100],
                    value=str(role.id),
                    description=f"Nivel {role.position}"[:100]
                )
            )

        super().__init__(
            placeholder="Selecciona el nuevo rol",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild

        if guild is None:

            await interaction.response.send_message(
                "❌ Este menú solo funciona en un servidor.",
                ephemeral=True
            )

            return

        member = guild.get_member(
            self.target_member.id
        )

        if member is None:

            await interaction.response.send_message(
                "❌ No se encontró al usuario.",
                ephemeral=True
            )

            return

        role = guild.get_role(
            int(self.values[0])
        )

        if role is None:

            await interaction.response.send_message(
                "❌ Ese rol ya no existe.",
                ephemeral=True
            )

            return

        me = guild.me

        if me is None:

            await interaction.response.send_message(
                "❌ No se encontró al bot.",
                ephemeral=True
            )

            return

        if role.managed or role.is_default():

            await interaction.response.send_message(
                "❌ Ese rol no se puede administrar.",
                ephemeral=True
            )

            return

        if role >= me.top_role:

            await interaction.response.send_message(
                "❌ No puedo administrar ese rol porque "
                "está al mismo nivel o por encima de mi rol.",
                ephemeral=True
            )

            return

        if member == guild.owner:

            await interaction.response.send_message(
                "❌ No puedes modificar al dueño del servidor.",
                ephemeral=True
            )

            return

        if member.top_role >= me.top_role:

            await interaction.response.send_message(
                "❌ No puedo modificar a este usuario "
                "porque su rol está al mismo nivel o por encima del mío.",
                ephemeral=True
            )

            return

        old_role = member.top_role

        try:

            if old_role != guild.default_role:

                await member.remove_roles(
                    old_role,
                    reason="Cambio de rol mediante promote/demote"
                )

            await member.add_roles(
                role,
                reason="Cambio de rol mediante promote/demote"
            )

            action = (
                "ascendido"
                if self.promote
                else "descendido"
            )

            embed = discord.Embed(
                title="✅ Rol cambiado",
                description=(
                    f"{member.mention} ha sido **{action}**.\n\n"
                    f"**Rol anterior:** {old_role.mention}\n"
                    f"**Rol nuevo:** {role.mention}"
                ),
                color=discord.Color.green()
            )

            await interaction.response.edit_message(
                embed=embed,
                view=None
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ Discord no me permite cambiar ese rol.",
                ephemeral=True
            )

        except Exception as e:

            await interaction.response.send_message(
                f"❌ Error: {e}",
                ephemeral=True
            )


class RoleView(discord.ui.View):

    def __init__(
        self,
        target_member,
        roles,
        promote
    ):

        super().__init__(
            timeout=60
        )

        self.add_item(
            RoleSelect(
                target_member,
                roles,
                promote
            )
        )

    async def on_timeout(self):

        for item in self.children:
            item.disabled = True


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

    if member == ctx.author:

        await ctx.send(
            "❌ No puedes usar promote sobre ti mismo."
        )

        return

    roles = get_manageable_roles(
        ctx.guild,
        member,
        promote=True
    )

    if not roles:

        await ctx.send(
            "❌ No hay roles disponibles para ascender a este usuario."
        )

        return

    embed = discord.Embed(
        title="⬆️ Promote",
        description=(
            f"Selecciona el nuevo rol para {member.mention}."
        ),
        color=discord.Color.green()
    )

    view = RoleView(
        member,
        roles,
        True
    )

    await ctx.send(
        embed=embed,
        view=view
    )


@bot.tree.command(
    name="promote",
    description="Asciende a un usuario a otro rol"
)
@app_commands.describe(
    member="Usuario que quieres ascender"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def promote_slash(
    interaction: discord.Interaction,
    member: discord.Member
):

    if member == interaction.user:

        await interaction.response.send_message(
            "❌ No puedes usar promote sobre ti mismo.",
            ephemeral=True
        )

        return

    roles = get_manageable_roles(
        interaction.guild,
        member,
        promote=True
    )

    if not roles:

        await interaction.response.send_message(
            "❌ No hay roles disponibles para ascender a este usuario.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="⬆️ Promote",
        description=(
            f"Selecciona el nuevo rol para {member.mention}."
        ),
        color=discord.Color.green()
    )

    view = RoleView(
        member,
        roles,
        True
    )

    await interaction.response.send_message(
        embed=embed,
        view=view
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

    if member == ctx.author:

        await ctx.send(
            "❌ No puedes usar demote sobre ti mismo."
        )

        return

    roles = get_manageable_roles(
        ctx.guild,
        member,
        promote=False
    )

    if not roles:

        await ctx.send(
            "❌ No hay roles disponibles para descender a este usuario."
        )

        return

    embed = discord.Embed(
        title="⬇️ Demote",
        description=(
            f"Selecciona el nuevo rol para {member.mention}."
        ),
        color=discord.Color.orange()
    )

    view = RoleView(
        member,
        roles,
        False
    )

    await ctx.send(
        embed=embed,
        view=view
    )


@bot.tree.command(
    name="demote",
    description="Desciende a un usuario a otro rol"
)
@app_commands.describe(
    member="Usuario que quieres descender"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def demote_slash(
    interaction: discord.Interaction,
    member: discord.Member
):

    if member == interaction.user:

        await interaction.response.send_message(
            "❌ No puedes usar demote sobre ti mismo.",
            ephemeral=True
        )

        return

    roles = get_manageable_roles(
        interaction.guild,
        member,
        promote=False
    )

    if not roles:

        await interaction.response.send_message(
            "❌ No hay roles disponibles para descender a este usuario.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="⬇️ Demote",
        description=(
            f"Selecciona el nuevo rol para {member.mention}."
        ),
        color=discord.Color.orange()
    )

    view = RoleView(
        member,
        roles,
        False
    )

    await interaction.response.send_message(
        embed=embed,
        view=view
    )


# =========================================================
# ROLE GROUP
# =========================================================

role_group = app_commands.Group(
    name="role",
    description="Gestiona los roles de los usuarios"
)


@role_group.command(
    name="add",
    description="Añade un rol a un usuario"
)
@app_commands.describe(
    member="Usuario",
    role="Rol que quieres añadir"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def role_add_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    me = interaction.guild.me

    if role.is_default() or role.managed:

        await interaction.response.send_message(
            "❌ Ese rol no se puede administrar.",
            ephemeral=True
        )

        return

    if role >= me.top_role:

        await interaction.response.send_message(
            "❌ Ese rol está al mismo nivel o por encima del mío.",
            ephemeral=True
        )

        return

    if member == interaction.guild.owner:

        await interaction.response.send_message(
            "❌ No puedes modificar al dueño.",
            ephemeral=True
        )

        return

    if member.top_role >= me.top_role:

        await interaction.response.send_message(
            "❌ El usuario tiene un rol demasiado alto.",
            ephemeral=True
        )

        return

    try:

        await member.add_roles(
            role,
            reason="Role add"
        )

        await interaction.response.send_message(
            f"✅ Se añadió {role.mention} a {member.mention}."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ No puedo añadir ese rol.",
            ephemeral=True
        )


@role_group.command(
    name="remove",
    description="Quita un rol a un usuario"
)
@app_commands.describe(
    member="Usuario",
    role="Rol que quieres quitar"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def role_remove_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):

    me = interaction.guild.me

    if role.is_default() or role.managed:

        await interaction.response.send_message(
            "❌ Ese rol no se puede administrar.",
            ephemeral=True
        )

        return

    if role >= me.top_role:

        await interaction.response.send_message(
            "❌ Ese rol está al mismo nivel o por encima del mío.",
            ephemeral=True
        )

        return

    if member == interaction.guild.owner:

        await interaction.response.send_message(
            "❌ No puedes modificar al dueño.",
            ephemeral=True
        )

        return

    try:

        await member.remove_roles(
            role,
            reason="Role remove"
        )

        await interaction.response.send_message(
            f"✅ Se quitó {role.mention} de {member.mention}."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ No puedo quitar ese rol.",
            ephemeral=True
        )


bot.tree.add_command(
    role_group
)


# =========================================================
# PREFIX ROLE
# =========================================================

@bot.group(
    name="role",
    invoke_without_command=True
)
@commands.has_permissions(
    manage_roles=True
)
async def role_prefix(ctx):

    prefix = get_prefix(
        ctx.guild.id
    )

    await ctx.send(
        "❌ Usa uno de estos comandos:\n\n"
        f"`{prefix}role add @usuario @rol`\n"
        f"`{prefix}role remove @usuario @rol`"
    )


@role_prefix.command(
    name="add"
)
@commands.has_permissions(
    manage_roles=True
)
async def role_add_prefix(
    ctx,
    member: discord.Member,
    role: discord.Role
):

    me = ctx.guild.me

    if role.is_default() or role.managed:

        await ctx.send(
            "❌ Ese rol no se puede administrar."
        )

        return

    if role >= me.top_role:

        await ctx.send(
            "❌ Ese rol está al mismo nivel o por encima del mío."
        )

        return

    if member == ctx.guild.owner:

        await ctx.send(
            "❌ No puedes modificar al dueño."
        )

        return

    if member.top_role >= me.top_role:

        await ctx.send(
            "❌ El usuario tiene un rol demasiado alto."
        )

        return

    try:

        await member.add_roles(
            role,
            reason="Role add"
        )

        await ctx.send(
            f"✅ Se añadió {role.mention} a {member.mention}."
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ No puedo añadir ese rol."
        )


@role_prefix.command(
    name="remove"
)
@commands.has_permissions(
    manage_roles=True
)
async def role_remove_prefix(
    ctx,
    member: discord.Member,
    role: discord.Role
):

    me = ctx.guild.me

    if role.is_default() or role.managed:

        await ctx.send(
            "❌ Ese rol no se puede administrar."
        )

        return

    if role >= me.top_role:

        await ctx.send(
            "❌ Ese rol está al mismo nivel o por encima del mío."
        )

        return

    if member == ctx.guild.owner:

        await ctx.send(
            "❌ No puedes modificar al dueño."
        )

        return

    try:

        await member.remove_roles(
            role,
            reason="Role remove"
        )

        await ctx.send(
            f"✅ Se quitó {role.mention} de {member.mention}."
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ No puedo quitar ese rol."
        )


# =========================================================
# ERRORES
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
            "❌ Uno de los argumentos no es válido."
        )

        return

    print(
        f"❌ Error en comando: {error}"
    )


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
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
                "❌ Ocurrió un error ejecutando el comando.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ Ocurrió un error ejecutando el comando.",
                ephemeral=True
            )

    except:
        pass


# =========================================================
# INICIAR BASES DE DATOS
# =========================================================

init_prefix_db()
init_message_db()


# =========================================================
# INICIAR BOT
# =========================================================

print("🚀 Iniciando bot...")

bot.run(TOKEN)