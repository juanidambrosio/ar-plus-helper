from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.alerts.notify import format_alert_line, format_alerts_list
from bot.alerts.parse import NUEVA_ALERTA_USAGE, parse_nueva_alerta
from bot.alerts.repository import AlertRepository

CB_ALERTS_CREATE = "alerts:create"
CB_ALERTS_LIST = "alerts:list"
CB_ALERTS_DELETE_MENU = "alerts:delete_menu"
CB_ALERTS_DELETE_PREFIX = "alerts:del:"
CB_ALERTS_CONFIRM_PREFIX = "alerts:cfm:"
CB_ALERTS_CANCEL = "alerts:cancel"


def _alerts_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Crear alerta", callback_data=CB_ALERTS_CREATE)],
            [InlineKeyboardButton("Ver mis alertas", callback_data=CB_ALERTS_LIST)],
            [
                InlineKeyboardButton(
                    "Eliminar alerta", callback_data=CB_ALERTS_DELETE_MENU
                )
            ],
        ]
    )


def _user_id(update: Update) -> str | None:
    user = update.effective_user
    if user is None:
        return None
    return str(user.id)


def _repo(context: ContextTypes.DEFAULT_TYPE) -> AlertRepository:
    return context.application.bot_data["alert_repo"]


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Alertas de vuelos:",
        reply_markup=_alerts_menu_keyboard(),
    )


async def nueva_alerta_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message:
        return
    user_id = _user_id(update)
    if user_id is None:
        return

    parsed = parse_nueva_alerta(context.args or [])
    if isinstance(parsed, str):
        await update.message.reply_text(parsed, parse_mode="Markdown")
        return

    alert_id = _repo(context).create(user_id, parsed)
    line = format_alert_line(parsed)
    await update.message.reply_text(f"Alerta creada ({alert_id[:8]}…):\n{line}")


async def alerts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    user_id = _user_id(update)
    if user_id is None:
        return

    data = query.data or ""
    repo = _repo(context)

    if data == CB_ALERTS_CREATE:
        await query.edit_message_text(NUEVA_ALERTA_USAGE, parse_mode="Markdown")
        return

    if data == CB_ALERTS_LIST:
        alerts = repo.list_by_user(user_id)
        await query.edit_message_text(format_alerts_list(alerts))
        return

    if data == CB_ALERTS_DELETE_MENU:
        alerts = repo.list_by_user(user_id)
        if not alerts:
            await query.edit_message_text("No tenés alertas.")
            return
        rows = []
        for alert in alerts:
            label = format_alert_line(alert)
            if len(label) > 60:
                label = label[:57] + "..."
            rows.append(
                [
                    InlineKeyboardButton(
                        label,
                        callback_data=f"{CB_ALERTS_DELETE_PREFIX}{alert.id}",
                    )
                ]
            )
        rows.append(
            [InlineKeyboardButton("Cancelar", callback_data=CB_ALERTS_CANCEL)]
        )
        await query.edit_message_text(
            "Elegí la alerta a eliminar:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if data == CB_ALERTS_CANCEL:
        await query.edit_message_text(
            "Alertas de vuelos:",
            reply_markup=_alerts_menu_keyboard(),
        )
        return

    if data.startswith(CB_ALERTS_DELETE_PREFIX):
        alert_id = data[len(CB_ALERTS_DELETE_PREFIX) :]
        alert = repo.get_for_user(user_id, alert_id)
        if alert is None:
            await query.edit_message_text("Alerta no encontrada.")
            return
        line = format_alert_line(alert)
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Sí, eliminar",
                        callback_data=f"{CB_ALERTS_CONFIRM_PREFIX}{alert_id}",
                    ),
                    InlineKeyboardButton("No", callback_data=CB_ALERTS_DELETE_MENU),
                ]
            ]
        )
        await query.edit_message_text(
            f"¿Eliminar esta alerta?\n{line}",
            reply_markup=keyboard,
        )
        return

    if data.startswith(CB_ALERTS_CONFIRM_PREFIX):
        alert_id = data[len(CB_ALERTS_CONFIRM_PREFIX) :]
        deleted = repo.delete_for_user(user_id, alert_id)
        if deleted:
            await query.edit_message_text("Alerta eliminada.")
        else:
            await query.edit_message_text("Alerta no encontrada.")
        return
