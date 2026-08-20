import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonIllegalDrugs,
    InputReportReasonPersonalDetails,
    InputReportReasonOther
)
from telethon.errors import (
    FloodWaitError,
    AuthKeyUnregisteredError,
    UserDeactivatedError,
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneNumberInvalidError,
    RPCError
)
from config import Config
import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ReportEngine")

REPORT_REASONS = {
    'spam': {
        'label': '🚫 Spam',
        'description': 'Unwanted promotional or repetitive content',
        'class': InputReportReasonSpam
    },
    'violence': {
        'label': '⚔️ Violence',
        'description': 'Violent, dangerous, or threatening content',
        'class': InputReportReasonViolence
    },
    'pornography': {
        'label': '🔞 Pornography',
        'description': 'Explicit adult / NSFW media',
        'class': InputReportReasonPornography
    },
    'child_abuse': {
        'label': '🚸 Child Abuse',
        'description': 'Harmful content involving minors',
        'class': InputReportReasonChildAbuse
    },
    'copyright': {
        'label': '⚖️ Copyright',
        'description': 'Intellectual property / copyright infringement',
        'class': InputReportReasonCopyright
    },
    'illegal_drugs': {
        'label': '💊 Illegal Drugs',
        'description': 'Promotion or sale of illicit substances',
        'class': InputReportReasonIllegalDrugs
    },
    'personal_details': {
        'label': '👤 Personal Details',
        'description': 'Doxxing or sharing private personal info',
        'class': InputReportReasonPersonalDetails
    },
    'other': {
        'label': '❓ Other',
        'description': 'General terms of service violation',
        'class': InputReportReasonOther
    }
}

async def test_session(session_string):
    """Test if a Telethon StringSession is valid and authorized"""
    try:
        client = TelegramClient(StringSession(session_string), Config.API_ID, Config.API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Session is not authorized"
        me = await client.get_me()
        await client.disconnect()
        username = f"@{me.username}" if me.username else me.first_name
        return True, f"Valid ({username} - ID: {me.id})"
    except Exception as e:
        return False, str(e)

async def verify_target(target_identifier, session_string=None):
    """Verify target entity username/link using a StringSession"""
    client = None
    try:
        if session_string:
            client = TelegramClient(StringSession(session_string), Config.API_ID, Config.API_HASH)
            await client.connect()
        else:
            active_sessions = database.get_active_sessions()
            if not active_sessions:
                return {'success': False, 'error': 'No active session available to verify target'}
            client = TelegramClient(StringSession(active_sessions[0]['session_string']), Config.API_ID, Config.API_HASH)
            await client.connect()
            
        entity = await client.get_entity(target_identifier)
        
        entity_type = "user"
        title = getattr(entity, 'first_name', '') or getattr(entity, 'title', 'Unknown')
        username = getattr(entity, 'username', None)
        participants = getattr(entity, 'participants_count', None)
        
        if hasattr(entity, 'broadcast') and entity.broadcast:
            entity_type = "channel"
        elif hasattr(entity, 'megagroup') and entity.megagroup:
            entity_type = "supergroup"
        elif hasattr(entity, 'gigagroup') and entity.gigagroup:
            entity_type = "gigagroup"
        elif hasattr(entity, 'bot') and entity.bot:
            entity_type = "bot"
            
        await client.disconnect()
        
        return {
            'success': True,
            'id': entity.id,
            'title': title,
            'username': f"@{username}" if username else "None",
            'type': entity_type,
            'participants': participants
        }
    except Exception as e:
        if client and client.is_connected():
            await client.disconnect()
        return {'success': False, 'error': str(e)}

async def _single_account_report(session_info, target, report_type, reason_key, message_ids=None, comment=None):
    """Report target using a single account session"""
    session_string = session_info['session_string']
    session_id = session_info['id']
    label = session_info.get('label', f"Session #{session_id}")
    
    reason_meta = REPORT_REASONS.get(reason_key, REPORT_REASONS['spam'])
    reason_obj = reason_meta['class']()
    
    client = TelegramClient(StringSession(session_string), Config.API_ID, Config.API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            database.toggle_session_status(session_id, False)
            return {'success': False, 'label': label, 'error': 'Session expired or logged out'}
            
        entity = await client.get_entity(target)
        
        ids_to_report = message_ids if message_ids else []
        report_msg = comment or "Reported due to Terms of Service violation"
        
        await client(ReportRequest(
            peer=entity,
            id=ids_to_report,
            reason=reason_obj,
            message=report_msg
        ))
        
        return {'success': True, 'label': label}
        
    except FloodWaitError as e:
        return {'success': False, 'label': label, 'error': f"Rate limited: Wait {e.seconds}s"}
    except (AuthKeyUnregisteredError, UserDeactivatedError):
        database.toggle_session_status(session_id, False)
        return {'success': False, 'label': label, 'error': "Session deactivated"}
    except Exception as e:
        return {'success': False, 'label': label, 'error': str(e)}
    finally:
        if client.is_connected():
            await client.disconnect()

async def run_mass_report(target, report_type, reason_key, message_ids=None, comment=None, progress_callback=None):
    """Run parallel mass report across all active user sessions"""
    sessions = database.get_active_sessions()
    if not sessions:
        return {
            'success': False,
            'error': 'No active account sessions found! Please add session strings first.',
            'total': 0, 'success_count': 0, 'fail_count': 0
        }
        
    total = len(sessions)
    success_count = 0
    fail_count = 0
    details = []
    
    # Process tasks concurrently with a limit of 5 at a time
    semaphore = asyncio.Semaphore(5)
    
    async def worker(session_info, index):
        nonlocal success_count, fail_count
        async with semaphore:
            res = await _single_account_report(
                session_info, target, report_type, reason_key, message_ids, comment
            )
            if res['success']:
                success_count += 1
            else:
                fail_count += 1
            details.append(res)
            
            if progress_callback:
                try:
                    await progress_callback(
                        current=index + 1,
                        total=total,
                        success=success_count,
                        fail=fail_count,
                        latest_res=res
                    )
                except Exception as e:
                    logger.error(f"Progress callback error: {e}")
                    
    tasks = [worker(session_info, idx) for idx, session_info in enumerate(sessions)]
    await asyncio.gather(*tasks)
    
    # Log report to DB
    database.log_report(
        target=str(target),
        report_type=report_type,
        reason=reason_key,
        total_accounts=total,
        success_count=success_count,
        fail_count=fail_count,
        details=details
    )
    
    return {
        'success': True,
        'total': total,
        'success_count': success_count,
        'fail_count': fail_count,
        'details': details
    }

async def initiate_phone_login(phone_number):
    """Start login process by requesting OTP code to phone number"""
    client = TelegramClient(StringSession(), Config.API_ID, Config.API_HASH)
    try:
        await client.connect()
        sent_code = await client.send_code_request(phone_number)
        return {
            'success': True,
            'client': client,
            'phone_code_hash': sent_code.phone_code_hash
        }
    except PhoneNumberInvalidError:
        if client.is_connected():
            await client.disconnect()
        return {'success': False, 'error': 'Invalid Phone Number format. Use international format e.g. +919876543210'}
    except FloodWaitError as e:
        if client.is_connected():
            await client.disconnect()
        return {'success': False, 'error': f'Rate limit: Please wait {e.seconds} seconds before trying again.'}
    except Exception as e:
        if client.is_connected():
            await client.disconnect()
        return {'success': False, 'error': str(e)}

async def complete_phone_login_otp(client, phone_number, phone_code_hash, code):
    """Submit OTP code to Telethon client"""
    try:
        clean_code = str(code).replace(" ", "").strip()
        await client.sign_in(phone=phone_number, code=clean_code, phone_code_hash=phone_code_hash)
        
        session_string = client.session.save()
        me = await client.get_me()
        await client.disconnect()
        
        label = f"{me.first_name} (@{me.username})" if me.username else f"{me.first_name} (+{me.phone})"
        sid = database.add_session(session_string, label=label, phone=me.phone)
        
        return {
            'status': 'success',
            'session_id': sid,
            'user': f"{me.first_name} (@{me.username or 'NoUsername'}) - ID: {me.id}"
        }
    except SessionPasswordNeededError:
        return {'status': '2fa_required'}
    except PhoneCodeInvalidError:
        return {'status': 'error', 'error': 'Invalid OTP code! Please check and try again.'}
    except PhoneCodeExpiredError:
        if client.is_connected():
            await client.disconnect()
        return {'status': 'error', 'error': 'OTP Code expired! Please restart the login process.'}
    except Exception as e:
        if client.is_connected():
            await client.disconnect()
        return {'status': 'error', 'error': str(e)}

async def complete_phone_login_2fa(client, password):
    """Submit 2-Step Verification password to Telethon client"""
    try:
        await client.sign_in(password=password)
        session_string = client.session.save()
        me = await client.get_me()
        await client.disconnect()
        
        label = f"{me.first_name} (@{me.username})" if me.username else f"{me.first_name} (+{me.phone})"
        sid = database.add_session(session_string, label=label, phone=me.phone)
        
        return {
            'success': True,
            'session_id': sid,
            'user': f"{me.first_name} (@{me.username or 'NoUsername'}) - ID: {me.id}"
        }
    except Exception as e:
        if client.is_connected():
            await client.disconnect()
        return {'success': False, 'error': f"2FA Password Failed: {str(e)}"}

