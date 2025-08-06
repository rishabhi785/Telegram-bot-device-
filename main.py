import asyncio
import json
import os
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8494137415:AAFAQ2hTbJuBGRz5hSdvIGxj8tUtIdoWQ4k")
CHANNEL_LINK = "https://t.me/freepromochannels"
GROUP_LINK = "https://t.me/promomogroup"
CHANNEL_ID = -1002729077216
GROUP_ID = -1002534343509
SUPPORT_USERNAME = "@zerixem"
WEBAPP_URL = "https://veryfyhtml.netlify.app/"
ADMIN_ID = "6736711885"  # Your admin chat ID

# Data files
USERS_FILE = "users_data.json"
REDEEM_CODES_FILE = "redeem_codes.json"

# Load data
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

async def check_membership(context, user_id):
    try:
        # Parallel membership checks for faster response
        import asyncio
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
                users_data[referrer_id]["balance"] += 3
                users_data[referrer_id]["referrals"] += 1
                save_users_data(users_data)
                await context.bot.send_message(referrer_id, "*🎉 You earned ₹3 from a new referral!*", parse_mode="Markdown")

    # Initialize user data
    if user_id not in users_data:
        users_data[user_id] = {
            "balance": 0,
            "referrals": 0,
            "last_bonus": None,
            "joined_channels": False,
            "verified": False
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
            ["BONUS", "SUPPORT"],
            ["GET REDEEM CODE"],
            ["🔧 ADMIN PANEL"]
        ]
    else:
        keyboard = [
            ["BALANCE", "REFERAL LINK"],
            ["BONUS", "SUPPORT"],
            ["GET REDEEM CODE"]
        ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    text = "*🏠 WELCOME GET FREE REDEEM CODE*"

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
    """Show main menu after 5-second delay without showing loading message"""
    try:
        # Wait for 2 seconds silently for faster response
        await asyncio.sleep(8)

        # Show main menu with reply keyboard (add admin panel for admin)
        if chat_id == int(ADMIN_ID):
            keyboard = [
                ["BALANCE", "REFERAL LINK"],
                ["BONUS", "SUPPORT"],
                ["GET REDEEM CODE"],
                ["🔧 ADMIN PANEL"]
            ]
        else:
            keyboard = [
                ["BALANCE", "REFERAL LINK"],
                ["BONUS", "SUPPORT"],
                ["GET REDEEM CODE"]
            ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        main_menu_text = f"**\n\n*🏠 WELCOME {username} GET FREE REDEEM CODE USE BUTTON BELOW*"

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
                    ["BONUS", "SUPPORT"],
                    ["GET REDEEM CODE"],
                    ["🔧 ADMIN PANEL"]
                ]
            else:
                keyboard = [
                    ["BALANCE", "REFERAL LINK"],
                    ["BONUS", "SUPPORT"],
                    ["GET REDEEM CODE"]
                ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"*✅ Welcome {username}! Bot is ready to use.*",
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
        import asyncio
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
        text = f"*{username}, please join both channel and group first!*\n\n* After joining, click '✨claim' again.*"

        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            print(f"Message edit failed: {e}")
            await context.bot.send_message(user_id, text, reply_markup=reply_markup, parse_mode="Markdown")

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle web app data when user completes verification with 3-second delay"""
    print(f"Web app data received: {update.web_app_data.data}")

    user_id = str(update.effective_user.id)
    username = update.effective_user.first_name or "User"
    chat_id = update.effective_chat.id

    print(f"Processing verification for user {user_id} ({username}) in chat {chat_id}")

    # Mark user as verified and channel member since they reached this point
    # This means they already passed initial membership check
    if user_id not in users_data:
        users_data[user_id] = {
            "balance": 0,
            "referrals": 0,
            "last_bonus": None,
            "joined_channels": True,
            "verified": True
        }
    else:
        users_data[user_id]["verified"] = True
        users_data[user_id]["joined_channels"] = True

    save_users_data(users_data)
    print(f"User {user_id} marked as verified and saved to data")

    # Show main menu with 3-second delay
    print(f"Starting delayed main menu for user {user_id}")
    await show_delayed_main_menu(chat_id, username, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    user_id = str(update.effective_user.id)
    text = update.message.text

    if user_id not in users_data or not users_data[user_id]["joined_channels"] or not users_data[user_id].get("verified", False):
        await update.message.reply_text("*Please start the bot first with /start, join required channels, and complete verification.*", parse_mode="Markdown")
        return

    is_member = await check_membership(context, user_id)
    if not is_member:
        users_data[user_id]["joined_channels"] = False
        users_data[user_id]["verified"] = False
        save_users_data(users_data)
        await update.message.reply_text("*⚠️ You need to join both channel and group to use this bot. Please /start again.*", parse_mode="Markdown")
        return

    if text == "BALANCE":
        balance = users_data[user_id]["balance"]
        await update.message.reply_text(f"*💰 Your Balance: ₹{balance}*", parse_mode="Markdown")

    elif text == "REFERAL LINK":
        referrals = users_data[user_id]["referrals"]
        bot_username = context.bot.username
        referal_link = f"https://t.me/{bot_username}?start={user_id}"

        referal_text = f"*💥 Per refer ₹3*\n\n*😍 Minimum redeem code ₹10*\n\n*👩‍💻 24/7 support*\n\n*✅ Bot link: {referal_link}*\n\n*🚀 Total Referrals: {referrals}*"

        keyboard = [
            [
                InlineKeyboardButton("✨my invite", url=referal_link),
                InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(referal_text, reply_markup=reply_markup, parse_mode="Markdown")

    elif text == "GET REDEEM CODE":
        balance = users_data[user_id]["balance"]
        if balance < 10:
            await update.message.reply_text("*⚠️ Minimum redeem ₹10 you need to earn more by referring*", parse_mode="Markdown")
        else:
            await update.message.reply_text("*🟢 Enter amount to redeem:*", parse_mode="Markdown")
            context.user_data['waiting_for_amount'] = True

    elif text == "BONUS":
        keyboard = [
            [InlineKeyboardButton("🕒 Daily Bonus", callback_data="daily_bonus")],
            [InlineKeyboardButton("🎁 Gift Code", callback_data="gift_code")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("*✨ Choose One:*", reply_markup=reply_markup, parse_mode="Markdown")

    elif text == "SUPPORT":
        support_text = f"*🗨️ For Any  Help Dm : {SUPPORT_USERNAME}*"
        await update.message.reply_text(support_text, parse_mode="Markdown")
    
    elif text == "🔧 ADMIN PANEL" and user_id == ADMIN_ID:
        admin_keyboard = [
            ["📢 BROADCAST", "💰 GIVE BALANCE"],
            ["📊 BOT STATS", "👥 USER LIST"],
            ["🏠 BACK TO MAIN"]
        ]
        admin_reply_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)
        await update.message.reply_text("*🔧 Admin Panel*\n\n*Choose an option:*", reply_markup=admin_reply_markup, parse_mode="Markdown")
    
    elif text == "🏠 BACK TO MAIN" and user_id == ADMIN_ID:
        # Show admin main menu
        keyboard = [
            ["BALANCE", "REFERAL LINK"],
            ["BONUS", "SUPPORT"],
            ["GET REDEEM CODE"],
            ["🔧 ADMIN PANEL"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("*🏠 Back to Main Menu*", reply_markup=reply_markup, parse_mode="Markdown")
    
    # Admin Panel Features (Only for Admin)
    elif user_id == ADMIN_ID:
        if text == "ADMIN PANEL":
            admin_keyboard = [
                ["📢 BROADCAST", "💰 GIVE BALANCE"],
                ["📊 BOT STATS", "👥 USER LIST"]
            ]
            admin_reply_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)
            await update.message.reply_text("*🔧 Admin Panel*\n\n*Choose an option:*", reply_markup=admin_reply_markup, parse_mode="Markdown")
        
        elif text == "📢 BROADCAST":
            await update.message.reply_text("*📢 Send broadcast message:*\n\n*Type your message to send to all users:*", parse_mode="Markdown")
            context.user_data['waiting_for_broadcast'] = True
            
        elif text == "💰 GIVE BALANCE":
            await update.message.reply_text("*💰 Give Balance*\n\n*Format: user_id amount*\n*Example: 123456789 50*\n\n*Send user ID and amount:*", parse_mode="Markdown")
            context.user_data['waiting_for_balance_add'] = True
            
        elif text == "📊 BOT STATS":
            total_users = len(users_data)
            verified_users = sum(1 for user in users_data.values() if user.get("verified", False))
            total_balance = sum(user.get("balance", 0) for user in users_data.values())
            total_referrals = sum(user.get("referrals", 0) for user in users_data.values())
            
            stats_text = f"*📊 Bot Statistics*\n\n"
            stats_text += f"*👥 Total Users: {total_users}*\n"
            stats_text += f"*✅ Verified Users: {verified_users}*\n"
            stats_text += f"*💰 Total Balance: ₹{total_balance}*\n"
            stats_text += f"*🔄 Total Referrals: {total_referrals}*\n"
            
            await update.message.reply_text(stats_text, parse_mode="Markdown")
            
        elif text == "👥 USER LIST":
            if users_data:
                user_list = "*👥 User List (Top 10):*\n\n"
                sorted_users = sorted(users_data.items(), key=lambda x: x[1].get('balance', 0), reverse=True)[:10]
                
                for i, (uid, data) in enumerate(sorted_users, 1):
                    balance = data.get('balance', 0)
                    referrals = data.get('referrals', 0)
                    verified = "✅" if data.get('verified', False) else "❌"
                    user_list += f"*{i}. ID: {uid[:8]}...*\n*Balance: ₹{balance} | Refs: {referrals} {verified}*\n\n"
                    
                await update.message.reply_text(user_list, parse_mode="Markdown")
            else:
                await update.message.reply_text("*❌ No users found*", parse_mode="Markdown")
        
        # Handle broadcast message
        elif context.user_data.get('waiting_for_broadcast'):
            broadcast_msg = text
            context.user_data['waiting_for_broadcast'] = False
            
            success_count = 0
            failed_count = 0
            
            await update.message.reply_text("*📢 Broadcasting message...*", parse_mode="Markdown")
            
            for target_user_id in users_data.keys():
                try:
                    await context.bot.send_message(chat_id=int(target_user_id), text=f"*📢 Broadcast Message:*\n\n{broadcast_msg}", parse_mode="Markdown")
                    success_count += 1
                    await asyncio.sleep(0.1)  # Small delay to avoid rate limiting
                except Exception as e:
                    failed_count += 1
                    print(f"Failed to send to {target_user_id}: {e}")
            
            result_text = f"*📊 Broadcast Complete!*\n\n*✅ Sent: {success_count}*\n*❌ Failed: {failed_count}*"
            await update.message.reply_text(result_text, parse_mode="Markdown")
        
        # Handle give balance
        elif context.user_data.get('waiting_for_balance_add'):
            try:
                parts = text.split()
                if len(parts) != 2:
                    await update.message.reply_text("*❌ Invalid format!*\n\n*Use: user_id amount*\n*Example: 123456789 50*", parse_mode="Markdown")
                    return
                
                target_user_id = parts[0]
                amount = int(parts[1])
                
                if target_user_id in users_data:
                    users_data[target_user_id]["balance"] += amount
                    save_users_data(users_data)
                    
                    # Notify the user
                    try:
                        await context.bot.send_message(chat_id=int(target_user_id), text=f"*🎉 You received ₹{amount} from admin!*\n\n*💰 Your new balance: ₹{users_data[target_user_id]['balance']}*", parse_mode="Markdown")
                        await update.message.reply_text(f"*✅ Successfully added ₹{amount} to user {target_user_id}*\n\n*💰 User's new balance: ₹{users_data[target_user_id]['balance']}*", parse_mode="Markdown")
                    except Exception as e:
                        await update.message.reply_text(f"*✅ Balance added but failed to notify user*\n\n*💰 User's new balance: ₹{users_data[target_user_id]['balance']}*", parse_mode="Markdown")
                else:
                    await update.message.reply_text(f"*❌ User {target_user_id} not found!*", parse_mode="Markdown")
                
                context.user_data['waiting_for_balance_add'] = False
                
            except ValueError:
                await update.message.reply_text("*❌ Invalid amount! Please enter a valid number.*", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"*❌ Error: {str(e)}*", parse_mode="Markdown")

    # Handle redeem amount input (moved outside admin panel logic)
    elif context.user_data.get('waiting_for_amount'):
        try:
            amount = int(text)
            balance = users_data[user_id]["balance"]
            print(f"User {user_id} requesting redeem: amount={amount}, balance={balance}")

            if amount > balance:
                await update.message.reply_text(f"*⚠️ Insufficient balance. Your balance: ₹{balance}*", parse_mode="Markdown")
            elif amount < 10:
                await update.message.reply_text("*⚠️ Minimum redeem amount is ₹10*", parse_mode="Markdown")
            else:
                # Deduct balance
                users_data[user_id]["balance"] -= amount
                save_users_data(users_data)
                print(f"Balance deducted. New balance: {users_data[user_id]['balance']}")

                # Generate redeem code
                if redeem_codes:
                    code = redeem_codes.pop(0)
                    save_redeem_codes(redeem_codes)
                    print(f"Used predefined code: {code}")
                else:
                    code = generate_fake_redeem_code()
                    print(f"Generated new code: {code}")

                await update.message.reply_text(f"*🎉 Redeem Code Generated!*\n\n*💳 Code: `{code}`*\n\n*💰 Amount: ₹{amount}*\n\n*⚠️ Use within 24 hours*", parse_mode="Markdown")
                print(f"Redeem code sent to user {user_id}")

            context.user_data['waiting_for_amount'] = False
        except ValueError:
            await update.message.reply_text("*⚠️ Please enter a valid number*", parse_mode="Markdown")
        except Exception as e:
            print(f"Error in redeem code generation: {e}")
            await update.message.reply_text("*❌ Error generating redeem code. Please try again.*", parse_mode="Markdown")
            context.user_data['waiting_for_amount'] = False

async def daily_bonus_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)

    await query.answer()

    last_bonus = users_data[user_id].get("last_bonus")
    now = datetime.now()

    if last_bonus:
        last_bonus_time = datetime.fromisoformat(last_bonus)
        if now - last_bonus_time < timedelta(hours=24):
            next_bonus = last_bonus_time + timedelta(hours=24)
            time_left = next_bonus - now
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)

            await query.edit_message_text(f"*⏰ Next bonus available in {hours}h {minutes}m*", parse_mode="Markdown")
            return

    bonus_amount = 1
    users_data[user_id]["balance"] += bonus_amount
    users_data[user_id]["last_bonus"] = now.isoformat()
    save_users_data(users_data)

    await query.edit_message_text(f"*🎉 Daily bonus claimed!*\n\n*💰 You received ₹{bonus_amount}*\n\n*🕘 Come back tomorrow for more!*", parse_mode="Markdown")

async def gift_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("*🎁 Enter gift code:*", parse_mode="Markdown")
    context.user_data['waiting_for_gift_code'] = True

async def leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    sorted_users = sorted(users_data.items(), key=lambda x: x[1].get('referrals', 0), reverse=True)

    leaderboard_text = "*🏆 Top Referrers*\n\n"
    for i, (user_id, data) in enumerate(sorted_users[:10], 1):
        referrals = data.get('referrals', 0)
        if referrals > 0:
            leaderboard_text += f"*{i}. User {user_id[:8]}... - {referrals} referrals*\n"

    if leaderboard_text == "*🏆 Top Referrers*\n\n":
        leaderboard_text += "*No referrers yet. Be the first!*"

    await query.edit_message_text(leaderboard_text, parse_mode="Markdown")

async def handle_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_gift_code'):
        return False

    user_id = str(update.effective_user.id)
    gift_code = update.message.text.strip().upper()

    gift_codes = {
        "WELCOME10": 10,
        "BONUS5": 5,
        "GIFT3": 1
    }

    if gift_code in gift_codes:
        amount = gift_codes[gift_code]
        users_data[user_id]["balance"] += amount
        save_users_data(users_data)
        await update.message.reply_text(f"*🎉 Gift code redeemed!*\n\n*💰 You received ₹{amount}*", parse_mode="Markdown")
    else:
        await update.message.reply_text("*❌ Invalid gift code*", parse_mode="Markdown")

    context.user_data['waiting_for_gift_code'] = False
    return True

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_gift_code'):
        await handle_gift_code(update, context)
        return

    await handle_message(update, context)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(claim_callback, pattern="claim"))
    application.add_handler(CallbackQueryHandler(daily_bonus_callback, pattern="daily_bonus"))
    application.add_handler(CallbackQueryHandler(gift_code_callback, pattern="gift_code"))
    application.add_handler(CallbackQueryHandler(leaderboard_callback, pattern="leaderboard"))

    # Web app data handler - crucial for handling mini app responses
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))

    print("Bot started...")
    application.run_polling()

if __name__ == "__main__":
    main()
