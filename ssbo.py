#!/usr/bin/python3.5

import requests
import time
import datetime
import telebot
from telebot import types
from dbhelper import DBHelper, ChatSearch, Item
from re import sub
from decimal import Decimal
import logging
from logging.handlers import RotatingFileHandler
import sys
import threading
import os
import locale
from fake_useragent import UserAgent

TOKEN = os.getenv("BOT_TOKEN", "Bot Token does not exist")
URL = "https://api.telegram.org/bot{}/".format(TOKEN)
URL_ITEMS = "https://api.wallapop.com/api/v3/search?source=search_box"
PROFILE = os.getenv("PROFILE")

if PROFILE is None:
    db = DBHelper()
else:
    db = DBHelper("db.sqlite")


ICON_VIDEO_GAMES = u'\U0001F3AE'  # 🎮
ICON_WARNING____ = u'\U000026A0'  # ⚠️
ICON_HIGH_VOLTAG = u'\U000026A1'  # ⚡️
ICON_COLLISION__ = u'\U0001F4A5'  # 💥
ICON_EXCLAMATION = u'\U00002757'  # ❗
ICON_DIRECT_HIT_ = u'\U0001F3AF'  # 🎯


def notel(chat_id, price, title, url_item, obs=None, user_id=None):
    # Determinar el tipo de notificación
    if obs is not None:
        # Es una bajada de precio
        text = f"📉 *¡BAJADA DE PRECIO!*\n\n"
        text += f"🏷️ *{title}*\n\n"
        text += f"💰 *Precio actual:* {locale.currency(price, grouping=True)}\n"
        text += f"📊 *Precio anterior:* {obs}\n\n"
        text += f"💡 *¡Ahorra dinero con esta oferta!*"
    else:
        # Es un producto nuevo
        text = f"🆕 *¡PRODUCTO NUEVO!*\n\n"
        text += f"🏷️ *{title}*\n\n"
        text += f"💰 *Precio:* {locale.currency(price, grouping=True)}\n"
        if user_id:
            text += f"👤 *Vendedor ID:* {user_id}\n"
        text += f"\n🎯 *¡Nuevo producto encontrado para ti!*"
    
    text += f"\n\n🔗 *Ver en Wallapop:*\n"
    text += f"https://es.wallapop.com/item/{url_item}"
    
    # Crear botón inline para ir al producto
    keyboard = types.InlineKeyboardMarkup()
    view_btn = types.InlineKeyboardButton("👀 Ver producto en Wallapop", url=f"https://es.wallapop.com/item/{url_item}")
    keyboard.add(view_btn)
    
    try:
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=False)
        logging.info(f"Notificación enviada a {chat_id}: {title}")
    except Exception as e:
        logging.error(f"Error enviando notificación: {e}")
        # Fallback sin botones si hay error
        urlz0rb0t = URL + "sendMessage?chat_id=%s&parse_mode=markdown&text=%s" % (chat_id, text)
        requests.get(url=urlz0rb0t)


def get_url_list(search):
    url = URL_ITEMS
    url += '&keywords='
    url += "+".join(search.kws.split(" "))
    url += '&time_filter=today'
    if search.cat_ids is not None:
        url += '&category_ids='
        url += search.cat_ids
    if search.min_price is not None:
        url += '&min_sale_price='
        url += search.min_price
    if search.max_price is not None:
        url += '&max_sale_price='
        url += search.max_price
    if search.dist is not None:
        url += '&dist='
        url += search.dist
    if search.orde is not None:
        url += '&order_by='
        url += search.orde
    return url


def get_items(url, chat_id):
    try:
   
        ua = UserAgent()

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'es,ru;q=0.9,en;q=0.8,de;q=0.7,pt;q=0.6',
            'Connection': 'keep-alive',
            'DeviceOS': '0',
            'Origin': 'https://es.wallapop.com',
            'Referer': 'https://es.wallapop.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': f'{ua.random}',
            'X-AppVersion': '75491',
            'X-DeviceOS': '0',
            'sec-ch-ua-mobile': '?0',
        }

        response = requests.get(url=url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()

            items = data.get('data', {}).get('section', {}).get('payload', {}).get('items', [])

            for x in items:
                logging.info('Encontrado: id=%s, price=%s, title=%s, user=%s',
                             str(x['id']),
                             locale.currency(x['price']['amount'], grouping=True),
                             x['title'],
                             x['user_id'])

                i = db.search_item(x['id'], chat_id)
                
                if i is None:
                    # Establecer fecha actual como publishDate
                    current_time = int(time.time() * 1000)
                    db.add_item(x['id'], chat_id, x['title'], x['price']['amount'], x['web_slug'], x['user_id'], current_time)
                    notel(chat_id, x['price']['amount'], x['title'], x['web_slug'], None, x['user_id'])
                    logging.info('New: id=%s, price=%s, title=%s', str(x['id']), locale.currency(x['price']['amount'], grouping=True), x['title'])
                else:
                    money = str(x['price']['amount'])
                    value_json = Decimal(sub(r'[^\d.]', '', money))
                    value_db = Decimal(sub(r'[^\d.]', '', i.price))
                    
                    if value_json < value_db:
                        new_obs = locale.currency(i.price, grouping=True)
                        if i.observaciones is not None:
                            new_obs += ' < ' + i.observaciones
                        db.update_item(x['id'], money, new_obs)
                        obs = new_obs  # Pasar el precio anterior completo
                        notel(chat_id, x['price']['amount'], x['title'], x['web_slug'], obs, x['user_id'])
                        logging.info('Baja: id=%s, price=%s, title=%s', str(x['id']), locale.currency(x['price']['amount'], grouping=True), x['title'])
        else:
            logging.error(f"Failed to fetch data: {response.status_code}")

    except Exception as e:
        logging.error(e)


def handle_exception(self, exception):
    logging.exception(exception)
    logging.error("Ha ocurrido un error con la llamada a Telegram. Se reintenta la conexión")
    print("Ha ocurrido un error con la llamada a Telegram. Se reintenta la conexión")
    bot.polling(none_stop=True, timeout=3000)


# INI Actualización de db a partir de la librería de Telegram
# bot = telebot.TeleBot(TOKEN, exception_handler=handle_exception)
bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start', 'help', 's', 'h'])
def send_welcome(message):
    welcome_text = f"""🎯 *¡Bienvenido a WallaBot!*

🔍 *Comandos disponibles:*

📝 *Añadir búsqueda:*
`/add producto,min-max`
💡 *Ejemplos:*
• `/add iPhone 13,200-400`
• `/add bicicleta montaña,50-150`
• `/add zapatos nike,20-80`

📋 *Ver tus búsquedas:*
`/lis` - Lista todas tus búsquedas activas

📊 *Ver estadísticas:*
`/stats` - Estadísticas detalladas de tus búsquedas

🗑️ *Eliminar búsqueda:*
`/del nombre_búsqueda`
💡 *Ejemplo:* `/del iPhone 13`

❓ *Ayuda:*
`/help` - Muestra este mensaje

⚡ *Funcionamiento automático:*
• Reviso Wallapop cada 5 minutos
• Te aviso de productos nuevos
• Te notifico bajadas de precio

🎮 ¡Empieza añadiendo tu primera búsqueda!"""

    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')


@bot.message_handler(commands=['del', 'borrar', 'd'])
def delete_search(message):
    parametros = str(message.text).split(' ', 1)
    if len(parametros) < 2:
        bot.send_message(message.chat.id, 
                        "❌ *Error:* Debes especificar qué búsqueda eliminar\n\n"
                        "💡 *Ejemplo:* `/del iPhone 13`\n"
                        "📋 Usa `/lis` para ver tus búsquedas activas", 
                        parse_mode='Markdown')
        return
    
    search_term = ' '.join(parametros[1:])
    
    # Verificar si la búsqueda existe antes de eliminar
    existing_searches = db.get_chat_searchs(message.chat.id)
    search_exists = any(search.kws.lower() == search_term.lower() for search in existing_searches)
    
    if not search_exists:
        bot.send_message(message.chat.id, 
                        f"❌ *No encontrado:* No tienes una búsqueda llamada '{search_term}'\n\n"
                        f"📋 Usa `/lis` para ver tus búsquedas activas", 
                        parse_mode='Markdown')
        return
    
    db.del_chat_search(message.chat.id, search_term)
    bot.send_message(message.chat.id, 
                    f"✅ *Búsqueda eliminada:* '{search_term}'\n\n"
                    f"🔍 Ya no recibirás notificaciones de esta búsqueda", 
                    parse_mode='Markdown')


@bot.message_handler(commands=['lis', 'listar', 'l'])
def get_searchs(message):
    searches = db.get_chat_searchs(message.chat.id)
    
    if not searches:
        bot.send_message(message.chat.id, 
                        "📭 *No tienes búsquedas activas*\n\n"
                        "💡 Añade una búsqueda con:\n"
                        "`/add producto,precio_min-precio_max`\n\n"
                        "🌟 *Ejemplo:* `/add iPhone 13,200-400`", 
                        parse_mode='Markdown')
        return
    
    # Crear mensaje con las búsquedas
    text = f"📋 *Tus búsquedas activas* ({len(searches)}):\n\n"
    
    for i, search in enumerate(searches, 1):
        text += f"🔍 *{i}.* {search.kws}\n"
        
        # Mostrar rango de precios
        if search.min_price or search.max_price:
            price_range = f"💰 Precio: "
            if search.min_price:
                price_range += f"{search.min_price}€"
            else:
                price_range += "0€"
            price_range += " - "
            if search.max_price:
                price_range += f"{search.max_price}€"
            else:
                price_range += "∞"
            text += price_range + "\n"
        
        # Mostrar categorías si las hay
        if search.cat_ids:
            text += f"🏷️ Categorías: {search.cat_ids}\n"
        
        text += "\n"
    
    # Crear teclado inline con botones para cada búsqueda
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    for i, search in enumerate(searches):
        # Botón para eliminar cada búsqueda específica
        delete_btn = types.InlineKeyboardButton(
            f"🗑️ Eliminar '{search.kws[:15]}{'...' if len(search.kws) > 15 else ''}'", 
            callback_data=f"delete_{search.kws}"
        )
        keyboard.add(delete_btn)
    
    # Botón para refrescar la lista
    refresh_btn = types.InlineKeyboardButton("🔄 Actualizar lista", callback_data="refresh_list")
    keyboard.add(refresh_btn)
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=keyboard)


# Comando para mostrar estadísticas
@bot.message_handler(commands=['stats', 'estadisticas', 'est'])
def show_statistics(message):
    searches = db.get_chat_searchs(message.chat.id)
    
    if not searches:
        bot.send_message(message.chat.id, 
                        "📊 *Estadísticas no disponibles*\n\n"
                        "❌ No tienes búsquedas activas\n\n"
                        "💡 Añade una búsqueda primero:\n"
                        "`/add producto,precio_min-precio_max`", 
                        parse_mode='Markdown')
        return
    
    # Obtener estadísticas generales
    general_stats = db.get_search_statistics(message.chat.id)
    search_activity = db.get_search_activity_stats(message.chat.id)
    recent_activity = db.get_recent_activity(message.chat.id, 24)
    
    # Construir mensaje de estadísticas generales
    stats_text = f"📊 *ESTADÍSTICAS GENERALES*\n\n"
    
    # Resumen general
    stats_text += f"🔍 *Búsquedas activas:* {len(searches)}\n"
    stats_text += f"📦 *Total productos encontrados:* {general_stats['total_items']}\n"
    stats_text += f"🆕 *Productos en últimas 24h:* {recent_activity}\n"
    stats_text += f"👥 *Vendedores únicos:* {general_stats['unique_sellers']}\n\n"
    
    # Estadísticas de precios (solo si hay productos)
    if general_stats['total_items'] > 0:
        stats_text += f"💰 *ANÁLISIS DE PRECIOS*\n"
        stats_text += f"📉 *Precio mínimo:* {locale.currency(general_stats['min_price'], grouping=True)}\n"
        stats_text += f"📈 *Precio máximo:* {locale.currency(general_stats['max_price'], grouping=True)}\n"
        stats_text += f"📊 *Precio promedio:* {locale.currency(general_stats['avg_price'], grouping=True)}\n\n"
    
    # Top 3 búsquedas más productivas
    if search_activity:
        stats_text += f"🏆 *TOP BÚSQUEDAS*\n"
        top_searches = sorted(search_activity, key=lambda x: x['items_found'], reverse=True)[:3]
        
        for i, search in enumerate(top_searches, 1):
            if search['items_found'] > 0:
                stats_text += f"{i}. *{search['search_term']}*\n"
                stats_text += f"   📦 {search['items_found']} productos"
                if search['price_drops'] > 0:
                    stats_text += f" | 📉 {search['price_drops']} bajadas"
                stats_text += f"\n"
        
        stats_text += f"\n"
    
    # Crear botones para estadísticas detalladas
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Botón para cada búsqueda
    for search in search_activity[:5]:  # Máximo 5 búsquedas para no saturar
        if search['items_found'] > 0:
            search_btn = types.InlineKeyboardButton(
                f"📊 {search['search_term']} ({search['items_found']} items)",
                callback_data=f"stats_{search['search_term']}"
            )
            keyboard.add(search_btn)
    
    # Botones adicionales
    refresh_btn = types.InlineKeyboardButton("🔄 Actualizar estadísticas", callback_data="refresh_stats")
    keyboard.add(refresh_btn)
    
    if general_stats['total_items'] > 0:
        best_deals_btn = types.InlineKeyboardButton("💎 Ver mejores ofertas", callback_data="best_deals")
        keyboard.add(best_deals_btn)
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown', reply_markup=keyboard)


# Manejador para los botones inline
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        if call.data.startswith("delete_"):
            # Extraer el nombre de la búsqueda a eliminar
            search_name = call.data[7:]  # Remover "delete_"
            
            # Eliminar la búsqueda
            db.del_chat_search(call.message.chat.id, search_name)
            
            # Responder al callback
            bot.answer_callback_query(call.id, f"✅ Búsqueda '{search_name}' eliminada")
            
            # Actualizar el mensaje con la lista actualizada
            searches = db.get_chat_searchs(call.message.chat.id)
            
            if not searches:
                # Si no quedan búsquedas, mostrar mensaje vacío
                new_text = ("📭 *No tienes búsquedas activas*\n\n"
                           "💡 Añade una búsqueda con:\n"
                           "`/add producto,precio_min-precio_max`")
                bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, 
                                     parse_mode='Markdown')
            else:
                # Recrear la lista actualizada
                text = f"📋 *Tus búsquedas activas* ({len(searches)}):\n\n"
                
                for i, search in enumerate(searches, 1):
                    text += f"🔍 *{i}.* {search.kws}\n"
                    
                    if search.min_price or search.max_price:
                        price_range = f"💰 Precio: "
                        if search.min_price:
                            price_range += f"{search.min_price}€"
                        else:
                            price_range += "0€"
                        price_range += " - "
                        if search.max_price:
                            price_range += f"{search.max_price}€"
                        else:
                            price_range += "∞"
                        text += price_range + "\n"
                    
                    if search.cat_ids:
                        text += f"🏷️ Categorías: {search.cat_ids}\n"
                    
                    text += "\n"
                
                # Recrear teclado
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                for search in searches:
                    delete_btn = types.InlineKeyboardButton(
                        f"🗑️ Eliminar '{search.kws[:15]}{'...' if len(search.kws) > 15 else ''}'", 
                        callback_data=f"delete_{search.kws}"
                    )
                    keyboard.add(delete_btn)
                
                refresh_btn = types.InlineKeyboardButton("🔄 Actualizar lista", callback_data="refresh_list")
                keyboard.add(refresh_btn)
                
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                     parse_mode='Markdown', reply_markup=keyboard)
        
        elif call.data == "refresh_list":
            # Refrescar la lista de búsquedas
            searches = db.get_chat_searchs(call.message.chat.id)
            
            bot.answer_callback_query(call.id, "🔄 Lista actualizada")
            
            if not searches:
                new_text = ("📭 *No tienes búsquedas activas*\n\n"
                           "💡 Añade una búsqueda con:\n"
                           "`/add producto,precio_min-precio_max`")
                bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, 
                                     parse_mode='Markdown')
            else:
                # Mismo código que arriba para recrear la lista
                text = f"📋 *Tus búsquedas activas* ({len(searches)}):\n\n"
                
                for i, search in enumerate(searches, 1):
                    text += f"🔍 *{i}.* {search.kws}\n"
                    
                    if search.min_price or search.max_price:
                        price_range = f"💰 Precio: "
                        if search.min_price:
                            price_range += f"{search.min_price}€"
                        else:
                            price_range += "0€"
                        price_range += " - "
                        if search.max_price:
                            price_range += f"{search.max_price}€"
                        else:
                            price_range += "∞"
                        text += price_range + "\n"
                    
                    if search.cat_ids:
                        text += f"🏷️ Categorías: {search.cat_ids}\n"
                    
                    text += "\n"
                
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                for search in searches:
                    delete_btn = types.InlineKeyboardButton(
                        f"🗑️ Eliminar '{search.kws[:15]}{'...' if len(search.kws) > 15 else ''}'", 
                        callback_data=f"delete_{search.kws}"
                    )
                    keyboard.add(delete_btn)
                
                refresh_btn = types.InlineKeyboardButton("🔄 Actualizar lista", callback_data="refresh_list")
                keyboard.add(refresh_btn)
                
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                     parse_mode='Markdown', reply_markup=keyboard)
        
        elif call.data.startswith("stats_"):
            # Mostrar estadísticas detalladas de una búsqueda específica
            search_term = call.data[6:]  # Remover "stats_"
            
            # Obtener estadísticas específicas
            search_stats = db.get_search_statistics(call.message.chat.id, search_term)
            items = db.get_items_by_search(call.message.chat.id, search_term)
            
            # Filtrar items por la búsqueda específica (aproximación simple)
            filtered_items = [item for item in items if search_term.lower() in item['title'].lower()]
            
            if not filtered_items:
                bot.answer_callback_query(call.id, f"❌ No hay datos para '{search_term}'")
                return
            
            # Estadísticas específicas
            total_items = len(filtered_items)
            prices = [item['price'] for item in filtered_items if item['price'] > 0]
            price_changes = sum(1 for item in filtered_items if item['price_changes'])
            
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                avg_price = sum(prices) / len(prices)
            else:
                min_price = max_price = avg_price = 0
            
            # Crear mensaje detallado
            detail_text = f"🔍 *ESTADÍSTICAS: {search_term}*\n\n"
            detail_text += f"📦 *Total productos:* {total_items}\n"
            detail_text += f"📉 *Bajadas de precio:* {price_changes}\n\n"
            
            if prices:
                detail_text += f"💰 *ANÁLISIS DE PRECIOS*\n"
                detail_text += f"📉 *Mínimo:* {locale.currency(min_price, grouping=True)}\n"
                detail_text += f"📈 *Máximo:* {locale.currency(max_price, grouping=True)}\n"
                detail_text += f"📊 *Promedio:* {locale.currency(avg_price, grouping=True)}\n\n"
            
            # Mostrar los 3 productos más baratos
            if filtered_items:
                detail_text += f"💎 *MEJORES OFERTAS*\n"
                cheapest = sorted(filtered_items, key=lambda x: x['price'])[:3]
                
                for i, item in enumerate(cheapest, 1):
                    if item['price'] > 0:
                        detail_text += f"{i}. {item['title'][:30]}{'...' if len(item['title']) > 30 else ''}\n"
                        detail_text += f"   💰 {locale.currency(item['price'], grouping=True)}"
                        if item['price_changes']:
                            detail_text += " 📉"
                        detail_text += f"\n"
            
            # Botón para volver
            back_keyboard = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("◀️ Volver a estadísticas", callback_data="refresh_stats")
            back_keyboard.add(back_btn)
            
            bot.answer_callback_query(call.id, f"📊 Estadísticas de '{search_term}'")
            bot.edit_message_text(detail_text, call.message.chat.id, call.message.message_id, 
                                 parse_mode='Markdown', reply_markup=back_keyboard)
        
        elif call.data == "refresh_stats":
            # Actualizar estadísticas generales
            searches = db.get_chat_searchs(call.message.chat.id)
            
            if not searches:
                new_text = ("📊 *Estadísticas no disponibles*\n\n"
                           "❌ No tienes búsquedas activas\n\n"
                           "💡 Añade una búsqueda primero:\n"
                           "`/add producto,precio_min-precio_max`")
                bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, 
                                     parse_mode='Markdown')
                bot.answer_callback_query(call.id, "📊 Estadísticas actualizadas")
                return
            
            # Recrear estadísticas (mismo código que el comando /stats)
            general_stats = db.get_search_statistics(call.message.chat.id)
            search_activity = db.get_search_activity_stats(call.message.chat.id)
            recent_activity = db.get_recent_activity(call.message.chat.id, 24)
            
            stats_text = f"📊 *ESTADÍSTICAS GENERALES*\n\n"
            stats_text += f"🔍 *Búsquedas activas:* {len(searches)}\n"
            stats_text += f"📦 *Total productos encontrados:* {general_stats['total_items']}\n"
            stats_text += f"🆕 *Productos en últimas 24h:* {recent_activity}\n"
            stats_text += f"👥 *Vendedores únicos:* {general_stats['unique_sellers']}\n\n"
            
            if general_stats['total_items'] > 0:
                stats_text += f"💰 *ANÁLISIS DE PRECIOS*\n"
                stats_text += f"📉 *Precio mínimo:* {locale.currency(general_stats['min_price'], grouping=True)}\n"
                stats_text += f"📈 *Precio máximo:* {locale.currency(general_stats['max_price'], grouping=True)}\n"
                stats_text += f"📊 *Precio promedio:* {locale.currency(general_stats['avg_price'], grouping=True)}\n\n"
            
            if search_activity:
                stats_text += f"🏆 *TOP BÚSQUEDAS*\n"
                top_searches = sorted(search_activity, key=lambda x: x['items_found'], reverse=True)[:3]
                
                for i, search in enumerate(top_searches, 1):
                    if search['items_found'] > 0:
                        stats_text += f"{i}. *{search['search_term']}*\n"
                        stats_text += f"   📦 {search['items_found']} productos"
                        if search['price_drops'] > 0:
                            stats_text += f" | 📉 {search['price_drops']} bajadas"
                        stats_text += f"\n"
                stats_text += f"\n"
            
            # Recrear botones
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            for search in search_activity[:5]:
                if search['items_found'] > 0:
                    search_btn = types.InlineKeyboardButton(
                        f"📊 {search['search_term']} ({search['items_found']} items)",
                        callback_data=f"stats_{search['search_term']}"
                    )
                    keyboard.add(search_btn)
            
            refresh_btn = types.InlineKeyboardButton("🔄 Actualizar estadísticas", callback_data="refresh_stats")
            keyboard.add(refresh_btn)
            
            if general_stats['total_items'] > 0:
                best_deals_btn = types.InlineKeyboardButton("💎 Ver mejores ofertas", callback_data="best_deals")
                keyboard.add(best_deals_btn)
            
            bot.answer_callback_query(call.id, "🔄 Estadísticas actualizadas")
            bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, 
                                 parse_mode='Markdown', reply_markup=keyboard)
        
        elif call.data == "best_deals":
            # Mostrar mejores ofertas globales
            items = db.get_items_by_search(call.message.chat.id, "")
            
            if not items:
                bot.answer_callback_query(call.id, "❌ No hay productos disponibles")
                return
            
            # Ordenar por precio (más baratos primero)
            best_items = sorted([item for item in items if item['price'] > 0], 
                               key=lambda x: x['price'])[:10]
            
            deals_text = f"💎 *MEJORES OFERTAS*\n\n"
            deals_text += f"🏆 *Top {len(best_items)} productos más baratos:*\n\n"
            
            for i, item in enumerate(best_items, 1):
                deals_text += f"{i}. *{item['title'][:40]}{'...' if len(item['title']) > 40 else ''}*\n"
                deals_text += f"💰 {locale.currency(item['price'], grouping=True)}"
                if item['price_changes']:
                    deals_text += " 📉 ¡Precio bajó!"
                deals_text += f"\n🔗 /item_{item['id']}\n\n"
            
            # Botón para volver
            back_keyboard = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("◀️ Volver a estadísticas", callback_data="refresh_stats")
            back_keyboard.add(back_btn)
            
            bot.answer_callback_query(call.id, "💎 Mejores ofertas")
            bot.edit_message_text(deals_text, call.message.chat.id, call.message.message_id, 
                                 parse_mode='Markdown', reply_markup=back_keyboard)
    
    except Exception as e:
        logging.error(f"Error en callback_query: {e}")
        bot.answer_callback_query(call.id, "❌ Error al procesar la acción")


# /add búsqueda,min-max,categorías separadas por comas
@bot.message_handler(commands=['add', 'añadir', 'append', 'a'])
def add_search(message):
    parametros = str(message.text).split(' ', 1)
    
    if len(parametros) < 2:
        bot.send_message(message.chat.id, 
                        "❌ *Error:* Debes especificar qué buscar\n\n"
                        "💡 *Formato:* `/add producto,precio_min-precio_max`\n\n"
                        "🌟 *Ejemplos:*\n"
                        "• `/add iPhone 13,200-400`\n"
                        "• `/add bicicleta,50-150`\n"
                        "• `/add zapatos nike` (sin límite de precio)", 
                        parse_mode='Markdown')
        return
    
    token = ' '.join(parametros[1:]).split(',')
    
    if len(token) < 1 or not token[0].strip():
        bot.send_message(message.chat.id, 
                        "❌ *Error:* El término de búsqueda no puede estar vacío\n\n"
                        "💡 *Ejemplo:* `/add iPhone 13,200-400`", 
                        parse_mode='Markdown')
        return
    
    # Verificar si ya existe esta búsqueda
    search_term = token[0].strip()
    existing_searches = db.get_chat_searchs(message.chat.id)
    
    if any(search.kws.lower() == search_term.lower() for search in existing_searches):
        bot.send_message(message.chat.id, 
                        f"⚠️ *Ya existe:* Ya tienes una búsqueda para '{search_term}'\n\n"
                        f"📋 Usa `/lis` para ver todas tus búsquedas", 
                        parse_mode='Markdown')
        return
    
    cs = ChatSearch()
    cs.chat_id = message.chat.id
    cs.kws = search_term
    
    # Procesar rango de precios
    if len(token) > 1 and token[1].strip():
        try:
            rango = token[1].strip().split('-')
            if rango[0].strip():
                # Validar que es un número
                min_price = float(rango[0].strip())
                if min_price < 0:
                    raise ValueError("Precio mínimo no puede ser negativo")
                cs.min_price = str(int(min_price))
            
            if len(rango) > 1 and rango[1].strip():
                max_price = float(rango[1].strip())
                if max_price < 0:
                    raise ValueError("Precio máximo no puede ser negativo")
                if cs.min_price and max_price < float(cs.min_price):
                    raise ValueError("Precio máximo debe ser mayor que el mínimo")
                cs.max_price = str(int(max_price))
                
        except ValueError as e:
            bot.send_message(message.chat.id, 
                            f"❌ *Error en precios:* Formato incorrecto\n\n"
                            f"💡 *Formato correcto:* `producto,min-max`\n"
                            f"🌟 *Ejemplo:* `/add iPhone,200-400`", 
                            parse_mode='Markdown')
            return
    
    # Procesar categorías
    if len(token) > 2:
        cs.cat_ids = sub('[\s+]', '', ','.join(token[2:]))
        if len(cs.cat_ids) == 0:
            cs.cat_ids = None
    
    cs.username = message.from_user.username
    cs.name = message.from_user.first_name
    cs.active = 1
    
    try:
        db.add_search(cs)
        
        # Mensaje de confirmación
        confirm_text = f"✅ *Búsqueda añadida:* '{cs.kws}'\n\n"
        
        if cs.min_price or cs.max_price:
            confirm_text += f"💰 *Rango de precio:* "
            if cs.min_price:
                confirm_text += f"{cs.min_price}€"
            else:
                confirm_text += "0€"
            confirm_text += " - "
            if cs.max_price:
                confirm_text += f"{cs.max_price}€"
            else:
                confirm_text += "∞"
            confirm_text += "\n\n"
        
        confirm_text += ("🔍 *Empezaré a buscar en Wallapop cada 5 minutos*\n"
                        "📱 Te notificaré cuando encuentre productos nuevos\n"
                        "💡 Usa `/lis` para ver todas tus búsquedas")
        
        bot.send_message(message.chat.id, confirm_text, parse_mode='Markdown')
        
        logging.info('Nueva búsqueda añadida: %s', cs)
        
    except Exception as e:
        logging.error(f"Error añadiendo búsqueda: {e}")
        bot.send_message(message.chat.id, 
                        "❌ *Error:* No se pudo añadir la búsqueda\n"
                        "🔄 Inténtalo de nuevo", 
                        parse_mode='Markdown')


# Manejador para mensajes no reconocidos
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    if message.text.startswith('/'):
        # Es un comando no reconocido
        bot.send_message(message.chat.id, 
                        f"❓ *Comando no reconocido:* `{message.text}`\n\n"
                        f"🤖 *Comandos disponibles:*\n"
                        f"• `/help` - Ver ayuda completa\n"
                        f"• `/add` - Añadir búsqueda\n"
                        f"• `/lis` - Ver búsquedas\n"
                        f"• `/stats` - Ver estadísticas\n"
                        f"• `/del` - Eliminar búsqueda\n\n"
                        f"💡 Usa `/help` para ver ejemplos detallados", 
                        parse_mode='Markdown')
    else:
        # Es un mensaje de texto normal
        bot.send_message(message.chat.id, 
                        "🤖 *¡Hola!* Soy tu asistente de Wallapop\n\n"
                        "📝 Para empezar, añade una búsqueda:\n"
                        "`/add producto,precio_min-precio_max`\n\n"
                        "❓ Usa `/help` para ver todos los comandos", 
                        parse_mode='Markdown')

pathlog = 'wallbot.log'
if PROFILE is None:
    pathlog = '/logs/' + pathlog

logging.basicConfig(
    handlers=[RotatingFileHandler(pathlog, maxBytes=1000000, backupCount=10)],
#    filename='wallbot.log',
    level=logging.INFO,
    format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')

locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')

#logger = telebot.logger
#formatter = logging.Formatter('[%(asctime)s] %(thread)d {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
#                              '%m-%d %H:%M:%S')
#ch = logging.StreamHandler(sys.stdout)
#logger.addHandler(ch)
#logger.setLevel(logging.INFO)  # or use logging.INFO
#ch.setFormatter(formatter)


# FIN

def wallapop():
    while True:
        # Recupera de db las búsquedas que hay que hacer en wallapop con sus respectivos chats_id
        for search in db.get_chats_searchs():
            u = get_url_list(search)

            # Lanza las búsquedas y notificaciones ...
            get_items(u, search.chat_id)

        # Borrar items antiguos (> 24hrs?)
        # No parece buena idea. Vuelven a entrar cada 5min algunos
        # db.deleteItems(24)

        time.sleep(300)
        continue


def recovery(times):
    try:
        time.sleep(times)
        logging.info("Conexión a Telegram.")
        print("Conexión a Telegram")
        bot.polling(none_stop=True, timeout=3000)
    except Exception as e:
        logging.error("Ha ocurrido un error con la llamada a Telegram. Se reintenta la conexión", e)
        print("Ha ocurrido un error con la llamada a Telegram. Se reintenta la conexión")
        if times > 16:
            times = 16
        recovery(times*2)


def main():
    print("JanJanJan starting...")
    logging.info("JanJanJan starting...")
    db.setup(readVersion())
    threading.Thread(target=wallapop).start()
    recovery(1)


def readVersion():
    file = open("VERSION", "r")
    version = file.readline()
    logging.info("Version %s", version)
    return version


if __name__ == '__main__':
    main()
