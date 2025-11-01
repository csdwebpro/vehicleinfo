import telebot
import requests
import re
import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent

# Replace with your BOT_TOKEN
BOT_TOKEN = '8187555363:AAEKQmiZmVf6K-RthgEsZ97pdiG-c2YH_sI'
bot = telebot.TeleBot(BOT_TOKEN)

# SQLite setup for user history (simple DB)
conn = sqlite3.connect('vehicle_history.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS history (user_id INTEGER, vehicle TEXT, result TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

# Vehicle number validation (basic regex for Indian formats)
def validate_vehicle_num(vnum):
    pattern = r'^[A-Z]{2}[0-9]{1,2}[A-Z]{0,2}[0-9]{4}$'
    return re.match(pattern, vnum.upper())

# API function to get vehicle info
def get_vehicle_info(vehicle_num):
    url = f'https://vehicle-advanced-api.zerovault.workers.dev/?vno={vehicle_num}&key=test'
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if API returned success
            if data.get('status') == 'success' and data.get('data'):
                vehicle_data = data['data']
                
                # Format the response in a readable way
                result = []
                
                # Basic vehicle info
                if 'reg_no' in vehicle_data:
                    result.append(f"• Registration No: {vehicle_data['reg_no']}")
                if 'chassis_no' in vehicle_data:
                    result.append(f"• Chassis No: {vehicle_data['chassis_no']}")
                if 'engine_no' in vehicle_data:
                    result.append(f"• Engine No: {vehicle_data['engine_no']}")
                if 'owner_name' in vehicle_data:
                    result.append(f"• Owner Name: {vehicle_data['owner_name']}")
                if 'vehicle_class' in vehicle_data:
                    result.append(f"• Vehicle Class: {vehicle_data['vehicle_class']}")
                if 'fuel_type' in vehicle_data:
                    result.append(f"• Fuel Type: {vehicle_data['fuel_type']}")
                if 'maker_model' in vehicle_data:
                    result.append(f"• Maker/Model: {vehicle_data['maker_model']}")
                if 'fitness_upto' in vehicle_data:
                    result.append(f"• Fitness Valid Until: {vehicle_data['fitness_upto']}")
                if 'insurance_upto' in vehicle_data:
                    result.append(f"• Insurance Valid Until: {vehicle_data['insurance_upto']}")
                if 'registration_date' in vehicle_data:
                    result.append(f"• Registration Date: {vehicle_data['registration_date']}")
                if 'rc_status' in vehicle_data:
                    result.append(f"• RC Status: {vehicle_data['rc_status']}")
                
                if result:
                    return '\n'.join(result)
                else:
                    return "No vehicle data found in API response."
            else:
                return f"API Error: {data.get('message', 'Unknown error')}"
        else:
            return f"HTTP Error: {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        return f"Network error: {str(e)}"
    except ValueError as e:
        return f"Error parsing API response: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"

# Store in DB
def store_history(user_id, vehicle, result):
    cursor.execute("INSERT INTO history (user_id, vehicle, result) VALUES (?, ?, ?)", (user_id, vehicle, result))
    conn.commit()

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    welcome = "Welcome to Vehicle Info Bot! 🚗\n\nSend /lookup <vehicle_number> (e.g., /lookup DL01AB1234) or use inline mode: @yourbot DL01AB1234\n\nFeatures:\n• Instant lookups\n• Search history with /history\n• Valid formats: DL01AB1234, MH12DE5678"
    bot.reply_to(message, welcome)

# Help command
@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message, "Usage:\n• /lookup DL01AB1234\n• Inline: @VehicleInfoBot DL01AB1234\n• /history - Your recent searches")

# Lookup command
@bot.message_handler(commands=['lookup'])
def lookup(message):
    try:
        vehicle = message.text.split(maxsplit=1)[1].strip().upper()
    except IndexError:
        bot.reply_to(message, "Please provide a vehicle number: /lookup DL01AB1234")
        return
    
    if not validate_vehicle_num(vehicle):
        bot.reply_to(message, "Invalid format! Use e.g., DL01AB1234 (2 letters + 1-2 digits + 1-2 letters + 4 digits)")
        return
    
    bot.reply_to(message, "🔍 Fetching details...")
    result = get_vehicle_info(vehicle)
    store_history(message.from_user.id, vehicle, result)
    
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(InlineKeyboardButton("🔄 Retry", callback_data=f"retry_{vehicle}"),
               InlineKeyboardButton("📋 Copy", callback_data="copy"))
    bot.reply_to(message, f"**Vehicle: {vehicle}**\n\n{result}", reply_markup=markup, parse_mode='Markdown')

# History command
@bot.message_handler(commands=['history'])
def history(message):
    cursor.execute("SELECT vehicle, result FROM history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5", (message.from_user.id,))
    rows = cursor.fetchall()
    if not rows:
        bot.reply_to(message, "No searches yet. Start with /lookup!")
        return
    
    hist = "🚗 Recent Searches:\n\n"
    for i, (vehicle, result) in enumerate(rows, 1):
        # Extract first line of result for preview
        preview = result.split('\n')[0] if result else "No data"
        hist += f"{i}. {vehicle}: {preview[:40]}...\n\n"
    
    bot.reply_to(message, hist)

# Callback for buttons
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data.startswith('retry_'):
        vehicle = call.data.split('_')[1]
        result = get_vehicle_info(vehicle)
        store_history(call.from_user.id, vehicle, result)
        
        # Create updated keyboard
        markup = InlineKeyboardMarkup()
        markup.row_width = 2
        markup.add(InlineKeyboardButton("🔄 Retry", callback_data=f"retry_{vehicle}"),
                   InlineKeyboardButton("📋 Copy", callback_data="copy"))
        
        bot.edit_message_text(f"**Vehicle: {vehicle}**\n\n{result}", 
                             call.message.chat.id, 
                             call.message.id, 
                             reply_markup=markup,
                             parse_mode='Markdown')
    elif call.data == 'copy':
        bot.answer_callback_query(call.id, "Use the copy feature in your Telegram app to copy the vehicle details!")

# Inline query handler (advanced: quick search without commands)
@bot.inline_handler(func=lambda query: len(query.query) > 0)
def inline_query(query):
    vehicle = query.query.upper().strip()
    
    # Validate vehicle number format
    if not validate_vehicle_num(vehicle):
        return
    
    result = get_vehicle_info(vehicle)
    store_history(query.from_user.id, vehicle, result)
    
    # Create a preview description
    preview_lines = result.split('\n')[:3]  # Show first 3 lines as preview
    preview = ' | '.join([line.replace('•', '').strip() for line in preview_lines])
    
    input_content = InputTextMessageContent(
        f"**Vehicle: {vehicle}**\n\n{result}", 
        parse_mode='Markdown'
    )
    
    results = [InlineQueryResultArticle(
        id=vehicle,
        title=f"Vehicle Info: {vehicle}",
        description=preview[:100] + "..." if len(preview) > 100 else preview,
        input_message_content=input_content,
        thumb_url="https://cdn-icons-png.flaticon.com/512/744/744465.png"  # Car icon
    )]
    
    bot.answer_inline_query(query.id, results, cache_time=1)

# Error handler
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    bot.reply_to(message, "I don't understand that command. Use /lookup <vehicle_number> or /help for instructions.")

# Run the bot
if __name__ == '__main__':
    print("🚗 Vehicle Info Bot starting...")
    print("Bot is running with API integration!")
    bot.infinity_polling()
