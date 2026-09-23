import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime, timezone, timedelta
import os


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("MEMBERCOUNT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "❌ MEMBERCOUNT_TOKEN no está configurado."
    )


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True


# ============================================================
# DATABASES
# ============================================================

PREFIX_DB = "prefixes.db"
MESSAGES_DB = "messages.db"
AFK_DB = "afk.db"


# ============================================================
# PREFIX DATABASE
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
            INSERT INTO prefixes (
                guild_id,
                prefix
            )
            VALUES (?, ?)

            ON CONFLICT(guild_id)
            DO UPDATE SET prefix = excluded.prefix
        """, (
            guild_id,
            prefix
        ))

        conn.commit()


def get_bot_prefix(bot, message):

    if message.guild is None:
        return "?"

    return get_prefix(message.guild.id)


# ============================================================
# LANGUAGE SYSTEM
# ============================================================

def get_locale_value(locale):

    if locale is None:
        return "en"

    value = str(locale).lower()

    if value.startswith("es"):
        return "es"

    if value.startswith("en"):
        return "en"

    if value.startswith("fr"):
        return "fr"

    if value.startswith("de"):
        return "de"

    if value.startswith("it"):
        return "it"

    if value.startswith("pt"):
        return "pt"

    if value.startswith("nl"):
        return "nl"

    if value.startswith("pl"):
        return "pl"

    return "en"


def get_user_language(user):

    locale = getattr(user, "locale", None)

    return get_locale_value(locale)


# ============================================================
# TRANSLATIONS
# ============================================================

TRANSLATIONS = {

    "en": {

        "no_reason": "❌ You must provide a reason.",
        "afk_set": "💤 **AFK set**",
        "reason": "Reason",
        "user_afk": "💤 User is AFK",
        "is_afk": "**{name}** is currently AFK.",
        "leave_message": "Leave a message",
        "message_saved": (
            "✅ Your message will be sent to them "
            "when they come back."
        ),
        "not_afk": "❌ This user is no longer AFK.",
        "back": "👋 {user} is no longer AFK.",
        "messages_while_afk": "💬 Messages while you were AFK",
        "messages_description": (
            "Here are the messages people left "
            "for you while you were AFK."
        ),
        "from_user": "💬 From {name}",
        "member_count": (
            "👥 **{server}** has **{count:,}** members."
        ),
        "no_permission": (
            "❌ You don't have permission to use this command."
        ),
        "missing_args": "❌ You're missing required arguments.",
        "invalid_argument": "❌ The argument is invalid.",
        "not_server": "❌ This command can only be used in a server.",
        "nickname_changed": (
            "✅ Nickname of **{user}** changed to **{nickname}**."
        ),
        "nickname_required": (
            "❌ You must provide a new nickname."
        ),
        "nickname_too_long": (
            "❌ The nickname cannot be longer than 32 characters."
        ),
        "cannot_owner_nick": (
            "❌ You cannot change the server owner's nickname."
        ),
        "role_hierarchy_nick": (
            "❌ I cannot change that user's nickname because "
            "their role is higher than or equal to mine."
        ),
        "no_nick_permission": (
            "❌ You don't have permission to change other users' nicknames."
        ),
        "cannot_nick": (
            "❌ I don't have permission to change that nickname."
        ),
        "purge_range": (
            "❌ The number must be between 1 and 100."
        ),
        "purged": (
            "🧹 **{count}** messages were deleted."
        ),
        "prefix_too_long": (
            "❌ The prefix cannot be longer than 5 characters."
        ),
        "prefix_changed": (
            "✅ Prefix changed to `{prefix}`."
        ),
        "stats_disabled": "🛑 Message counting is disabled",
        "stats_disabled_desc": (
            "Message counting is not enabled in this server.\n\n"
            "Message statistics are unavailable while this option "
            "is disabled.\n\n"
            "An administrator can enable it with:\n"
            "`{prefix}aenable`\n"
            "or `/aenable`"
        ),
        "today": "📅 Today",
        "week": "📆 This week",
        "month": "🗓️ This month",
        "total": "📈 Total",
        "stats_title": "📊 Message Stats — {name}",
        "invalid_period": (
            "❌ Invalid period.\n"
            "Use: `today`, `week`, `month` or `total`."
        ),
        "negative_amount": (
            "❌ The amount cannot be negative."
        ),
        "stats_set": (
            "✅ Your {period} messages have been set to **{amount:,}**."
        ),
        "count_enabled": (
            "✅ **Message counting enabled.**\n"
            "New messages will be counted again."
        ),
        "count_disabled": (
            "🛑 **Message counting disabled.**\n"
            "New messages will no longer be counted."
        ),
        "no_roles": "❌ There are no available roles.",
        "select_promote": (
            "⬆️ Select the new role for {user}."
        ),
        "select_demote": (
            "⬇️ Select the new role for {user}."
        ),
        "promote_placeholder": "Select a role to promote",
        "demote_placeholder": "Select a role to demote",
        "menu_not_you": "❌ This menu isn't for you.",
        "role_updated": (
            "✅ {user} now has the {role} role."
        ),
        "cannot_modify_owner": (
            "❌ You cannot modify the server owner."
        ),
        "cannot_self_role": (
            "❌ You cannot use this command on yourself."
        ),
        "role_no_permission": (
            "❌ I don't have permission to manage that role."
        ),
        "role_added": (
            "✅ {role} was added to {user}."
        ),
        "role_removed": (
            "✅ {role} was removed from {user}."
        ),
        "cannot_manage_role": (
            "❌ You cannot manage that role."
        ),
        "role_above_bot": (
            "❌ That role is higher than my role."
        ),
        "old_commands_cleaned": "🧹 Old commands removed",
        "sync_error": "❌ Error syncing commands: {error}",
        "generic_error": "❌ An error occurred."
    },

    "es": {

        "no_reason": "❌ Tienes que poner un motivo.",
        "afk_set": "💤 **AFK activado**",
        "reason": "Motivo",
        "user_afk": "💤 Usuario AFK",
        "is_afk": "**{name}** está actualmente AFK.",
        "leave_message": "Dejar un mensaje",
        "message_saved": (
            "✅ Tu mensaje será enviado cuando vuelva."
        ),
        "not_afk": "❌ Esta persona ya no está AFK.",
        "back": "👋 {user} ya no está AFK.",
        "messages_while_afk": "💬 Mensajes mientras estabas AFK",
        "messages_description": (
            "Estos son los mensajes que te dejaron "
            "mientras estabas AFK."
        ),
        "from_user": "💬 De {name}",
        "member_count": (
            "👥 **{server}** tiene **{count:,}** miembros."
        ),
        "no_permission": (
            "❌ No tienes permisos para usar este comando."
        ),
        "missing_args": "❌ Faltan argumentos.",
        "invalid_argument": "❌ El argumento no es válido.",
        "not_server": "❌ Este comando solo funciona en servidores.",
        "nickname_changed": (
            "✅ El nickname de **{user}** cambió a **{nickname}**."
        ),
        "nickname_required": (
            "❌ Tienes que poner el nuevo nickname."
        ),
        "nickname_too_long": (
            "❌ El nickname no puede tener más de 32 caracteres."
        ),
        "cannot_owner_nick": (
            "❌ No puedes cambiar el nickname del dueño del servidor."
        ),
        "role_hierarchy_nick": (
            "❌ No puedo cambiar el nickname porque su rol "
            "está por encima o al mismo nivel que el mío."
        ),
        "no_nick_permission": (
            "❌ No tienes permiso para cambiar nicknames de otros usuarios."
        ),
        "cannot_nick": (
            "❌ No tengo permisos para cambiar ese nickname."
        ),
        "purge_range": (
            "❌ El número debe estar entre 1 y 100."
        ),
        "purged": (
            "🧹 Se eliminaron **{count}** mensajes."
        ),
        "prefix_too_long": (
            "❌ El prefix no puede tener más de 5 caracteres."
        ),
        "prefix_changed": (
            "✅ Prefix cambiado a `{prefix}`."
        ),
        "stats_disabled": "🛑 Conteo de mensajes desactivado",
        "stats_disabled_desc": (
            "El conteo de mensajes no está activado en este servidor.\n\n"
            "Las estadísticas no están disponibles mientras esté desactivado.\n\n"
            "Un administrador puede activarlo con:\n"
            "`{prefix}aenable`\n"
            "o `/aenable`"
        ),
        "today": "📅 Hoy",
        "week": "📆 Esta semana",
        "month": "🗓️ Este mes",
        "total": "📈 Total",
        "stats_title": "📊 Estadísticas — {name}",
        "invalid_period": (
            "❌ Periodo inválido.\n"
            "Usa: `hoy`, `semana`, `mes` o `total`."
        ),
        "negative_amount": (
            "❌ La cantidad no puede ser negativa."
        ),
        "stats_set": (
            "✅ Tus mensajes de {period} se han establecido en **{amount:,}**."
        ),
        "count_enabled": (
            "✅ **Conteo de mensajes activado.**\n"
            "Los nuevos mensajes volverán a contarse."
        ),
        "count_disabled": (
            "🛑 **Conteo de mensajes desactivado.**\n"
            "Los nuevos mensajes ya no serán contados."
        ),
        "no_roles": "❌ No hay roles disponibles.",
        "select_promote": (
            "⬆️ Selecciona el nuevo rol para {user}."
        ),
        "select_demote": (
            "⬇️ Selecciona el nuevo rol para {user}."
        ),
        "promote_placeholder": "Selecciona un rol para ascender",
        "demote_placeholder": "Selecciona un rol para descender",
        "menu_not_you": "❌ Este menú no es para ti.",
        "role_updated": (
            "✅ {user} ahora tiene el rol {role}."
        ),
        "cannot_modify_owner": (
            "❌ No puedes modificar al dueño del servidor."
        ),
        "cannot_self_role": (
            "❌ No puedes usar este comando contigo mismo."
        ),
        "role_no_permission": (
            "❌ No tengo permisos para gestionar ese rol."
        ),
        "role_added": (
            "✅ Se añadió {role} a {user}."
        ),
        "role_removed": (
            "✅ Se quitó {role} de {user}."
        ),
        "cannot_manage_role": (
            "❌ No puedes gestionar ese rol."
        ),
        "role_above_bot": (
            "❌ Ese rol está por encima de mi rol."
        ),
        "old_commands_cleaned": "🧹 Comandos antiguos eliminados",
        "sync_error": "❌ Error sincronizando comandos: {error}",
        "generic_error": "❌ Ha ocurrido un error."
    },

    "fr": {},
    "de": {},
    "it": {},
    "pt": {},
    "nl": {},
    "pl": {}
}


def t(user, key, **kwargs):

    language = get_user_language(user)

    translations = TRANSLATIONS.get(
        language,
        TRANSLATIONS["en"]
    )

    text = translations.get(
        key,
        TRANSLATIONS["en"].get(
            key,
            key
        )
    )

    return text.format(**kwargs)


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
                PRIMARY KEY (
                    guild_id,
                    user_id,
                    period
                )
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
            INSERT INTO message_settings (
                guild_id,
                enabled
            )
            VALUES (?, ?)

            ON CONFLICT(guild_id)
            DO UPDATE SET enabled = excluded.enabled
        """, (
            guild_id,
            1 if enabled else 0
        ))

        conn.commit()


def save_message(
    guild_id,
    user_id,
    channel_id
):

    now = datetime.now(
        timezone.utc
    ).isoformat()

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

    now = datetime.now(
        timezone.utc
    )

    if period == "today":

        return now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

    if period == "week":

        start = now - timedelta(
            days=now.weekday()
        )

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


def get_real_count(
    guild_id,
    user_id,
    period
):

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

    start = get_period_start(
        period
    )

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


def get_adjusted_count(
    guild_id,
    user_id,
    period
):

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

        current_start = get_period_start(
            period
        )

        if not current_start:
            return real_count

        if period_start != current_start.isoformat():

            return real_count

    difference = real_count - reference_real

    return max(
        0,
        amount + difference
    )


def set_adjusted_count(
    guild_id,
    user_id,
    period,
    amount
):

    real_count = get_real_count(
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

            ON CONFLICT(
                guild_id,
                user_id,
                period
            )
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
                PRIMARY KEY (
                    guild_id,
                    user_id
                )
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


def set_afk(
    guild_id,
    user_id,
    reason,
    original_nick
):

    with sqlite3.connect(AFK_DB) as conn:

        conn.execute("""
            INSERT INTO afk (
                guild_id,
                user_id,
                reason,
                original_nick
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(
                guild_id,
                user_id
            )
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


def remove_afk(
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
            datetime.now(
                timezone.utc
            ).isoformat()
        ))

        conn.commit()


def get_afk_messages(
    guild_id,
    afk_user_id
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
            afk_user_id
        )).fetchall()

    return rows


def delete_afk_messages(
    guild_id,
    afk_user_id
):

    with sqlite3.connect(AFK_DB) as conn:

        conn.execute("""
            DELETE FROM afk_messages
            WHERE guild_id = ?
            AND afk_user_id = ?
        """, (
            guild_id,
            afk_user_id
        ))

        conn.commit()


# ============================================================
# BOT
# ============================================================

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
    print(
        f"✅ Bot conectado como {bot.user}"
    )
    print(
        f"🆔 ID: {bot.user.id}"
    )
    print(
        f"🌐 Servidores: {len(bot.guilds)}"
    )
    print("=" * 50)

    if not commands_cleaned:

        print(
            "🧹 Limpiando comandos antiguos..."
        )

        for guild in bot.guilds:

            try:

                old_commands = (
                    await bot.tree.fetch_commands(
                        guild=guild
                    )
                )

                if old_commands:

                    bot.tree.clear_commands(
                        guild=guild
                    )

                    await bot.tree.sync(
                        guild=guild
                    )

                    print(
                        f"🧹 {guild.name}: comandos antiguos eliminados."
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
# AFK ACTIVATE
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

    current_name = member.display_name

    if current_name.startswith("[AFK] "):

        new_nick = current_name

    else:

        new_nick = f"[AFK] {current_name}"

    if len(new_nick) > 32:

        new_nick = new_nick[:32]

    set_afk(
        guild.id,
        member.id,
        reason,
        original_nick
    )

    try:

        if guild.me.guild_permissions.manage_nicknames:

            await member.edit(
                nick=new_nick,
                reason="AFK activated"
            )

    except discord.Forbidden:

        pass


# ============================================================
# AFK DEACTIVATE
# ============================================================

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
                reason="AFK removed"
            )

    except discord.Forbidden:

        pass

    pending = get_afk_messages(
        guild.id,
        member.id
    )

    remove_afk(
        guild.id,
        member.id
    )

    if pending:

        language = get_user_language(
            member
        )

        embed = discord.Embed(
            title=t(
                member,
                "messages_while_afk"
            ),
            description=t(
                member,
                "messages_description"
            ),
            color=discord.Color.blurple()
        )

        for sender_id, msg in pending:

            sender = guild.get_member(
                sender_id
            )

            if sender:

                sender_name = sender.display_name

            else:

                sender_name = "Unknown user"

            embed.add_field(
                name=t(
                    member,
                    "from_user",
                    name=sender_name
                ),
                value=msg[:1024],
                inline=False
            )

        try:

            await member.send(
                embed=embed
            )

        except discord.Forbidden:

            pass

    delete_afk_messages(
        guild.id,
        member.id
    )

    return True


# ============================================================
# AFK MESSAGE MODAL
# ============================================================

class AFKMessageModal(
    discord.ui.Modal
):

    def __init__(
        self,
        afk_user_id,
        guild_id,
        sender
    ):

        super().__init__(
            title="Leave a message"
        )

        self.afk_user_id = afk_user_id
        self.guild_id = guild_id
        self.sender = sender

        self.message_input = discord.ui.TextInput(
            label="Your message",
            placeholder=(
                "Write the message they should receive..."
            ),
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )

        self.add_item(
            self.message_input
        )

    async def on_submit(
        self,
        interaction
    ):

        save_afk_message(
            self.guild_id,
            self.afk_user_id,
            interaction.user.id,
            self.message_input.value
        )

        await interaction.response.send_message(
            t(
                interaction.user,
                "message_saved"
            ),
            ephemeral=True
        )


# ============================================================
# AFK BUTTON
# ============================================================

class AFKMessageView(
    discord.ui.View
):

    def __init__(
        self,
        afk_user_id,
        guild_id
    ):

        super().__init__(
            timeout=300
        )

        self.afk_user_id = afk_user_id
        self.guild_id = guild_id

    @discord.ui.button(
        label="Leave a message",
        style=discord.ButtonStyle.primary,
        emoji="💬"
    )
    async def leave_message(
        self,
        interaction,
        button
    ):

        data = get_afk(
            self.guild_id,
            self.afk_user_id
        )

        if not data:

            await interaction.response.send_message(
                t(
                    interaction.user,
                    "not_afk"
                ),
                ephemeral=True
            )

            return

        await interaction.response.send_modal(
            AFKMessageModal(
                self.afk_user_id,
                self.guild_id,
                interaction.user
            )
        )


# ============================================================
# AFK PREFIX
# ============================================================

@bot.command(name="afk")
async def afk_prefix(
    ctx,
    *,
    reason=None
):

    if ctx.guild is None:

        await ctx.send(
            t(
                ctx.author,
                "not_server"
            )
        )

        return

    if not reason or not reason.strip():

        await ctx.send(
            t(
                ctx.author,
                "no_reason"
            )
        )

        return

    await activate_afk(
        ctx.guild,
        ctx.author,
        reason.strip()
    )

    await ctx.send(
        f"{t(ctx.author, 'afk_set')}\n"
        f"**{t(ctx.author, 'reason')}:** "
        f"{reason.strip()}"
    )


# ============================================================
# AFK SLASH
# ============================================================

@bot.tree.command(
    name="afk",
    description="Set yourself as AFK"
)
@app_commands.describe(
    reason="Why are you AFK?"
)
async def afk_slash(
    interaction,
    reason: str
):

    if not reason.strip():

        await interaction.response.send_message(
            t(
                interaction.user,
                "no_reason"
            ),
            ephemeral=True
        )

        return

    member = interaction.guild.get_member(
        interaction.user.id
    )

    if not member:

        await interaction.response.send_message(
            t(
                interaction.user,
                "generic_error"
            ),
            ephemeral=True
        )

        return

    await activate_afk(
        interaction.guild,
        member,
        reason.strip()
    )

    await interaction.response.send_message(
        f"{t(interaction.user, 'afk_set')}\n"
        f"**{t(interaction.user, 'reason')}:** "
        f"{reason.strip()}"
    )


# ============================================================
# MEMBERCOUNT
# ============================================================

@bot.command(name="membercount")
async def membercount_prefix(ctx):

    await ctx.send(
        t(
            ctx.author,
            "member_count",
            server=ctx.guild.name,
            count=ctx.guild.member_count
        )
    )


@bot.tree.command(
    name="membercount",
    description="Show the server member count"
)
async def membercount_slash(
    interaction
):

    await interaction.response.send_message(
        t(
            interaction.user,
            "member_count",
            server=interaction.guild.name,
            count=interaction.guild.member_count
        )
    )


# ============================================================
# BAN
# ============================================================

@bot.command(name="ban")
@commands.has_permissions(
    ban_members=True
)
async def ban_prefix(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    await member.ban(
        reason=reason
    )

    await ctx.send(
        f"🔨 **{member}** banned.\n"
        f"**{t(ctx.author, 'reason')}:** {reason}"
    )


@bot.tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.describe(
    member="Member to ban",
    reason="Reason"
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def ban_slash(
    interaction,
    member: discord.Member,
    reason="No reason provided"
):

    await member.ban(
        reason=reason
    )

    await interaction.response.send_message(
        f"🔨 **{member}** banned.\n"
        f"**{t(interaction.user, 'reason')}:** {reason}"
    )


# ============================================================
# KICK
# ============================================================

@bot.command(name="kick")
@commands.has_permissions(
    kick_members=True
)
async def kick_prefix(
    ctx,
    member: discord.Member,
    *,
    reason="No reason provided"
):

    await member.kick(
        reason=reason
    )

    await ctx.send(
        f"👢 **{member}** kicked."
    )


@bot.tree.command(
    name="kick",
    description="Kick a member"
)
@app_commands.describe(
    member="Member to kick",
    reason="Reason"
)
@app_commands.checks.has_permissions(
    kick_members=True
)
async def kick_slash(
    interaction,
    member: discord.Member,
    reason="No reason provided"
):

    await member.kick(
        reason=reason
    )

    await interaction.response.send_message(
        f"👢 **{member}** kicked."
    )


# ============================================================
# UNBAN
# ============================================================

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
            f"🔓 **{user}** unbanned."
        )

    except discord.NotFound:

        await ctx.send(
            "❌ That user isn't banned."
        )


@bot.tree.command(
    name="unban",
    description="Unban a user"
)
@app_commands.describe(
    user_id="User ID"
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def unban_slash(
    interaction,
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
            f"🔓 **{user}** unbanned."
        )

    except (
        ValueError,
        discord.NotFound
    ):

        await interaction.response.send_message(
            "❌ Invalid ID or user isn't banned.",
            ephemeral=True
        )


# ============================================================
# SETNICK
# ============================================================

async def execute_setnick(
    interaction_or_ctx,
    target,
    nickname
):

    guild = interaction_or_ctx.guild

    actor = (
        interaction_or_ctx.author
        if isinstance(
            interaction_or_ctx,
            commands.Context
        )
        else interaction_or_ctx.user
    )

    if target.id != actor.id:

        if not actor.guild_permissions.manage_nicknames:

            msg = t(
                actor,
                "no_nick_permission"
            )

            if isinstance(
                interaction_or_ctx,
                commands.Context
            ):

                await interaction_or_ctx.send(msg)

            else:

                await interaction_or_ctx.response.send_message(
                    msg,
                    ephemeral=True
                )

            return

    if target.id == guild.owner_id:

        msg = t(
            actor,
            "cannot_owner_nick"
        )

        if isinstance(
            interaction_or_ctx,
            commands.Context
        ):

            await interaction_or_ctx.send(msg)

        else:

            await interaction_or_ctx.response.send_message(
                msg,
                ephemeral=True
            )

        return

    if target.top_role >= guild.me.top_role:

        msg = t(
            actor,
            "role_hierarchy_nick"
        )

        if isinstance(
            interaction_or_ctx,
            commands.Context
        ):

            await interaction_or_ctx.send(msg)

        else:

            await interaction_or_ctx.response.send_message(
                msg,
                ephemeral=True
            )

        return

    if len(nickname) > 32:

        msg = t(
            actor,
            "nickname_too_long"
        )

        if isinstance(
            interaction_or_ctx,
            commands.Context
        ):

            await interaction_or_ctx.send(msg)

        else:

            await interaction_or_ctx.response.send_message(
                msg,
                ephemeral=True
            )

        return

    try:

        await target.edit(
            nick=nickname,
            reason=f"Nickname changed by {actor}"
        )

        msg = t(
            actor,
            "nickname_changed",
            user=target,
            nickname=nickname
        )

        if isinstance(
            interaction_or_ctx,
            commands.Context
        ):

            await interaction_or_ctx.send(msg)

        else:

            await interaction_or_ctx.response.send_message(
                msg
            )

    except discord.Forbidden:

        msg = t(
            actor,
            "cannot_nick"
        )

        if isinstance(
            interaction_or_ctx,
            commands.Context
        ):

            await interaction_or_ctx.send(msg)

        else:

            await interaction_or_ctx.response.send_message(
                msg,
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
            f"❌ Usage: "
            f"`{get_prefix(ctx.guild.id)}setnick @user nickname`"
        )

        return

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
                t(
                    ctx.author,
                    "nickname_required"
                )
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
    description="Change a user's nickname"
)
@app_commands.describe(
    member="Member",
    nickname="New nickname"
)
@app_commands.checks.has_permissions(
    manage_nicknames=True
)
async def setnick_slash(
    interaction,
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
            t(
                ctx.author,
                "purge_range"
            )
        )

        return

    deleted = await ctx.channel.purge(
        limit=amount + 1
    )

    msg = await ctx.send(
        t(
            ctx.author,
            "purged",
            count=max(
                0,
                len(deleted) - 1
            )
        )
    )

    await msg.delete(
        delay=1
    )


@bot.tree.command(
    name="purge",
    description="Delete messages"
)
@app_commands.describe(
    amount="Amount of messages"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def purge_slash(
    interaction,
    amount: int
):

    if amount < 1 or amount > 100:

        await interaction.response.send_message(
            t(
                interaction.user,
                "purge_range"
            ),
            ephemeral=True
        )

        return

    await interaction.channel.purge(
        limit=amount
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "purged",
            count=amount
        ),
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
            t(
                ctx.author,
                "prefix_too_long"
            )
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
@app_commands.describe(
    new_prefix="New prefix"
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def prefix_slash(
    interaction,
    new_prefix: str
):

    if len(new_prefix) > 5:

        await interaction.response.send_message(
            t(
                interaction.user,
                "prefix_too_long"
            ),
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


# ============================================================
# MESSAGE STATS
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
        title=t(
            member,
            "stats_title",
            name=member.display_name
        ),
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(
        name=t(member, "today"),
        value=f"**{today:,}**",
        inline=True
    )

    embed.add_field(
        name=t(member, "week"),
        value=f"**{week:,}**",
        inline=True
    )

    embed.add_field(
        name=t(member, "month"),
        value=f"**{month:,}**",
        inline=True
    )

    embed.add_field(
        name=t(member, "total"),
        value=f"**{total:,}**",
        inline=True
    )

    return embed


def create_disabled_am_embed(
    guild,
    user
):

    embed = discord.Embed(
        title=t(
            user,
            "stats_disabled"
        ),
        description=t(
            user,
            "stats_disabled_desc",
            prefix=get_prefix(guild.id)
        ),
        color=discord.Color.red()
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
            embed=create_disabled_am_embed(
                ctx.guild,
                ctx.author
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


@bot.tree.command(
    name="am",
    description="Show message statistics"
)
@app_commands.describe(
    member="User to check"
)
async def am_slash(
    interaction,
    member: discord.Member = None
):

    if not is_message_tracking_enabled(
        interaction.guild.id
    ):

        await interaction.response.send_message(
            embed=create_disabled_am_embed(
                interaction.guild,
                interaction.user
            ),
            ephemeral=True
        )

        return

    if member is None:

        member = interaction.guild.get_member(
            interaction.user.id
        )

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


PERIOD_NAMES = {

    "today": "today",
    "week": "week",
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
            t(
                ctx.author,
                "invalid_period"
            )
        )

        return

    if amount < 0:

        await ctx.send(
            t(
                ctx.author,
                "negative_amount"
            )
        )

        return

    set_adjusted_count(
        ctx.guild.id,
        ctx.author.id,
        period_key,
        amount
    )

    await ctx.send(
        t(
            ctx.author,
            "stats_set",
            period=PERIOD_NAMES[period_key],
            amount=amount
        )
    )


@bot.tree.command(
    name="aset",
    description="Set message statistics"
)
@app_commands.describe(
    period="Period",
    amount="Amount"
)
@app_commands.choices(
    period=[
        app_commands.Choice(
            name="Today",
            value="today"
        ),
        app_commands.Choice(
            name="Week",
            value="week"
        ),
        app_commands.Choice(
            name="Month",
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
    interaction,
    period: app_commands.Choice[str],
    amount: int
):

    if amount < 0:

        await interaction.response.send_message(
            t(
                interaction.user,
                "negative_amount"
            ),
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
        t(
            interaction.user,
            "stats_set",
            period=period.name,
            amount=amount
        )
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
        t(
            ctx.author,
            "count_enabled"
        )
    )


@bot.tree.command(
    name="aenable",
    description="Enable message counting"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def aenable_slash(
    interaction
):

    set_message_tracking(
        interaction.guild.id,
        True
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "count_enabled"
        )
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
        t(
            ctx.author,
            "count_disabled"
        )
    )


@bot.tree.command(
    name="adesable",
    description="Disable message counting"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def adesable_slash(
    interaction
):

    set_message_tracking(
        interaction.guild.id,
        False
    )

    await interaction.response.send_message(
        t(
            interaction.user,
            "count_disabled"
        )
    )


# ============================================================
# ROLE FUNCTIONS
# ============================================================

def get_manageable_roles(guild):

    bot_member = guild.me

    return [
        role
        for role in guild.roles
        if not role.is_default()
        and not role.managed
        and role < bot_member.top_role
    ]


def get_promote_roles(
    guild,
    member
):

    return [
        role
        for role in get_manageable_roles(guild)
        if role > member.top_role
    ]


def get_demote_roles(
    guild,
    member
):

    return [
        role
        for role in get_manageable_roles(guild)
        if role < member.top_role
    ]


# ============================================================
# ROLE SELECT
# ============================================================

class RoleSelect(
    discord.ui.Select
):

    def __init__(
        self,
        requester,
        target,
        mode
    ):

        self.requester = requester
        self.target = target
        self.mode = mode

        if mode == "promote":

            roles = get_promote_roles(
                target.guild,
                target
            )

        else:

            roles = get_demote_roles(
                target.guild,
                target
            )

        roles = roles[:25]

        options = [
            discord.SelectOption(
                label=role.name[:100],
                value=str(role.id)
            )
            for role in roles
        ]

        super().__init__(
            placeholder=(
                "Select a role to promote"
                if mode == "promote"
                else "Select a role to demote"
            ),
            options=options
        )

    async def callback(
        self,
        interaction
    ):

        if interaction.user.id != self.requester.id:

            await interaction.response.send_message(
                t(
                    interaction.user,
                    "menu_not_you"
                ),
                ephemeral=True
            )

            return

        role = interaction.guild.get_role(
            int(self.values[0])
        )

        if not role:

            await interaction.response.send_message(
                t(
                    interaction.user,
                    "generic_error"
                ),
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
                content=t(
                    interaction.user,
                    "role_updated",
                    user=self.target.mention,
                    role=role.mention
                ),
                view=None
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                t(
                    interaction.user,
                    "role_no_permission"
                ),
                ephemeral=True
            )


class RoleView(
    discord.ui.View
):

    def __init__(
        self,
        requester,
        target,
        mode
    ):

        super().__init__(
            timeout=60
        )

        self.add_item(
            RoleSelect(
                requester,
                target,
                mode
            )
        )


async def execute_role_change(
    interaction,
    target,
    mode
):

    if target.id == interaction.user.id:

        await interaction.response.send_message(
            t(
                interaction.user,
                "cannot_self_role"
            ),
            ephemeral=True
        )

        return

    if target.id == interaction.guild.owner_id:

        await interaction.response.send_message(
            t(
                interaction.user,
                "cannot_modify_owner"
            ),
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
            t(
                interaction.user,
                "no_roles"
            ),
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        (
            t(
                interaction.user,
                "select_promote",
                user=target.mention
            )
            if mode == "promote"
            else
            t(
                interaction.user,
                "select_demote",
                user=target.mention
            )
        ),
        view=RoleView(
            interaction.user,
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
            t(
                ctx.author,
                "no_roles"
            )
        )

        return

    await ctx.send(
        t(
            ctx.author,
            "select_promote",
            user=member.mention
        ),
        view=RoleView(
            ctx.author,
            member,
            "promote"
        )
    )


@bot.tree.command(
    name="promote",
    description="Promote a member"
)
@app_commands.describe(
    member="Member"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def promote_slash(
    interaction,
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
            t(
                ctx.author,
                "no_roles"
            )
        )

        return

    await ctx.send(
        t(
            ctx.author,
            "select_demote",
            user=member.mention
        ),
        view=RoleView(
            ctx.author,
            member,
            "demote"
        )
    )


@bot.tree.command(
    name="demote",
    description="Demote a member"
)
@app_commands.describe(
    member="Member"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def demote_slash(
    interaction,
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
    description="Manage roles"
)


@role_group.command(
    name="add",
    description="Add a role to a member"
)
@app_commands.describe(
    member="Member",
    role="Role"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def role_add(
    interaction,
    member: discord.Member,
    role: discord.Role
):

    if role.is_default() or role.managed:

        await interaction.response.send_message(
            t(
                interaction.user,
                "cannot_manage_role"
            ),
            ephemeral=True
        )

        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_above_bot"
            ),
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
                user=member.mention
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_no_permission"
            ),
            ephemeral=True
        )


@role_group.command(
    name="remove",
    description="Remove a role from a member"
)
@app_commands.describe(
    member="Member",
    role="Role"
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def role_remove(
    interaction,
    member: discord.Member,
    role: discord.Role
):

    if role.is_default() or role.managed:

        await interaction.response.send_message(
            t(
                interaction.user,
                "cannot_manage_role"
            ),
            ephemeral=True
        )

        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_above_bot"
            ),
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
                user=member.mention
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            t(
                interaction.user,
                "role_no_permission"
            ),
            ephemeral=True
        )


bot.tree.add_command(
    role_group
)


# ============================================================
# ON MESSAGE
# ============================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is None:

        await bot.process_commands(
            message
        )

        return

    # ========================================================
    # AFK PING
    # ========================================================

    for mentioned in message.mentions:

        if mentioned.bot:
            continue

        if mentioned.id == message.author.id:
            continue

        afk_data = get_afk(
            message.guild.id,
            mentioned.id
        )

        if afk_data:

            reason = afk_data[0]

            embed = discord.Embed(
                title=t(
                    message.author,
                    "user_afk"
                ),
                description=t(
                    message.author,
                    "is_afk",
                    name=mentioned.display_name
                ),
                color=discord.Color.orange()
            )

            embed.add_field(
                name=t(
                    message.author,
                    "reason"
                ),
                value=reason,
                inline=False
            )

            embed.set_thumbnail(
                url=mentioned.display_avatar.url
            )

            await message.channel.send(
                embed=embed,
                view=AFKMessageView(
                    mentioned.id,
                    message.guild.id
                )
            )

    # ========================================================
    # REMOVE AFK WHEN USER TALKS
    # ========================================================

    afk_data = get_afk(
        message.guild.id,
        message.author.id
    )

    if afk_data:

        prefix = get_prefix(
            message.guild.id
        )

        content = message.content.strip()

        is_afk_command = (
            content == f"{prefix}afk"
            or content.startswith(
                f"{prefix}afk "
            )
        )

        if not is_afk_command:

            removed = await deactivate_afk(
                message.guild,
                message.author
            )

            if removed:

                try:

                    back_message = await message.channel.send(
                        t(
                            message.author,
                            "back",
                            user=message.author.mention
                        )
                    )

                    await back_message.delete(
                        delay=1
                    )

                except discord.Forbidden:

                    pass

    # ========================================================
    # MESSAGE COUNTING
    # ========================================================

    if is_message_tracking_enabled(
        message.guild.id
    ):

        save_message(
            message.guild.id,
            message.author.id,
            message.channel.id
        )

    # ========================================================
    # PREFIX COMMANDS
    # ========================================================

    await bot.process_commands(
        message
    )


# ============================================================
# PREFIX ERROR HANDLER
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
            t(
                ctx.author,
                "missing_args"
            )
        )

        return

    if isinstance(
        error,
        commands.BadArgument
    ):

        await ctx.send(
            t(
                ctx.author,
                "invalid_argument"
            )
        )

        return

    print(
        f"❌ Prefix error: {error}"
    )


# ============================================================
# SLASH ERROR HANDLER
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
        f"❌ Slash error: {error}"
    )

    try:

        message = t(
            interaction.user,
            "generic_error"
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

    except Exception:

        pass


# ============================================================
# INITIALIZE DATABASES
# ============================================================

init_prefix_db()
init_message_db()
init_afk_db()


# ============================================================
# START
# ============================================================

print("🚀 Starting bot...")
print("💾 Prefix database: OK")
print("📊 Message database: OK")
print("💤 AFK database: OK")
print("🌍 Language system: OK")
print("🌐 Slash commands: GLOBAL")
print("📅 Message stats: Today / Week / Month / Total")
print("💤 AFK system: OK")
print("▶️ Connecting to Discord...")


bot.run(TOKEN)