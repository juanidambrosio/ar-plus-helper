from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.filters.repository import FilterRepository

CB_FILTERS_ADD_MENU = "filters:add_menu"
CB_FILTERS_LIST = "filters:list"
CB_FILTERS_DELETE_MENU = "filters:delete_menu"
CB_FILTERS_ADD_MAX_RESULTS = "filters:add:max_results"
CB_FILTERS_SET_LIMIT_PREFIX = "filters:set:limit:"
CB_FILTERS_DELETE_PREFIX = "filters:del:"
CB_FILTERS_CONFIRM_PREFIX = "filters:cfm:"
CB_FILTERS_CANCEL = "filters:cancel"


def _filters_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Agregar Filtro", callback_data=CB_FILTERS_ADD_MENU)],
            [InlineKeyboardButton("Ver mi filtro", callback_data=CB_FILTERS_LIST)],
            [
                InlineKeyboardButton(
                    "Eliminar filtro", callback_data=CB_FILTERS_DELETE_MENU
                )
            ],
        ]
    )


def _add_filter_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Max Resultados", callback_data=CB_FILTERS_ADD_MAX_RESULTS
                )
            ],
            [InlineKeyboardButton("Atrás", callback_data=CB_FILTERS_CANCEL)],
        ]
    )


def _limit_buttons_keyboard() -> InlineKeyboardMarkup:
    rows = []
    current_row = []
    for i in range(1, 32):
        current_row.append(
            InlineKeyboardButton(
                str(i), callback_data=f"{CB_FILTERS_SET_LIMIT_PREFIX}{i}"
            )
        )
        if len(current_row) == 5:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([InlineKeyboardButton("Atrás", callback_data=CB_FILTERS_ADD_MENU)])
    return InlineKeyboardMarkup(rows)


def _user_id(update: Update) -> str | None:
    user = update.effective_user
    if user is None:
        return None
    return str(user.id)


def _repo(context: ContextTypes.DEFAULT_TYPE) -> FilterRepository:
    return context.application.bot_data["filter_repo"]


async def filters_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Filtros de búsqueda:",
        reply_markup=_filters_menu_keyboard(),
    )


async def filters_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    user_id = _user_id(update)
    if user_id is None:
        return

    data = query.data or ""
    repo = _repo(context)

    if data == CB_FILTERS_ADD_MENU:
        await query.edit_message_text(
            "Elegí qué filtro agregar:",
            reply_markup=_add_filter_menu_keyboard(),
        )
        return

    if data == CB_FILTERS_ADD_MAX_RESULTS:
        await query.edit_message_text(
            "Elegí el límite máximo de resultados (1-31):",
            reply_markup=_limit_buttons_keyboard(),
        )
        return

    if data.startswith(CB_FILTERS_SET_LIMIT_PREFIX):
        limit_str = data[len(CB_FILTERS_SET_LIMIT_PREFIX) :]
        try:
            limit = int(limit_str)
        except ValueError:
            await query.edit_message_text("Límite inválido.")
            return
        repo.set_for_user(user_id, limit)
        await query.edit_message_text(
            f"Filtro guardado. Límite de resultados: {limit}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Volver al menú", callback_data=CB_FILTERS_CANCEL)]]
            )
        )
        return

    if data == CB_FILTERS_LIST:
        user_filter = repo.get_by_user(user_id)
        if user_filter is None:
            await query.edit_message_text(
                "No tenés ningún filtro activo. Límite por defecto: 10 resultados.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Volver al menú", callback_data=CB_FILTERS_CANCEL)]]
                )
            )
        else:
            await query.edit_message_text(
                f"Filtro activo:\nLímite de resultados: {user_filter.limit}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Volver al menú", callback_data=CB_FILTERS_CANCEL)]]
                )
            )
        return

    if data == CB_FILTERS_DELETE_MENU:
        user_filter = repo.get_by_user(user_id)
        if user_filter is None:
            await query.edit_message_text(
                "No tenés filtros activos.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Volver al menú", callback_data=CB_FILTERS_CANCEL)]]
                )
            )
            return
        rows = [
            [
                InlineKeyboardButton(
                    f"Límite: {user_filter.limit}",
                    callback_data=f"{CB_FILTERS_DELETE_PREFIX}{user_filter.id}",
                )
            ],
            [InlineKeyboardButton("Cancelar", callback_data=CB_FILTERS_CANCEL)],
        ]
        await query.edit_message_text(
            "Elegí el filtro a eliminar:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if data == CB_FILTERS_CANCEL:
        await query.edit_message_text(
            "Filtros de búsqueda:",
            reply_markup=_filters_menu_keyboard(),
        )
        return

    if data.startswith(CB_FILTERS_DELETE_PREFIX):
        filter_id = data[len(CB_FILTERS_DELETE_PREFIX) :]
        user_filter = repo.get_by_id(user_id, filter_id)
        if user_filter is None:
            await query.edit_message_text(
                "Filtro no encontrado.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Volver al menú", callback_data=CB_FILTERS_CANCEL)]]
                )
            )
            return
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Sí, eliminar",
                        callback_data=f"{CB_FILTERS_CONFIRM_PREFIX}{filter_id}",
                    ),
                    InlineKeyboardButton("No", callback_data=CB_FILTERS_DELETE_MENU),
                ]
            ]
        )
        await query.edit_message_text(
            f"¿Eliminar este filtro?\nLímite: {user_filter.limit}",
            reply_markup=keyboard,
        )
        return

    if data.startswith(CB_FILTERS_CONFIRM_PREFIX):
        filter_id = data[len(CB_FILTERS_CONFIRM_PREFIX) :]
        deleted = repo.delete_by_id(user_id, filter_id)
        if deleted:
            await query.edit_message_text(
                "Filtro eliminado.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Volver al menú", callback_data=CB_FILTERS_CANCEL)]]
                )
            )
        else:
            await query.edit_message_text(
                "Filtro no encontrado o ya eliminado.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Volver al menú", callback_data=CB_FILTERS_CANCEL)]]
                )
            )
        return
