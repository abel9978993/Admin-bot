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


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True


# =========================================================
# BASE DE DATOS DE PREFIJOS
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
    conn.commit()


# =========================================================
# BASE DE DATOS DE AJUSTES
# =========================================================

with sqlite3.connect(MESSAGES_DB) as conn:
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
    conn.commit()


def migrate_adjustment_table():

    with sqlite3.connect(MESSAGES_DB) as conn:

        columns = conn.execute(
            "PRAGMA table_info(message_adjustments)"
        ).fetchall()

        column_names = [column[1] for column in columns]

        if "reference_real" not in column_names:
            conn.execute("""
                ALTER TABLE message_adjustments
                ADD COLUMN reference_real INTEGER NOT NULL DEFAULT 0
            """)

        if "period_start" not in column_names:
            conn.execute("""
                ALTER TABLE message_adjustments
                ADD COLUMN period_start TEXT
            """)

        conn.commit()


migrate_adjustment_table()


# =========================================================
# FECHAS
# =========================================================

def get_period_starts():

    now = datetime.now(timezone.utc)

    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    week_start = today_start - timedelta(
        days=today_start.weekday()
    )

    month_start = today_start.replace(
        day=1
    )

    year_start = today_start.replace(
        month=1,
        day=1
    )

    return (
        today_start,
        week_start,
        month_start,
        year_start
    )


# =========================================================
# CONTAR MENSAJES
# =========================================================

def count_messages(
    guild_id,
    user_id,
    start_time=None
):

    with sqlite3.connect(MESSAGES_DB) as conn:

        if start_time is None:

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

            row = conn.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE guild_id = ?
                AND user_id = ?
                AND created_at >= ?
            """, (
                guild_id,
                user_id,
                start_time.isoformat()
            )).fetchone()

    return row[0]


def count_total_messages(
    guild_id,
    user_id
):

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

    return row[0]


# =========================================================
# AJUSTES DE ESTADÍSTICAS
# =========================================================

def get_adjustment(
    guild_id,
    user_id,
    period
):

    with sqlite3.connect(MESSAGES_DB) as conn:

        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT *
            FROM message_adjustments
            WHERE guild_id = ?
            AND user_id = ?
            AND period = ?
        """, (
            guild_id,
            user_id,
            period
        )).fetchone()

    if row:
        return dict(row)

    return None


def set_adjustment(
    guild_id,
    user_id,
    period,
    amount,
    reference_real,
    period_start
):

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
            reference_real,
            period_start
        ))

        conn.commit()


def prepare_aset(
    guild_id,
    user_id,
    period,
    amount
):

    (
        today_start,
        week_start,
        month_start,
        year_start
    ) = get_period_starts()

    if period == "hoy":

        real_count = count_messages(
            guild_id,
            user_id,
            today_start
        )

        period_start = today_start.isoformat()

    elif period == "semana":

        real_count = count_messages(
            guild_id,
            user_id,
            week_start
        )

        period_start = week_start.isoformat()

    elif period == "mes":

        real_count = count_messages(
            guild_id,
            user_id,
            month_start
        )

        period_start = month_start.isoformat()

    elif period == "total":

        real_count = count_total_messages(
            guild_id,
            user_id
        )

        period_start = None

    else:

        raise ValueError("Periodo inválido")

    set_adjustment(
        guild_id,
        user_id,
        period,
        amount,
        real_count,
        period_start
    )


# =========================================================
# ESTADÍSTICAS AJUSTADAS
# =========================================================

def calculate_adjusted_value(
    guild_id,
    user_id,
    period,
    start_time
):

    real_count = count_messages(
        guild_id,
        user_id,
        start_time
    )

    adjustment = get_adjustment(
        guild_id,
        user_id,
        period
    )

    if adjustment is None:
        return real_count

    saved_period_start = adjustment["period_start"]
    current_period_start = start_time.isoformat()

    if saved_period_start != current_period_start:
        return real_count

    messages_after_adjustment = (
        real_count -
        adjustment["reference_real"]
    )

    if messages_after_adjustment < 0:
        messages_after_adjustment = 0

    result = (
        adjustment["amount"] +
        messages_after_adjustment
    )

    return max(0, result)


def calculate_adjusted_total(
    guild_id,
    user_id
):

    real_count = count_total_messages(
        guild_id,
        user_id
    )

    adjustment = get_adjustment(
        guild_id,
        user_id,
        "total"
    )

    if adjustment is None:
        return real_count

    messages_after_adjustment = (
        real_count -
        adjustment["reference_real"]
    )

    if messages_after_adjustment < 0:
        messages_after_adjustment = 0

    result = (
        adjustment["amount"] +
        messages_after_adjustment
    )

    return max(0, result)


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


# Evita limpiar los comandos antiguos más de una vez
commands_cleaned = False


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    global commands_cleaned

    print("=" * 55)
    print(f"🤖 Bot conectado como {bot.user}")
    print(f"🆔 ID: {bot.user.id}")
    print(f"🌐 Servidores: {len(bot.guilds)}")
    print("=" * 55)

    # =====================================================
    # LIMPIAR COMANDOS DE SERVIDOR ANTIGUOS
    # =====================================================

    if not commands_cleaned:

        print("🧹 Buscando comandos antiguos de servidor...")

        for guild in bot.guilds:

            try:

                old_commands = await bot.tree.fetch_commands(
                    guild=guild
                )

                if old_commands:

                    print(
                        f"🧹 Eliminando {len(old_commands)} "
                        f"comandos antiguos de {guild.name}..."
                    )

                    bot.tree.clear_commands(
                        guild=guild
                    )

                    await bot.tree.sync(
                        guild=guild
                    )

                    print(
                        f"✅ Comandos antiguos eliminados "
                        f"de {guild.name}"
                    )

                else:

                    print(
                        f"✓ No hay comandos antiguos "
                        f"en {guild.name}"
                    )

            except Exception as e:

                print(
                    f"⚠️ No se pudieron limpiar "
                    f"los comandos de {guild.name}: {e}"
                )

        commands_cleaned = True

        # Volver a sincronizar los globales
        try:

            synced = await bot.tree.sync()

            print(
                f"🌎 {len(synced)} comandos globales activos."
            )

        except Exception as e:

            print(
                f"❌ Error sincronizando globales: {e}"
            )

    print("=" * 55)
    print("🧠 Sistema de estadísticas cargado")
    print("📊 /am y ?am cargados")
    print("➕ /aset y ?aset cargados")
    print("👤 AM: todos los usuarios")
    print("👑 ASET: solo administradores")
    print("🌎 Slash commands: GLOBAL")
    print("=" * 55)


# =========================================================
# REGISTRAR MENSAJES
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is not None:

        with sqlite3.connect(MESSAGES_DB) as conn:

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

    await bot.process_commands(message)


# =========================================================
# MEMBERCOUNT
# =========================================================

@bot.command(name="membercount")
async def membercount_prefix(ctx):

    if ctx.guild is None:
        return

    await ctx.send(
        f"👥 **Miembros del servidor:** "
        f"{ctx.guild.member_count}"
    )


@bot.tree.command(
    name="membercount",
    description="Muestra el número de miembros del servidor"
)
async def membercount_slash(
    interaction: discord.Interaction
):

    if interaction.guild is None:
        return

    await interaction.response.send_message(
        f"👥 **Miembros del servidor:** "
        f"{interaction.guild.member_count}"
    )


# =========================================================
# AM - PREFIX
# =========================================================

@bot.command(name="am")
async def am_prefix(
    ctx,
    member: discord.Member = None
):

    if ctx.guild is None:
        return

    target = member or ctx.author

    (
        today_start,
        week_start,
        month_start,
        year_start
    ) = get_period_starts()

    today = calculate_adjusted_value(
        ctx.guild.id,
        target.id,
        "hoy",
        today_start
    )

    week = calculate_adjusted_value(
        ctx.guild.id,
        target.id,
        "semana",
        week_start
    )

    month = calculate_adjusted_value(
        ctx.guild.id,
        target.id,
        "mes",
        month_start
    )

    year = count_messages(
        ctx.guild.id,
        target.id,
        year_start
    )

    total = calculate_adjusted_total(
        ctx.guild.id,
        target.id
    )

    embed = discord.Embed(
        title=f"📊 Estadísticas de {target.display_name}",
        description=(
            f"**Hoy:** {today}\n"
            f"**Esta semana:** {week}\n"
            f"**Este mes:** {month}\n"
            f"**Este año:** {year}\n"
            f"**Total:** {total}"
        ),
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=target.display_avatar.url
    )

    await ctx.send(
        embed=embed
    )


# =========================================================
# AM - SLASH GLOBAL
# =========================================================

@bot.tree.command(
    name="am",
    description="Muestra las estadísticas de mensajes"
)
@app_commands.describe(
    member="Usuario cuyas estadísticas quieres ver"
)
async def am_slash(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    if interaction.guild is None:
        return

    target = member or interaction.user

    (
        today_start,
        week_start,
        month_start,
        year_start
    ) = get_period_starts()

    today = calculate_adjusted_value(
        interaction.guild.id,
        target.id,
        "hoy",
        today_start
    )

    week = calculate_adjusted_value(
        interaction.guild.id,
        target.id,
        "semana",
        week_start
    )

    month = calculate_adjusted_value(
        interaction.guild.id,
        target.id,
        "mes",
        month_start
    )

    year = count_messages(
        interaction.guild.id,
        target.id,
        year_start
    )

    total = calculate_adjusted_total(
        interaction.guild.id,
        target.id
    )

    embed = discord.Embed(
        title=f"📊 Estadísticas de {target.display_name}",
        description=(
            f"**Hoy:** {today}\n"
            f"**Esta semana:** {week}\n"
            f"**Este mes:** {month}\n"
            f"**Este año:** {year}\n"
            f"**Total:** {total}"
        ),
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=target.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# ASET - PREFIX
# =========================================================

@bot.command(name="aset")
@commands.has_permissions(administrator=True)
async def aset_prefix(
    ctx,
    period: str,
    amount: int
):

    period = period.lower()

    equivalencias = {
        "hoy": "hoy",
        "día": "hoy",
        "dia": "hoy",
        "today": "hoy",
        "semana": "semana",
        "week": "semana",
        "mes": "mes",
        "month": "mes",
        "total": "total"
    }

    if period not in equivalencias:

        await ctx.send(
            "❌ Usa: `hoy`, `semana`, `mes` o `total`."
        )

        return

    period = equivalencias[period]

    if amount < 0:

        await ctx.send(
            "❌ La cantidad no puede ser negativa."
        )

        return

    prepare_aset(
        ctx.guild.id,
        ctx.author.id,
        period,
        amount
    )

    await ctx.send(
        f"✅ **{period}** establecido en **{amount}**.\n"
        f"Los nuevos mensajes se sumarán a partir de ahora."
    )


# =========================================================
# ASET - SLASH GLOBAL
# =========================================================

@bot.tree.command(
    name="aset",
    description="Establece una cantidad inicial de mensajes"
)
@app_commands.describe(
    period="Periodo que quieres modificar",
    amount="Cantidad inicial"
)
@app_commands.choices(
    period=[
        app_commands.Choice(
            name="Hoy",
            value="hoy"
        ),
        app_commands.Choice(
            name="Esta semana",
            value="semana"
        ),
        app_commands.Choice(
            name="Este mes",
            value="mes"
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

    prepare_aset(
        interaction.guild.id,
        interaction.user.id,
        period.value,
        amount
    )

    await interaction.response.send_message(
        f"✅ **{period.name}** establecido en **{amount}**.\n"
        f"Los nuevos mensajes se sumarán a partir de ahora."
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
    reason: str = "Sin razón especificada"
):

    await member.ban(
        reason=reason
    )

    await ctx.send(
        f"🔨 {member.mention} ha sido baneado."
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
    reason: str = "Sin razón especificada"
):

    await member.ban(
        reason=reason
    )

    await interaction.response.send_message(
        f"🔨 {member.mention} ha sido baneado."
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
    reason: str = "Sin razón especificada"
):

    await member.kick(
        reason=reason
    )

    await ctx.send(
        f"👢 {member.mention} ha sido expulsado."
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
    reason: str = "Sin razón especificada"
):

    await member.kick(
        reason=reason
    )

    await interaction.response.send_message(
        f"👢 {member.mention} ha sido expulsado."
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

        await ctx.guild.unban(
            user
        )

        await ctx.send(
            f"✅ {user} ha sido desbaneado."
        )

    except discord.NotFound:

        await ctx.send(
            "❌ No encontré ese usuario entre los baneados."
        )


@bot.tree.command(
    name="unban",
    description="Desbanea un usuario mediante su ID"
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
            f"✅ {user} ha sido desbaneado."
        )

    except (discord.NotFound, ValueError):

        await interaction.response.send_message(
            "❌ No encontré ese usuario entre los baneados.",
            ephemeral=True
        )


# =========================================================
# SETNICK
# =========================================================

@bot.command(
    name="setnick",
    aliases=["nick"]
)
@commands.has_permissions(
    manage_nicknames=True
)
async def setnick_prefix(
    ctx,
    member: discord.Member = None,
    *,
    nickname: str = None
):

    # ?setnick nickname
    if member is None:

        if nickname is None:

            await ctx.send(
                "❌ Especifica el nuevo nickname."
            )

            return

        await ctx.author.edit(
            nick=nickname
        )

        await ctx.send(
            "✅ Tu nickname ha sido cambiado."
        )

        return

    if nickname is None:

        await ctx.send(
            "❌ Especifica el nuevo nickname."
        )

        return

    if member == ctx.guild.owner:

        await ctx.send(
            "❌ No puedo cambiar el nickname del dueño."
        )

        return

    if member.top_role >= ctx.guild.me.top_role:

        await ctx.send(
            "❌ No puedo cambiar el nickname de ese usuario."
        )

        return

    await member.edit(
        nick=nickname
    )

    await ctx.send(
        f"✅ Nickname de {member.mention} cambiado a "
        f"**{nickname}**."
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
            "❌ No puedo cambiar el nickname del dueño.",
            ephemeral=True
        )

        return

    if member.top_role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ No puedo cambiar el nickname de ese usuario.",
            ephemeral=True
        )

        return

    await member.edit(
        nick=nickname
    )

    await interaction.response.send_message(
        f"✅ Nickname de {member.mention} cambiado a "
        f"**{nickname}**."
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

    deleted_count = max(
        0,
        len(deleted) - 1
    )

    confirmation = await ctx.send(
        f"🧹 Se eliminaron **{deleted_count}** mensajes."
    )

    await asyncio.sleep(3)

    try:
        await confirmation.delete()
    except discord.HTTPException:
        pass


@bot.tree.command(
    name="purge",
    description="Elimina mensajes"
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
        f"🧹 Se eliminaron **{len(deleted)}** mensajes.",
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

    if not new_prefix.strip():

        await ctx.send(
            "❌ El prefijo no puede estar vacío."
        )

        return

    if len(new_prefix) > 5:

        await ctx.send(
            "❌ El prefijo puede tener máximo 5 caracteres."
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

    if not new_prefix.strip():

        await interaction.response.send_message(
            "❌ El prefijo no puede estar vacío.",
            ephemeral=True
        )

        return

    if len(new_prefix) > 5:

        await interaction.response.send_message(
            "❌ El prefijo puede tener máximo 5 caracteres.",
            ephemeral=True
        )

        return

    set_prefix(
        interaction.guild.id,
        new_prefix
    )

    await interaction.response.send_message(
        f"✅ El nuevo prefijo es `{new_prefix}`"
    )


# =========================================================
# ERRORES PREFIX
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
            "❌ Faltan argumentos en el comando."
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


# =========================================================
# ERRORES SLASH
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ No tienes permisos para usar este comando.",
                ephemeral=True
            )

        return

    print(
        f"❌ Error en slash command: {error}"
    )

    if not interaction.response.is_done():

        await interaction.response.send_message(
            "❌ Ha ocurrido un error al ejecutar el comando.",
            ephemeral=True
        )


# =========================================================
# INICIAR BOT
# =========================================================

if not TOKEN:

    raise RuntimeError(
        "❌ No se encontró MEMBERCOUNT_TOKEN."
    )


bot.run(TOKEN)