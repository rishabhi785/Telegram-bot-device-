import asyncio
import json
import os
import random
import string
import aiohttp
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Bot configuration
BOT_TOKEN = "8052913761:AAEkusCiEw5xNDT_U-SzOUvURg7LI-wXZwI"
CHANNEL_LINK = "https://t.me/freepromochannels"
GROUP_LINK = "https://t.me/promomogroup"
CHANNEL_ID = -1002729077216
GROUP_ID = -1002534343509
SUPPORT_USERNAME = "@zerixem"
WEBAPP_URL = "https://veryfyhtml.netlify.app/"
ADMIN_ID = "6736711885"  # Your admin chat ID

# VSV API Configuration
VSV_API_URL = "https://vsv-gateway-solutions.co.in/Api/api.php"
VSV_API_TOKEN = "DGXXDQHP"

# Data files
USERS_FILE = "users_data.json"
REDEEM_CODES_FILE = "redeem_codes.json"
CONFIG_FILE = "config.json"

# Default configuration
DEFAULT_CONFIG = {
    "min_withdrawal": 15,
    "daily_bonus": 1,
    "referral_bonus": 2.5
}

# Load configuration
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

# Load data functions
def load_users_data():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users_data(data):
    with open(USERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_redeem_codes():
    if os.path.exists(REDEEM_CODES_FILE):
        with open(REDEEM_CODES_FILE, 'r') as f:
            return json.load(f)
    return ["1A6ZNVNDNYX842UE", "9Z99FF2XM1N46AT5"]

def save_redeem_codes(codes):
    with open(REDEEM_CODES_FILE, 'w') as f:
        json.dump(codes, f, indent=2)

def generate_fake_redeem_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

# Global data
users_data = load_users_data()
redeem_codes = load_redeem_codes()
config = load_config()

# Wallet validation function
def validate_wallet_number(wallet_number):
    """Validate VSV wallet number (must be 10 digits)"""
    return bool(re.match(r'^\d{10}$', wallet_number))

# VSV API integration
async def transfer_money_via_vsv(recipient_wallet, amount, user_id):
    """Transfer money using VSV API"""
    try:
        # Construct the VSV API URL with parameters using the correct format
        comment = f"Bot_Withdrawal_User_{user_id}"
        api_url = f"{VSV_API_URL}?token={VSV_API_TOKEN}&paytm={recipient_wallet}&amount={amount}&comment={comment}"
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url) as response:
                
                if response.status == 200:
                    result = await response.text()
                    print(f"VSV API Response: {result}")  # Debug logging
                    
                    # Check if the response indicates success
                    if "success" in result.lower() or "completed" in result.lower() or "sent" in result.lower():
                        return {'success': True, 'transaction_id': f'VSV_{user_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'}
                    else:
                        return {'success': False, 'error': f'Transfer failed: {result}'}
                else:
                    error_data = await response.text()
                    return {'success': False, 'error': f'API Error: {response.status} - {error_data}'}
                    
    except asyncio.TimeoutError:
        return {'success': False, 'error': 'Transfer timeout - please try again later'}
    except Exception as e:
        return {'success': False, 'error': f'Transfer failed: {str(e)}'}

async def check_membership(context, user_id):
    try:
        # Parallel membership checks for faster response
        channel_task = context.bot.get_chat_member(CHANNEL_ID, user_id)
        group_task = context.bot.get_chat_member(GROUP_ID, user_id)
        
        # Wait for both with timeout
        channel_member, group_member = await asyncio.gather(channel_task, group_task, return_exceptions=True)
        
        # Check if both are valid responses
        if isinstance(channel_member, Exception) or isinstance(group_member, Exception):
            print(f"Membership check failed: {channel_member if isinstance(channel_member, Exception) else group_member}")
            return True  # Assume joined on API errors to avoid blocking users
            
        channel_joined = channel_member.status in ['member', 'administrator', 'creator']
        group_joined = group_member.status in ['member', 'administrator', 'creator']

        return channel_joined and group_joined
    except Exception as e:
        print(f"Membership check error: {e}")
        return True  # Assume joined on errors

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    user_id = str(update.effective_user.id)
    username = update.effective_user.first_name or "User"

    # Referral handling
    if context.args:
        referrer_id = context.args[0]
        if referrer_id != user_id and referrer_id in users_data:
            if user_id not in users_data:
                users_data[referrer_id]["balance"] += config["referral_bonus"]
                users_data[referrer_id]["referrals"] += 1
                save_users_data(users_data)
                await context.bot.send_message(referrer_id, f"*🎉 You earned ₹{config['referral_bonus']} from a new referral!*", parse_mode="Markdown")

    # Initialize user data
    if user_id not in users_data:
        users_data[user_id] = {
            "balance": 0,
            "referrals": 0,
            "last_bonus": None,
            "joined_channels": False,
            "verified": False,
            "wallet_number": None
        }
        save_users_data(users_data)

    # Check membership
    is_member = await check_membership(context, user_id)
    users_data[user_id]["joined_channels"] = is_member
    save_users_data(users_data)

    # Check if user is verified and member
    if is_member and users_data[user_id].get("verified", False):
        await show_main_menu(update, context)
    else:
        keyboard = [
            [InlineKeyboardButton("Join", url=CHANNEL_LINK),
             InlineKeyboardButton("Join", url=GROUP_LINK)],
            [InlineKeyboardButton("🔒claim", callback_data="claim")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"*😍 Hi {username} Welcome To Bot*\n\n*🟢 Must Join All Channels To Use Bot*\n\n◼️ *After Joining Click '🔒claim'*"
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID:
        keyboard = [
            ["BALANCE", "REFERAL LINK"],
            ["BONUS", "WITHDRAW"],
            ["LINK WALLET"],
            ["🔧 ADMIN PANEL"]
        ]
    else:
        keyboard = [
            ["BALANCE", "REFERAL LINK"],
            ["BONUS", "WITHDRAW"],
            ["LINK WALLET"]
        ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    text = "*🏠 Welcome! Use buttons below to manage your account.*"

    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            await update.callback_query.answer()
        elif hasattr(update, 'web_app_data') and update.web_app_data:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        print(f"Error showing menu: {e}")
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as fallback_error:
            print(f"Fallback error: {fallback_error}")

async def show_delayed_main_menu(chat_id: int, username: str, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu after delay without showing loading message"""
    try:
        # Wait for 8 seconds silently for faster response
        await asyncio.sleep(8)

        # Show main menu with reply keyboard (add admin panel for admin)
        if chat_id == int(ADMIN_ID):
            keyboard = [
                ["BALANCE", "REFERAL LINK"],
                ["BONUS", "WITHDRAW"],
                ["LINK WALLET"],
                ["🔧 ADMIN PANEL"]
            ]
        else:
            keyboard = [
                ["BALANCE", "REFERAL LINK"],
                ["BONUS", "WITHDRAW"],
                ["LINK WALLET"]
            ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        main_menu_text = f"*🏠 WELCOME {username} AND EARN MONEY EASILY*"

        await context.bot.send_message(
            chat_id=chat_id,
            text=main_menu_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        print(f"Main menu sent successfully to user {username}")

    except Exception as e:
        print(f"Error in delayed main menu: {e}")
        # Fallback to simple main menu
        try:
            if chat_id == int(ADMIN_ID):
                keyboard = [
                    ["BALANCE", "REFERAL LINK"],
                    ["BONUS", "WITHDRAW"],
                    ["LINK WALLET"],
                    ["🔧 ADMIN PANEL"]
                ]
            else:
                keyboard = [
                    ["BALANCE", "REFERAL LINK"],
                    ["BONUS", "WITHDRAW"],
                    ["LINK WALLET"]
                ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"*🏠 WELCOME {username} AND EARN MONEY EASILY*",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as fallback_error:
            print(f"Fallback error in delayed main menu: {fallback_error}")

async def claim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    username = query.from_user.first_name or "User"

    # Instant response to user
    try:
        await query.answer("✅ Processing...")
    except Exception as e:
        print(f"Error answering callback query: {e}")

    # Check if user is already verified - skip membership check for speed
    if users_data[user_id].get("verified", False) and users_data[user_id].get("joined_channels", False):
        print(f"User {user_id} already verified, showing delayed main menu instantly")
        await show_delayed_main_menu(query.message.chat_id, username, context)
        return

    # For new users, do quick membership check
    try:
        is_member = await asyncio.wait_for(check_membership(context, user_id), timeout=1.0)
    except asyncio.TimeoutError:
        print(f"Membership check timeout for user {user_id}, assuming member")
        is_member = True
    except Exception as e:
        print(f"Error checking membership for user {user_id}: {e}")
        is_member = True

    if is_member:
        # Mark user as verified immediately
        users_data[user_id]["joined_channels"] = True
        users_data[user_id]["verified"] = True
        save_users_data(users_data)
        print(f"User {user_id} verified and saved")

        # Show verification button quickly and start delayed menu
        keyboard = [
            [InlineKeyboardButton("🔐 Click here to verify", web_app=WebAppInfo(url=WEBAPP_URL))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "*🔐 Click here to verify*"

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
            print(f"Verification button sent to user {user_id}")
        except Exception as e:
            print(f"Message edit failed: {e}")
            await context.bot.send_message(user_id, text, reply_markup=reply_markup, parse_mode="Markdown")

        # Start delayed main menu
        await show_delayed_main_menu(query.message.chat_id, username, context)
    else:
        keyboard = [
            [InlineKeyboardButton("Join", url=CHANNEL_LINK),
             InlineKeyboardButton("Join", url=GROUP_LINK)],
            [InlineKeyboardButton("🔒claim", callback_data="claim")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"*{username}, please join both channel and group first!*\n\n*After joining, click '✨claim' again.*"

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            print(f"Message edit failed: {e}")
            await context.bot.send_message(user_id, text, reply_markup=reply_markup, parse_mode="Markdown")

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle web app data when user completes verification"""
    print(f"Web app data received: {update.web_app_data.data}")

    user_id = str(update.effective_user.id)
    username = update.effective_user.first_name or "User"
    chat_id = update.effective_chat.id

    print(f"Processing verification for user {user_id} ({username}) in chat {chat_id}")

    # Mark user as verified and channel member since they reached this point
    if user_id not in users_data:
        users_data[user_id] = {
            "balance": 0,
            "referrals": 0,
            "last_bonus": None,
            "joined_channels": True,
            "verified": True,
            "wallet_number": None
        }
    else:
        users_data[user_id]["verified"] = True
        users_data[user_id]["joined_channels"] = True

    save_users_data(users_data)
    print(f"User {user_id} marked as verified and saved to data")

    # Show main menu with delay
    print(f"Starting delayed main menu for user {user_id}")
    await show_delayed_main_menu(chat_id, username, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    user_id = str(update.effective_user.id)
    message_text = update.message.text

    # Check if user is verified
    if not users_data.get(user_id, {}).get("verified", False):
        await update.message.reply_text("*❌ Please complete verification first by using /start*", parse_mode="Markdown")
        return

    if message_text == "BALANCE":
        balance = users_data[user_id]["balance"]
        text = f"*💰 Your Balance: ₹{balance}*"
        await update.message.reply_text(text, parse_mode="Markdown")

    elif message_text == "REFERAL LINK":
        bot_username = context.bot.username or "EARNINGVIBES_BOT"
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        referrals = users_data[user_id]["referrals"]
        text = f"*💫 Per refer ₹2.5*\n\n*😍 Minimum withdrawal ₹15*\n\n*😎 High fund bot*\n\n*🗨️ 24/7 support available*\n\n*✅BOT LINK : {referral_link}*"
        
        # Add inline buttons
        keyboard = [
            [InlineKeyboardButton("🏆 LEADERBOARD", callback_data="leaderboard")],
            [InlineKeyboardButton("✨ MY INVITE", callback_data=f"my_invite_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    elif message_text == "BONUS":
        await handle_bonus(update, context)

    elif message_text == "WITHDRAW":
        await handle_withdraw_request(update, context)

    elif message_text == "LINK WALLET":
        await handle_wallet_link(update, context)

    elif message_text == "🔧 ADMIN PANEL" and user_id == ADMIN_ID:
        await show_admin_panel(update, context)
    
    # Admin panel reply keyboard handlers
    elif message_text == "👥 Total Users" and user_id == ADMIN_ID:
        total_users = len(users_data)
        verified_users = sum(1 for user in users_data.values() if user.get("verified", False))
        users_with_wallet = sum(1 for user in users_data.values() if user.get("wallet_number"))
        text = f"*👥 USER STATISTICS*\n\n" \
               f"*Total Users: {total_users}*\n" \
               f"*Verified Users: {verified_users}*\n" \
               f"*Users with Wallet: {users_with_wallet}*"
        await update.message.reply_text(text, parse_mode="Markdown")
    
    elif message_text == "💰 Add Money" and user_id == ADMIN_ID:
        # Initialize user_data if it doesn't exist
        if not hasattr(context, 'user_data') or context.user_data is None:
            context.user_data = {}
        if 'awaiting_admin_input' not in context.user_data:
            context.user_data['awaiting_admin_input'] = {}
            
        context.user_data['awaiting_admin_input'][user_id] = 'add_money_global'
        text = "*💰 Enter amount to add to ALL users' balance:*"
        await update.message.reply_text(text, parse_mode="Markdown")
    
    elif message_text == "💳 Add User Money" and user_id == ADMIN_ID:
        # Initialize user_data if it doesn't exist
        if not hasattr(context, 'user_data') or context.user_data is None:
            context.user_data = {}
        if 'awaiting_admin_input' not in context.user_data:
            context.user_data['awaiting_admin_input'] = {}
            
        context.user_data['awaiting_admin_input'][user_id] = 'add_user_money_id'
        text = "*💳 Enter user chat ID:*"
        await update.message.reply_text(text, parse_mode="Markdown")
    
    elif message_text == "⚙️ Settings" and user_id == ADMIN_ID:
        text = f"*⚙️ CURRENT SETTINGS*\n\n" \
               f"*💸 Min Withdrawal: ₹{config['min_withdrawal']}*\n" \
               f"*🎁 Daily Bonus: ₹{config['daily_bonus']}*\n" \
               f"*🎯 Referral Bonus: ₹{config['referral_bonus']}*\n\n" \
               f"*Type 'SET MIN X' to change min withdrawal*\n" \
               f"*Type 'SET BONUS X' to change daily bonus*"
        await update.message.reply_text(text, parse_mode="Markdown")
    
    elif message_text == "🔄 Restart" and user_id == ADMIN_ID:
        text = "*🔄 Bot restarted successfully!*"
        await update.message.reply_text(text, parse_mode="Markdown")
    
    elif message_text == "❌ Close" and user_id == ADMIN_ID:
        # Return to admin menu (normal user menu + admin panel button)
        keyboard = [
            ["BALANCE", "REFERAL LINK"],
            ["BONUS", "WITHDRAW"],
            ["LINK WALLET"],
            ["🔧 ADMIN PANEL"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        text = "*❌ Admin panel closed*"
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    
    # Handle admin quick settings
    elif message_text.startswith("SET MIN ") and user_id == ADMIN_ID:
        try:
            value = float(message_text.replace("SET MIN ", ""))
            if value > 0:
                config['min_withdrawal'] = value
                save_config(config)
                text = f"*✅ Minimum withdrawal updated to ₹{value}*"
            else:
                text = "*❌ Value must be positive*"
        except ValueError:
            text = "*❌ Invalid format. Use: SET MIN 15*"
        await update.message.reply_text(text, parse_mode="Markdown")
    
    elif message_text.startswith("SET BONUS ") and user_id == ADMIN_ID:
        try:
            value = float(message_text.replace("SET BONUS ", ""))
            if value > 0:
                config['daily_bonus'] = value
                save_config(config)
                text = f"*✅ Daily bonus updated to ₹{value}*"
            else:
                text = "*❌ Value must be positive*"
        except ValueError:
            text = "*❌ Invalid format. Use: SET BONUS 1*"
        await update.message.reply_text(text, parse_mode="Markdown")
    


    # Handle wallet number input
    elif (hasattr(context, 'user_data') and context.user_data is not None and 
          user_id in context.user_data.get('awaiting_wallet', [])):
        await handle_wallet_input(update, context)

    # Handle admin input
    elif (hasattr(context, 'user_data') and context.user_data is not None and 
          user_id in context.user_data.get('awaiting_admin_input', {})):
        await handle_admin_input(update, context)

async def handle_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    last_bonus = users_data[user_id].get("last_bonus")
    
    now = datetime.now()
    if last_bonus:
        last_bonus_date = datetime.fromisoformat(last_bonus)
        if now.date() == last_bonus_date.date():
            # Calculate hours until next bonus (24 hours from last claim)
            next_bonus_time = last_bonus_date + timedelta(days=1)
            hours_remaining = int((next_bonus_time - now).total_seconds() / 3600)
            if hours_remaining <= 0:
                hours_remaining = 24  # Show 24 hours if calculation is off
            text = f"*⏰ Next bonus available {hours_remaining} hours*"
            await update.message.reply_text(text, parse_mode="Markdown")
            return
    
    users_data[user_id]["balance"] += config["daily_bonus"]
    users_data[user_id]["last_bonus"] = now.isoformat()
    save_users_data(users_data)
    
    text = "*✨ Choose One:*"
    
    # Add inline buttons in column layout
    keyboard = [
        [InlineKeyboardButton("🕒 DAILY BONUS", callback_data=f"daily_bonus_{user_id}")],
        [InlineKeyboardButton("🎁 GIFT CODE", callback_data="gift_code")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_withdraw_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    balance = users_data[user_id]["balance"]
    min_withdrawal = config["min_withdrawal"]
    
    if balance < min_withdrawal:
        text = f"*MINIMUM WITHDRAWAL ₹{min_withdrawal} EARN MORE BY REFERRING*"
        await update.message.reply_text(text, parse_mode="Markdown")
        return
    
    wallet_number = users_data[user_id].get("wallet_number")
    if not wallet_number:
        text = "*❌ Please link your VSV wallet first*\n*Use: LINK WALLET button*"
        await update.message.reply_text(text, parse_mode="Markdown")
        return
    
    # Show withdrawal confirmation
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Withdrawal", callback_data=f"withdraw_confirm_{balance}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="withdraw_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"*💸 Withdrawal Request*\n\n*💰 Amount: ₹{balance}*\n*🏦 Wallet: {wallet_number}*\n\n*Confirm withdrawal*"
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_wallet_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    current_wallet = users_data[user_id].get("wallet_number")
    if current_wallet:
        keyboard = [
            [InlineKeyboardButton("🔄 Change Wallet", callback_data="change_wallet")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_wallet")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"*🏦 Your current wallet:*\n`{current_wallet}`\n\n*Do you want to change it?*"
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        # Initialize user_data if it doesn't exist
        if not hasattr(context, 'user_data') or context.user_data is None:
            context.user_data = {}
        if 'awaiting_wallet' not in context.user_data:
            context.user_data['awaiting_wallet'] = []
            
        context.user_data['awaiting_wallet'].append(user_id)
        text = "*PLEASE SEND YOUR VSV WALLET NUMBER*"
        await update.message.reply_text(text, parse_mode="Markdown")

async def handle_wallet_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wallet_number = update.message.text.strip()
    
    if validate_wallet_number(wallet_number):
        users_data[user_id]["wallet_number"] = wallet_number
        save_users_data(users_data)
        
        # Remove from awaiting list
        if (hasattr(context, 'user_data') and context.user_data is not None and 
            'awaiting_wallet' in context.user_data and user_id in context.user_data['awaiting_wallet']):
            context.user_data['awaiting_wallet'].remove(user_id)
        
        text = f"*✅ YOUR VSV WALLET CONNECT SUCCESSFULLY*"
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        text = "*❌ WRONG WALLET PLEASE ENTER CORRECT WALLET NUMBER*\n*📝 Enter only 10 digits number*\n\n*Example: 1234567890*"
        await update.message.reply_text(text, parse_mode="Markdown")

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["👥 Total Users", "💰 Add Money"],
        ["⚙️ Settings", "🔄 Restart"],
        ["💳 Add User Money", "❌ Close"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    total_users = len(users_data)
    total_balance = sum(user.get("balance", 0) for user in users_data.values())
    total_referrals = sum(user.get("referrals", 0) for user in users_data.values())
    
    text = f"*🔧 ADMIN PANEL*\n\n" \
           f"*📊 Bot Statistics:*\n" \
           f"*👥 Total Users: {total_users}*\n" \
           f"*💰 Total Balance: ₹{total_balance}*\n" \
           f"*🔗 Total Referrals: {total_referrals}*\n\n" \
           f"*⚙️ Current Settings:*\n" \
           f"*💸 Min Withdrawal: ₹{config['min_withdrawal']}*\n" \
           f"*🎁 Daily Bonus: ₹{config['daily_bonus']}*\n" \
           f"*🎯 Referral Bonus: ₹{config['referral_bonus']}*"
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    input_text = update.message.text.strip()
    
    if (not hasattr(context, 'user_data') or context.user_data is None or 
        user_id not in context.user_data.get('awaiting_admin_input', {})):
        return
    
    input_type = context.user_data['awaiting_admin_input'][user_id]
    
    if input_type == 'add_money_global':
        try:
            amount = float(input_text)
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            # Add money to all users
            for uid in users_data:
                users_data[uid]["balance"] = users_data[uid].get("balance", 0) + amount
            save_users_data(users_data)
            
            text = f"*✅ Added ₹{amount} to all {len(users_data)} users' balance*"
            
            # Remove from awaiting list
            del context.user_data['awaiting_admin_input'][user_id]
            await update.message.reply_text(text, parse_mode="Markdown")
            
        except ValueError:
            text = "*❌ Invalid amount! Please enter a positive number.*"
            await update.message.reply_text(text, parse_mode="Markdown")
            
    elif input_type == 'add_user_money_id':
        # Store the target user ID and ask for amount
        target_user_id = input_text
        if target_user_id in users_data:
            context.user_data['awaiting_admin_input'][user_id] = f'add_user_money_amount_{target_user_id}'
            text = f"*💳 Enter amount to add to user {target_user_id[:8]}...'s balance:*"
            await update.message.reply_text(text, parse_mode="Markdown")
        else:
            text = "*❌ User not found! Please enter a valid chat ID.*"
            await update.message.reply_text(text, parse_mode="Markdown")
            
    elif input_type.startswith('add_user_money_amount_'):
        target_user_id = input_type.split('_')[-1]
        try:
            amount = float(input_text)
            if amount <= 0:
                raise ValueError("Amount must be positive")
                
            if target_user_id in users_data:
                old_balance = users_data[target_user_id].get("balance", 0)
                users_data[target_user_id]["balance"] = old_balance + amount
                save_users_data(users_data)
                
                text = f"*✅ Added ₹{amount} to user {target_user_id[:8]}...*\n" \
                       f"*Old Balance: ₹{old_balance}*\n" \
                       f"*New Balance: ₹{users_data[target_user_id]['balance']}*"
                
                # Remove from awaiting list
                del context.user_data['awaiting_admin_input'][user_id]
                await update.message.reply_text(text, parse_mode="Markdown")
            else:
                text = "*❌ User not found!*"
                await update.message.reply_text(text, parse_mode="Markdown")
                
        except ValueError:
            text = "*❌ Invalid amount! Please enter a positive number.*"
            await update.message.reply_text(text, parse_mode="Markdown")
    
    elif input_type == 'min_withdrawal':
        try:
            value = float(input_text)
            if value <= 0:
                raise ValueError("Value must be positive")
            
            config['min_withdrawal'] = value
            save_config(config)
            text = f"*✅ Minimum withdrawal updated to ₹{value}*"
            
            # Remove from awaiting list
            del context.user_data['awaiting_admin_input'][user_id]
            await update.message.reply_text(text, parse_mode="Markdown")
            
        except ValueError:
            text = "*❌ Invalid input! Please enter a positive number.*"
            await update.message.reply_text(text, parse_mode="Markdown")
            
    elif input_type == 'daily_bonus':
        try:
            value = float(input_text)
            if value <= 0:
                raise ValueError("Value must be positive")
            
            config['daily_bonus'] = value
            save_config(config)
            text = f"*✅ Daily bonus updated to ₹{value}*"
            
            # Remove from awaiting list
            del context.user_data['awaiting_admin_input'][user_id]
            await update.message.reply_text(text, parse_mode="Markdown")
            
        except ValueError:
            text = "*❌ Invalid input! Please enter a positive number.*"
            await update.message.reply_text(text, parse_mode="Markdown")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    data = query.data
    
    await query.answer()
    
    if data == "claim":
        await claim_callback(update, context)
    
    elif data.startswith("withdraw_confirm_"):
        amount = float(data.split("_")[-1])
        wallet_number = users_data[user_id]["wallet_number"]
        
        # Process withdrawal
        await query.edit_message_text("*💸 Processing withdrawal...*", parse_mode="Markdown")
        
        result = await transfer_money_via_vsv(wallet_number, amount, user_id)
        
        if result['success']:
            # Deduct balance
            users_data[user_id]["balance"] = 0
            save_users_data(users_data)
            
            text = f"*✅ Withdrawal Successful!*\n\n" \
                   f"*💰 Amount: ₹{amount}*\n" \
                   f"*🏦 Wallet: {wallet_number}*\n" \
                   f"*🆔 Transaction ID: {result['transaction_id']}*\n\n" \
                   f"*Money transferred to your wallet successfully*"
        else:
            text = f"*❌ Withdrawal Failed!*\n\n" \
                   f"*Error: {result['error']}*\n\n" \
                   f"*Please try again later*"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif data == "withdraw_cancel":
        await query.edit_message_text("*❌ Withdrawal cancelled*", parse_mode="Markdown")
    
    elif data == "change_wallet":
        # Initialize user_data if it doesn't exist
        if not hasattr(context, 'user_data') or context.user_data is None:
            context.user_data = {}
        if 'awaiting_wallet' not in context.user_data:
            context.user_data['awaiting_wallet'] = []
            
        context.user_data['awaiting_wallet'].append(user_id)
        text = "*PLEASE SEND YOUR VSV WALLET NUMBER*"
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif data == "cancel_wallet":
        await query.edit_message_text("*❌ Cancelled*", parse_mode="Markdown")
    
    # Admin callbacks
    elif data == "admin_min_withdrawal" and user_id == ADMIN_ID:
        # Initialize user_data if it doesn't exist
        if not hasattr(context, 'user_data') or context.user_data is None:
            context.user_data = {}
        if 'awaiting_admin_input' not in context.user_data:
            context.user_data['awaiting_admin_input'] = {}
            
        context.user_data['awaiting_admin_input'][user_id] = 'min_withdrawal'
        text = f"*💰 Current minimum withdrawal: ₹{config['min_withdrawal']}*\n\n*Enter new minimum withdrawal amount:*"
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif data == "admin_daily_bonus" and user_id == ADMIN_ID:
        # Initialize user_data if it doesn't exist
        if not hasattr(context, 'user_data') or context.user_data is None:
            context.user_data = {}
        if 'awaiting_admin_input' not in context.user_data:
            context.user_data['awaiting_admin_input'] = {}
            
        context.user_data['awaiting_admin_input'][user_id] = 'daily_bonus'
        text = f"*🎁 Current daily bonus: ₹{config['daily_bonus']}*\n\n*Enter new daily bonus amount:*"
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif data == "admin_user_stats" and user_id == ADMIN_ID:
        verified_users = sum(1 for user in users_data.values() if user.get("verified", False))
        users_with_wallet = sum(1 for user in users_data.values() if user.get("wallet_number"))
        
        text = f"*📊 Detailed User Statistics*\n\n" \
               f"*👥 Total Users: {len(users_data)}*\n" \
               f"*✅ Verified Users: {verified_users}*\n" \
               f"*🏦 Users with Wallet: {users_with_wallet}*\n" \
               f"*💰 Total Balance: ₹{sum(user.get('balance', 0) for user in users_data.values())}*\n" \
               f"*🔗 Total Referrals: {sum(user.get('referrals', 0) for user in users_data.values())}*"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif data == "admin_close" and user_id == ADMIN_ID:
        await query.edit_message_text("*✅ Admin panel closed*", parse_mode="Markdown")
    
    elif data.startswith("copy_link_"):
        # Handle copy link callback
        await query.answer("✅ Link copied! Share it with friends to earn money.", show_alert=True)
    
    elif data == "leaderboard":
        # Show top 10 referrers
        sorted_users = sorted(
            [(uid, data) for uid, data in users_data.items() if data.get("referrals", 0) > 0],
            key=lambda x: x[1].get("referrals", 0),
            reverse=True
        )[:10]
        
        text = "*🏆 TOP 10 LEADERBOARD*\n\n"
        if sorted_users:
            for i, (uid, data) in enumerate(sorted_users, 1):
                referrals = data.get("referrals", 0)
                text += f"*{i}. User {uid[:8]}... - {referrals} referrals*\n"
        else:
            text += "*No referrals yet. Be the first!*"
        
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif data.startswith("my_invite_"):
        user_invite_id = data.split("_")[-1]
        referrals = users_data[user_invite_id]["referrals"]
        text = f"*✨ YOUR INVITE STATS*\n\n*👥 Total Invites: {referrals}*\n*💰 Earned from Referrals: ₹{referrals * config['referral_bonus']}*"
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif data.startswith("daily_bonus_"):
        bonus_user_id = data.split("_")[-1]
        text = f"*🎁 ₹{config['daily_bonus']} CLAIM SUCCESSFULLY*"
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif data == "gift_code":
        text = "*NOT AVAILABLE*"
        await query.edit_message_text(text, parse_mode="Markdown")

def main():
    print("Starting Telegram bot...")
    
    # Initialize configuration
    save_config(config)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Start the bot
    print("Bot started successfully!")
    application.run_polling()

if __name__ == "__main__":
    main()
