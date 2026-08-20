import sys
import asyncio
import logging
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient, events, Button
from telethon.tl.custom import Message
import database
from config import Config
from report_engine import (
    REPORT_REASONS,
    verify_target,
    test_session,
    run_mass_report,
    initiate_phone_login,
    complete_phone_login_otp,
    complete_phone_login_2fa
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("MassReportBot")

# Initialize SQLite database
database.init_db()

# User conversation state storage
# Structure: { user_id: { 'state': str, 'data': dict } }
USER_STATES = {}

def get_state(user_id):
    return USER_STATES.get(user_id, {'state': None, 'data': {}})

def set_state(user_id, state_name, data=None):
    if data is None:
        data = get_state(user_id).get('data', {})
    USER_STATES[user_id] = {'state': state_name, 'data': data}

def clear_state(user_id):
    USER_STATES.pop(user_id, None)

def is_authorized(user_id):
    if not Config.ADMIN_IDS:
        return True
    return user_id in Config.ADMIN_IDS

# Create Telethon Bot Client instance
bot = TelegramClient('bot_session', Config.API_ID, Config.API_HASH)

def build_progress_bar(current, total, length=10):
    percent = current / total if total > 0 else 0
    filled = int(round(length * percent))
    bar = '█' * filled + '░' * (length - filled)
    return bar, int(percent * 100)

def main_menu_buttons():
    return [
        [
            Button.inline("🚀 Start Mass Report", data="menu_report"),
            Button.inline("🔑 Session Manager", data="menu_sessions")
        ],
        [
            Button.inline("🔍 Verify Target", data="menu_verify"),
            Button.inline("📊 Report History", data="menu_history")
        ],
        [
            Button.inline("⚙️ System Stats", data="menu_stats"),
            Button.inline("ℹ️ Help & Setup", data="menu_help")
        ]
    ]

@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event: events.NewMessage.Event):
    if not is_authorized(event.sender_id):
        await event.respond("⛔ **Access Denied**: You are not authorized to use this bot.")
        return
        
    clear_state(event.sender_id)
    stats = database.get_stats()
    
    text = (
        "🤖 **Telegram Mass Reporting Bot**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Welcome! This bot allows you to run concurrent **Mass Report** operations "
        "on channels, groups, messages, or users using your registered account sessions.\n\n"
        f"🔑 **Active Worker Sessions**: `{stats['active_sessions']}/{stats['total_sessions']}`\n"
        f"📊 **Total Reports Processed**: `{stats['total_reports']}`\n"
        f"✅ **Successful Submissions**: `{stats['total_successes']}`\n\n"
        "Select an option below to begin:"
    )
    await event.respond(text, buttons=main_menu_buttons())

@bot.on(events.NewMessage(pattern="/menu"))
async def menu_handler(event: events.NewMessage.Event):
    await start_handler(event)

@bot.on(events.NewMessage(pattern="/report"))
async def report_cmd_handler(event: events.NewMessage.Event):
    if not is_authorized(event.sender_id):
        return
    await start_report_wizard(event.sender_id, event)

@bot.on(events.NewMessage(pattern="/sessions"))
async def sessions_cmd_handler(event: events.NewMessage.Event):
    if not is_authorized(event.sender_id):
        return
    await show_sessions_menu(event.sender_id, event)

@bot.on(events.NewMessage(pattern="/verify"))
async def verify_cmd_handler(event: events.NewMessage.Event):
    if not is_authorized(event.sender_id):
        return
    set_state(event.sender_id, "WAITING_VERIFY_TARGET")
    await event.respond("🔍 **Target Verifier**\nPlease enter the channel/group/user username or link (e.g., `@target_channel` or `https://t.me/target`):")

@bot.on(events.NewMessage(pattern="/history"))
async def history_cmd_handler(event: events.NewMessage.Event):
    if not is_authorized(event.sender_id):
        return
    await show_history(event)

# Callback Query Handler for Inline Buttons
@bot.on(events.CallbackQuery)
async def callback_handler(event: events.CallbackQuery.Event):
    if not is_authorized(event.sender_id):
        await event.answer("⛔ Unauthorized", alert=True)
        return
        
    data = event.data.decode('utf-8')
    user_id = event.sender_id
    
    if data == "main_menu":
        clear_state(user_id)
        stats = database.get_stats()
        text = (
            "🤖 **Telegram Mass Reporting Bot**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 **Active Worker Sessions**: `{stats['active_sessions']}/{stats['total_sessions']}`\n"
            f"📊 **Total Reports Processed**: `{stats['total_reports']}`\n\n"
            "Select an option below:"
        )
        await event.edit(text, buttons=main_menu_buttons())
        
    elif data == "menu_report":
        await start_report_wizard(user_id, event)
        
    elif data == "menu_sessions":
        await show_sessions_menu(user_id, event)
        
    elif data == "menu_verify":
        set_state(user_id, "WAITING_VERIFY_TARGET")
        await event.edit(
            "🔍 **Target Verifier**\n"
            "Please send the target username or link in chat (e.g. `@channel` or `https://t.me/channel`):",
            buttons=[[Button.inline("🔙 Back", data="main_menu")]]
        )
        
    elif data == "menu_history":
        await show_history(event)
        
    elif data == "menu_stats":
        stats = database.get_stats()
        text = (
            "⚙️ **System & Bot Statistics**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 **Total Sessions Added**: `{stats['total_sessions']}`\n"
            f"✅ **Active Working Sessions**: `{stats['active_sessions']}`\n"
            f"📊 **Total Mass Reports Run**: `{stats['total_reports']}`\n"
            f"🎯 **Total Individual Reports Delivered**: `{stats['total_successes']}`\n"
        )
        await event.edit(text, buttons=[[Button.inline("🔙 Back", data="main_menu")]])
        
    elif data == "menu_help":
        help_text = (
            "ℹ️ **Setup & Usage Guide**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "1. **Adding Accounts**: Use `Session Manager` -> `➕ Add String Session` to add Telethon string sessions.\n"
            "2. **Starting Mass Report**: Click `🚀 Start Mass Report` -> Select target type -> Enter username/link -> Select reason -> Launch!\n"
            "3. **How it works**: The bot connects to Telegram servers using your added account sessions and sends official `ReportRequest` calls simultaneously.\n"
            "4. **API Credentials**: Make sure your `API_ID` and `API_HASH` are set in `config.py` / `.env`."
        )
        await event.edit(help_text, buttons=[[Button.inline("🔙 Back", data="main_menu")]])
        
    elif data.startswith("type_"):
        report_type = data.split("_")[1]
        set_state(user_id, "WAITING_REPORT_TARGET", {'report_type': report_type})
        
        prompt = "🎯 **Enter Target Identifier**\nSend the `@username`, link (`https://t.me/...`), or ID of the target:"
        if report_type == "message":
            prompt = "🎯 **Enter Channel/Group for Message Report**\nSend the channel/group username or link containing the message:"
            
        await event.edit(prompt, buttons=[[Button.inline("🔙 Cancel", data="main_menu")]])
        
    elif data.startswith("reason_"):
        reason_key = data.split("_")[1]
        st = get_state(user_id)
        st['data']['reason'] = reason_key
        
        if st['data'].get('report_type') == 'message':
            set_state(user_id, "WAITING_MSG_ID", st['data'])
            await event.edit(
                "💬 **Enter Message ID**\nPlease send the Message ID to report (or post link e.g. `https://t.me/channel/123`):",
                buttons=[[Button.inline("🔙 Cancel", data="main_menu")]]
            )
        else:
            set_state(user_id, "CONFIRM_REPORT", st['data'])
            await show_report_confirmation(event, st['data'])
            
    elif data == "launch_report":
        st = get_state(user_id)
        report_data = st.get('data', {})
        clear_state(user_id)
        await execute_report_flow(event, report_data)
        
    elif data == "add_phone_session":
        set_state(user_id, "WAITING_LOGIN_PHONE")
        prompt = (
            "📱 **Add Account via Phone & OTP**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Please enter the **Phone Number** of the Telegram account to log in.\n\n"
            "Include your international country code e.g.:\n"
            "`+919876543210` or `+12345678901`"
        )
        await event.edit(prompt, buttons=[[Button.inline("🔙 Cancel", data="menu_sessions")]])
        
    elif data == "add_session":
        set_state(user_id, "WAITING_SESSION_STRING")
        prompt = (
            "➕ **Add String Session (Advanced)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Please send the **Telethon String Session** text in chat.\n\n"
            "💡 *Tip*: You can optionally add a label using format:\n"
            "`Label | StringSessionText`"
        )
        await event.edit(prompt, buttons=[[Button.inline("🔙 Cancel", data="menu_sessions")]])
        
    elif data == "test_sessions":
        await event.answer("🧪 Testing sessions...", alert=False)
        sessions = database.get_all_sessions()
        if not sessions:
            await event.edit("❌ No sessions found to test.", buttons=[[Button.inline("🔙 Back", data="menu_sessions")]])
            return
            
        msg = await event.edit("🧪 **Testing all sessions... Please wait.**")
        results = []
        for s in sessions:
            valid, info = await test_session(s['session_string'])
            database.toggle_session_status(s['id'], 1 if valid else 0)
            status_icon = "✅" if valid else "❌"
            results.append(f"{status_icon} **Session #{s['id']}** ({s.get('label', 'No Label')}): {info}")
            
        res_text = "🧪 **Session Test Results**\n━━━━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(results)
        await msg.edit(res_text, buttons=[[Button.inline("🔙 Back to Sessions", data="menu_sessions")]])
        
    elif data == "delete_session_menu":
        sessions = database.get_all_sessions()
        if not sessions:
            await event.answer("No sessions to delete", alert=True)
            return
        buttons = [
            [Button.inline(f"🗑️ Delete #{s['id']} ({s.get('label', 'Session')})", data=f"delsess_{s['id']}")]
            for s in sessions
        ]
        buttons.append([Button.inline("🔙 Back", data="menu_sessions")])
        await event.edit("🗑️ **Select session to delete:**", buttons=buttons)
        
    elif data.startswith("delsess_"):
        session_id = int(data.split("_")[1])
        database.delete_session(session_id)
        await event.answer(f"Session #{session_id} deleted!", alert=True)
        await show_sessions_menu(user_id, event)

async def start_report_wizard(user_id, event):
    active_count = len(database.get_active_sessions())
    if active_count == 0:
        text = (
            "⚠️ **No Active Account Sessions!**\n"
            "You must add at least 1 Telethon user session string before launching a mass report."
        )
        buttons = [
            [Button.inline("➕ Add Session Now", data="add_session")],
            [Button.inline("🔙 Back to Menu", data="main_menu")]
        ]
        if isinstance(event, events.CallbackQuery.Event):
            await event.edit(text, buttons=buttons)
        else:
            await event.respond(text, buttons=buttons)
        return
        
    set_state(user_id, "SELECT_REPORT_TYPE")
    text = (
        "🚀 **Mass Report Wizard (Step 1/3)**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Select what type of target you want to report:"
    )
    buttons = [
        [Button.inline("📢 Channel / Group", data="type_channel")],
        [Button.inline("💬 Specific Message", data="type_message")],
        [Button.inline("👤 User Account", data="type_user")],
        [Button.inline("🔙 Cancel", data="main_menu")]
    ]
    if isinstance(event, events.CallbackQuery.Event):
        await event.edit(text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons)

async def show_sessions_menu(user_id, event):
    clear_state(user_id)
    sessions = database.get_all_sessions()
    
    text = f"🔑 **Session Manager**\n━━━━━━━━━━━━━━━━━━━━━━━━━\nTotal Sessions: `{len(sessions)}`\n\n"
    if not sessions:
        text += "❌ No account sessions registered."
    else:
        for s in sessions:
            icon = "✅ Active" if s['is_active'] else "❌ Inactive/Expired"
            label = s.get('label') or f"Session #{s['id']}"
            text += f"• **ID #{s['id']}** | `{label}` | {icon}\n"
            
    buttons = [
        [Button.inline("📱 Add via Phone & OTP (Easy)", data="add_phone_session")],
        [Button.inline("🔑 Paste String Session (Advanced)", data="add_session")],
        [Button.inline("🧪 Test All Sessions", data="test_sessions"), Button.inline("🗑️ Delete", data="delete_session_menu")],
        [Button.inline("🔙 Main Menu", data="main_menu")]
    ]
    
    if isinstance(event, events.CallbackQuery.Event):
        await event.edit(text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons)

async def show_history(event):
    history = database.get_report_history(limit=10)
    if not history:
        text = "📊 **Report History**\n━━━━━━━━━━━━━━━━━━━━━━━━━\nNo report logs found."
    else:
        text = "📊 **Recent Mass Report Logs**\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for log in history:
            text += (
                f"🎯 **Target**: `{log['target']}`\n"
                f"📋 **Type**: `{log['report_type']}` | ⚠️ **Reason**: `{log['reason']}`\n"
                f"✅ Success: `{log['success_count']}/{log['total_accounts']}` | 🕒 {log['created_at']}\n"
                f"-----------------------------------------\n"
            )
    buttons = [[Button.inline("🔙 Main Menu", data="main_menu")]]
    if isinstance(event, events.CallbackQuery.Event):
        await event.edit(text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons)

async def show_report_confirmation(event, data):
    target = data.get('target')
    report_type = data.get('report_type')
    reason = data.get('reason')
    msg_id = data.get('message_id')
    active_sessions = len(database.get_active_sessions())
    
    reason_info = REPORT_REASONS.get(reason, {}).get('label', reason)
    
    text = (
        "🚀 **Confirm Mass Report Execution**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **Target**: `{target}`\n"
        f"📌 **Type**: `{report_type.upper()}`\n"
        f"⚠️ **Reason**: `{reason_info}`\n"
    )
    if msg_id:
        text += f"💬 **Message ID**: `{msg_id}`\n"
    text += f"🔑 **Worker Accounts**: `{active_sessions} Sessions`\n\n"
    text += "Are you ready to disptach mass reports across all active account sessions?"
    
    buttons = [
        [Button.inline("🚀 Launch Mass Report!", data="launch_report")],
        [Button.inline("❌ Cancel", data="main_menu")]
    ]
    await event.edit(text, buttons=buttons)

async def execute_report_flow(event, data):
    target = data.get('target')
    report_type = data.get('report_type')
    reason = data.get('reason')
    msg_id = data.get('message_id')
    
    message_ids = [int(msg_id)] if msg_id else []
    
    status_msg = await event.edit("⚡ **Initiating Mass Report Engine...**")
    last_update_time = time.time()
    
    async def progress_cb(current, total, success, fail, latest_res):
        nonlocal last_update_time
        # Throttle Telegram message updates to max once per 1.2s to avoid rate limits
        if time.time() - last_update_time < 1.2 and current < total:
            return
        last_update_time = time.time()
        
        bar, percent = build_progress_bar(current, total)
        latest_label = latest_res.get('label', 'Session')
        latest_status = "✅ Success" if latest_res.get('success') else f"❌ {latest_res.get('error', 'Failed')}"
        
        text = (
            "⚡ **Mass Report Execution in Progress**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 **Target**: `{target}`\n"
            f"⚠️ **Reason**: `{reason.upper()}`\n\n"
            f"📊 **Progress**: `[{bar}] {percent}%` ({current}/{total})\n"
            f"✅ **Success**: `{success}` | ❌ **Failed**: `{fail}`\n\n"
            f"🔹 **Latest Action**: {latest_label} ➔ {latest_status}"
        )
        try:
            await status_msg.edit(text)
        except Exception:
            pass
            
    res = await run_mass_report(
        target=target,
        report_type=report_type,
        reason_key=reason,
        message_ids=message_ids,
        progress_callback=progress_cb
    )
    
    summary_text = (
        "✅ **Mass Report Completed!**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **Target**: `{target}`\n"
        f"⚠️ **Reason**: `{reason.upper()}`\n"
        f"📊 **Total Account Sessions**: `{res['total']}`\n"
        f"✅ **Successful Submissions**: `{res['success_count']}`\n"
        f"❌ **Failed Submissions**: `{res['fail_count']}`\n\n"
        "All report requests have been processed and logged."
    )
    buttons = [[Button.inline("🔙 Main Menu", data="main_menu")]]
    await status_msg.edit(summary_text, buttons=buttons)

# Text Message Event Handler for Dialog States
@bot.on(events.NewMessage)
async def text_input_handler(event: events.NewMessage.Event):
    if event.text.startswith("/"):
        return # Handled by command decorators
    if not is_authorized(event.sender_id):
        return
        
    user_id = event.sender_id
    st = get_state(user_id)
    state = st.get('state')
    
    if state == "WAITING_LOGIN_PHONE":
        phone_num = event.text.strip()
        msg = await event.respond(f"⏳ **Sending OTP code to `{phone_num}`...**")
        res = await initiate_phone_login(phone_num)
        
        if res['success']:
            set_state(user_id, "WAITING_LOGIN_OTP", {
                'client': res['client'],
                'phone': phone_num,
                'phone_code_hash': res['phone_code_hash']
            })
            prompt = (
                f"📩 **OTP Code Sent to `{phone_num}`!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Please enter the OTP verification code received in your Telegram app.\n\n"
                "💡 *Tip*: You can type it with or without spaces e.g. `12345` or `1 2 3 4 5`."
            )
            await msg.edit(prompt, buttons=[[Button.inline("❌ Cancel", data="menu_sessions")]])
        else:
            clear_state(user_id)
            await msg.edit(f"❌ **Login Failed**: {res['error']}", buttons=[[Button.inline("🔑 Back to Sessions", data="menu_sessions")]])
            
    elif state == "WAITING_LOGIN_OTP":
        code = event.text.strip()
        data = st.get('data', {})
        client = data.get('client')
        phone = data.get('phone')
        phone_code_hash = data.get('phone_code_hash')
        
        msg = await event.respond("⏳ **Verifying OTP code...**")
        res = await complete_phone_login_otp(client, phone, phone_code_hash, code)
        
        if res['status'] == 'success':
            clear_state(user_id)
            await msg.edit(
                f"✅ **Account Logged In Successfully!**\n"
                f"👤 Account: `{res['user']}`\n"
                f"🔑 Session ID #{res['session_id']} saved to database.",
                buttons=[[Button.inline("🔑 Sessions Menu", data="menu_sessions")]]
            )
        elif res['status'] == '2fa_required':
            set_state(user_id, "WAITING_LOGIN_2FA", data)
            prompt = (
                "🔒 **Two-Step Verification (2FA) Required!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "This account has 2FA enabled. Please enter your **2-Step Verification Password** in chat:"
            )
            await msg.edit(prompt, buttons=[[Button.inline("❌ Cancel", data="menu_sessions")]])
        else:
            await msg.edit(f"❌ **OTP Error**: {res.get('error')}", buttons=[[Button.inline("🔑 Sessions Menu", data="menu_sessions")]])
            
    elif state == "WAITING_LOGIN_2FA":
        password = event.text.strip()
        data = st.get('data', {})
        client = data.get('client')
        
        msg = await event.respond("⏳ **Verifying 2FA Password...**")
        res = await complete_phone_login_2fa(client, password)
        clear_state(user_id)
        
        if res['success']:
            await msg.edit(
                f"✅ **2FA Login Successful!**\n"
                f"👤 Account: `{res['user']}`\n"
                f"🔑 Session ID #{res['session_id']} saved to database.",
                buttons=[[Button.inline("🔑 Sessions Menu", data="menu_sessions")]]
            )
        else:
            await msg.edit(f"❌ **2FA Failed**: {res.get('error')}", buttons=[[Button.inline("🔑 Sessions Menu", data="menu_sessions")]])

    elif state == "WAITING_SESSION_STRING":
        text = event.text.strip()
        clear_state(user_id)
        
        label = "Session"
        session_str = text
        if "|" in text:
            parts = text.split("|", 1)
            label = parts[0].strip()
            session_str = parts[1].strip()
            
        msg = await event.respond("🧪 **Validating session string...**")
        valid, info = await test_session(session_str)
        if valid:
            sid = database.add_session(session_str, label=label)
            if sid:
                await msg.edit(f"✅ **Session Added Successfully!**\nID #{sid}: {info}", buttons=[[Button.inline("🔑 Sessions Menu", data="menu_sessions")]])
            else:
                await msg.edit("⚠️ Session already exists in database.", buttons=[[Button.inline("🔑 Sessions Menu", data="menu_sessions")]])
        else:
            await msg.edit(f"❌ **Invalid Session**: {info}", buttons=[[Button.inline("🔑 Sessions Menu", data="menu_sessions")]])
            
    elif state == "WAITING_VERIFY_TARGET":
        target = event.text.strip()
        clear_state(user_id)
        
        msg = await event.respond(f"🔍 **Verifying target `{target}`...**")
        res = await verify_target(target)
        if res['success']:
            card = (
                "🎯 **Target Verification Result**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📛 **Title/Name**: `{res['title']}`\n"
                f"🆔 **Entity ID**: `{res['id']}`\n"
                f"👤 **Username**: `{res['username']}`\n"
                f"📌 **Type**: `{res['type'].upper()}`\n"
            )
            if res.get('participants') is not None:
                card += f"👥 **Members/Subscribers**: `{res['participants']}`\n"
            await msg.edit(card, buttons=[[Button.inline("🚀 Report This Target", data="menu_report"), Button.inline("🔙 Main Menu", data="main_menu")]])
        else:
            await msg.edit(f"❌ **Verification Failed**: {res['error']}", buttons=[[Button.inline("🔙 Main Menu", data="main_menu")]])
            
    elif state == "WAITING_REPORT_TARGET":
        target = event.text.strip()
        data = st.get('data', {})
        data['target'] = target
        
        msg = await event.respond(f"🔍 **Checking entity target `{target}`...**")
        res = await verify_target(target)
        
        target_info_text = ""
        if res['success']:
            target_info_text = f"\n✅ Verified: **{res['title']}** ({res['type'].upper()})"
            
        set_state(user_id, "SELECT_REASON", data)
        
        buttons = []
        row = []
        for r_key, r_val in REPORT_REASONS.items():
            row.append(Button.inline(r_val['label'], data=f"reason_{r_key}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([Button.inline("🔙 Cancel", data="main_menu")])
        
        text = (
            f"⚠️ **Select Mass Report Reason (Step 2/3)**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Target: `{target}`{target_info_text}\n\n"
            f"Choose the primary violation reason:"
        )
        await msg.edit(text, buttons=buttons)
        
    elif state == "WAITING_MSG_ID":
        raw = event.text.strip()
        msg_id = raw
        if "t.me/" in raw and "/" in raw:
            msg_id = raw.rstrip("/").split("/")[-1]
            
        if not msg_id.isdigit():
            await event.respond("❌ Invalid Message ID. Please send a numeric ID (e.g. `123`):")
            return
            
        data = st.get('data', {})
        data['message_id'] = int(msg_id)
        set_state(user_id, "CONFIRM_REPORT", data)
        await show_report_confirmation(event, data)

if __name__ == "__main__":
    missing = Config.validate()
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        print("\n❌ ERROR: Missing environment configuration!")
        print(f"Please set the following variables in your environment or .env file: {', '.join(missing)}")
        print("Example:\nBOT_TOKEN=123456789:ABC...\nAPI_ID=123456\nAPI_HASH=abcdef123456...\n")
    else:
        print("🚀 Starting Telegram Mass Report Bot...")
        bot.start(bot_token=Config.BOT_TOKEN)
        print("✅ Bot is online and listening for messages!")
        bot.run_until_disconnected()
