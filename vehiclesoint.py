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

# Multiple API endpoints as fallback
def get_vehicle_info(vehicle_num):
    # Try multiple API endpoints and approaches
    apis_to_try = [
        # Try without API key first
        f'https://vehicle-advanced-api.zerovault.workers.dev/?vno={vehicle_num}',
        # Try with different parameter names
        f'https://vehicle-advanced-api.zerovault.workers.dev/?number={vehicle_num}',
        f'https://vehicle-advanced-api.zerovault.workers.dev/?registration={vehicle_num}',
        f'https://vehicle-advanced-api.zerovault.workers.dev/?vehicle={vehicle_num}',
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://zerovault.workers.dev/'
    }
    
    for api_url in apis_to_try:
        try:
            print(f"Trying API: {api_url}")  # Debug log
            response = requests.get(api_url, headers=headers, timeout=15)
            
            print(f"Response Status: {response.status_code}")  # Debug log
            
            if response.status_code == 200:
                data = response.json()
                print(f"API Response: {data}")  # Debug log
                
                # Handle different response formats
                if isinstance(data, dict):
                    if data.get('status') == 'success' and data.get('data'):
                        return format_vehicle_data(data['data'])
                    elif data.get('data'):
                        return format_vehicle_data(data['data'])
                    elif data.get('vehicle_info'):
                        return format_vehicle_data(data['vehicle_info'])
                    else:
                        # Return whatever data we got
                        return format_vehicle_data(data)
                elif isinstance(data, list) and len(data) > 0:
                    return format_vehicle_data(data[0])
                else:
                    return "Received data but in unexpected format"
                    
            elif response.status_code == 401:
                print("API returned 401 - Unauthorized")
                continue  # Try next API endpoint
            elif response.status_code == 404:
                print("API returned 404 - Not Found")
                continue
            else:
                print(f"API returned {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {api_url}: {e}")
            continue
        except ValueError as e:
            print(f"JSON parse error for {api_url}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error for {api_url}: {e}")
            continue
    
    # If all APIs fail, try web scraping as fallback
    return fallback_vehicle_lookup(vehicle_num)

def format_vehicle_data(vehicle_data):
    """Format vehicle data into readable string"""
    if not vehicle_data:
        return "No vehicle data found"
    
    result = []
    
    # Map possible field names to display names
    field_mapping = {
        'reg_no': 'Registration No',
        'registration_no': 'Registration No',
        'vehicle_number': 'Registration No',
        'number': 'Registration No',
        'chassis_no': 'Chassis No',
        'chassis_number': 'Chassis No',
        'engine_no': 'Engine No',
        'engine_number': 'Engine No',
        'owner_name': 'Owner Name',
        'owner': 'Owner Name',
        'vehicle_class': 'Vehicle Class',
        'class': 'Vehicle Class',
        'fuel_type': 'Fuel Type',
        'fuel': 'Fuel Type',
        'maker_model': 'Maker/Model',
        'model': 'Maker/Model',
        'manufacturer': 'Maker/Model',
        'fitness_upto': 'Fitness Valid Until',
        'fitness': 'Fitness Valid Until',
        'insurance_upto': 'Insurance Valid Until',
        'insurance': 'Insurance Valid Until',
        'registration_date': 'Registration Date',
        'reg_date': 'Registration Date',
        'rc_status': 'RC Status',
        'status': 'RC Status',
        'vehicle_type': 'Vehicle Type',
        'type': 'Vehicle Type',
        'state': 'State',
        'rto': 'RTO Office'
    }
    
    for field, display_name in field_mapping.items():
        if field in vehicle_data and vehicle_data[field]:
            result.append(f"• {display_name}: {vehicle_data[field]}")
    
    if not result:
        # If no mapped fields found, show all available fields
        for key, value in vehicle_data.items():
            if value and not key.startswith('_'):
                formatted_key = ' '.join(word.capitalize() for word in key.split('_'))
                result.append(f"• {formatted_key}: {value}")
    
    if result:
        return '\n'.join(result)
    else:
        return "Vehicle data received but no readable information found"

def fallback_vehicle_lookup(vehicle_num):
    """Fallback method using web scraping or alternative sources"""
    try:
        # Try government RTO sites (example - you'll need to adapt this)
        fallback_apis = [
            f"https://api.vehicledata.in/vehicle/{vehicle_num}",
            f"https://rto-vehicle-api.example.com/search?q={vehicle_num}",  # Placeholder
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for api_url in fallback_apis:
            try:
                response = requests.get(api_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return format_vehicle_data(data)
            except:
                continue
                
        return "❌ Unable to fetch vehicle details at the moment.\n\nPossible reasons:\n• Vehicle number not found\n• API service temporarily unavailable\n• Invalid vehicle number format\n\nPlease try again later or verify the vehicle number."
        
    except Exception as e:
        return f"❌ Service temporarily unavailable. Error: {str(e)}"

# Store in DB
def store_history(user_id, vehicle, result):
    cursor.execute("INSERT INTO history (user_id, vehicle, result) VALUES (?, ?, ?)", (user_id, vehicle, result))
    conn.commit()

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    welcome = """🚗 Welcome to Vehicle Info Bot!

🔍 Get vehicle information instantly!

**Commands:**
/lookup <vehicle_number> - Lookup vehicle details
/history - View your search history
/help - Show help message

**Examples:**
`/lookup DL01AB1234`
`/lookup MH12DE5678`

**Inline Mode:**
Type `@YourBotName DL01AB1234` in any chat!

**Supported Formats:**
• DL01AB1234
• MH12DE5678  
• KA05MN1234"""
    bot.reply_to(message, welcome, parse_mode='Markdown')

# Help command
@bot.message_handler(commands=['help'])
def help_cmd(message):
    help_text = """📖 **How to use this bot:**

**1. Direct Lookup:**
`/lookup DL01AB1234`

**2. Inline Mode:**
Type `@YourBotName DL01AB1234` in any chat

**3. View History:**
`/history` - See your last 5 searches

**Valid Vehicle Number Formats:**
• 2 letters (State code)
• 1-2 digits (RTO code)  
• 0-2 letters (Series)
• 4 digits (Number)

**Examples:** DL01AB1234, MH12DE5678, KA05MN1234"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

# Lookup command
@bot.message_handler(commands=['lookup'])
def lookup(message):
    try:
        vehicle = message.text.split(maxsplit=1)[1].strip().upper()
    except IndexError:
        bot.reply_to(message, "❌ Please provide a vehicle number:\n`/lookup DL01AB1234`", parse_mode='Markdown')
        return
    
    if not validate_vehicle_num(vehicle):
        bot.reply_to(message, "❌ Invalid vehicle number format!\n\nPlease use formats like:\n• `DL01AB1234`\n• `MH12DE5678`\n• `KA05MN1234`", parse_mode='Markdown')
        return
    
    # Send typing action
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Get vehicle info
    result = get_vehicle_info(vehicle)
    store_history(message.from_user.id, vehicle, result)
    
    # Create keyboard
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("🔄 Retry", callback_data=f"retry_{vehicle}"),
        InlineKeyboardButton("📋 Copy", callback_data=f"copy_{vehicle}")
    )
    
    # Send result
    bot.reply_to(message, f"**Vehicle: {vehicle}**\n\n{result}", reply_markup=markup, parse_mode='Markdown')

# History command
@bot.message_handler(commands=['history'])
def history(message):
    cursor.execute("SELECT vehicle, result FROM history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5", (message.from_user.id,))
    rows = cursor.fetchall()
    
    if not rows:
        bot.reply_to(message, "📝 No search history yet!\nUse `/lookup DL01AB1234` to get started!", parse_mode='Markdown')
        return
    
    hist = "📚 Your Recent Searches:\n\n"
    for i, (vehicle, result) in enumerate(rows, 1):
        preview = result.split('\n')[0] if result else "No data"
        hist += f"**{i}. {vehicle}**\n"
        hist += f"   {preview[:35]}...\n\n"
    
    bot.reply_to(message, hist, parse_mode='Markdown')

# Callback for buttons
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data.startswith('retry_'):
        vehicle = call.data.split('_')[1]
        
        # Show typing action
        bot.send_chat_action(call.message.chat.id, 'typing')
        
        result = get_vehicle_info(vehicle)
        store_history(call.from_user.id, vehicle, result)
        
        markup = InlineKeyboardMarkup()
        markup.row_width = 2
        markup.add(
            InlineKeyboardButton("🔄 Retry", callback_data=f"retry_{vehicle}"),
            InlineKeyboardButton("📋 Copy", callback_data=f"copy_{vehicle}")
        )
        
        bot.edit_message_text(
            f"**Vehicle: {vehicle}**\n\n{result}",
            call.message.chat.id,
            call.message.id,
            reply_markup=markup,
            parse_mode='Markdown'
        )
        
    elif call.data.startswith('copy_'):
        bot.answer_callback_query(call.id, "📋 Use the copy feature in Telegram to copy the details!")

# Inline query handler
@bot.inline_handler(func=lambda query: len(query.query) > 0)
def inline_query(query):
    vehicle = query.query.upper().strip()
    
    if not validate_vehicle_num(vehicle):
        return
    
    # Get vehicle info
    result = get_vehicle_info(vehicle)
    store_history(query.from_user.id, vehicle, result)
    
    # Create preview
    preview_lines = result.split('\n')[:2]
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
        thumb_url="https://cdn-icons-png.flaticon.com/512/744/744465.png"
    )]
    
    bot.answer_inline_query(query.id, results, cache_time=0)

# Handle other messages
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    bot.reply_to(message, "🤖 I'm a Vehicle Info Bot!\n\nUse `/lookup DL01AB1234` to get vehicle details or `/help` for more info.", parse_mode='Markdown')

# Run the bot
if __name__ == '__main__':
    print("🚗 Vehicle Info Bot starting...")
    print("✅ Bot is running with enhanced API handling!")
    bot.infinity_polling()
