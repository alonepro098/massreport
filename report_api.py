from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
from report_bot import ReportBot, ReportBotHandler
from database import db, UserSession, SystemLog
from config import Config
import asyncio
import json
from datetime import datetime

report_api_bp = Blueprint('report_api', __name__, url_prefix='/api/report')

# Initialize report bot
report_bot = ReportBot(Config.API_ID, Config.API_HASH)
report_handler = ReportBotHandler(report_bot)

# Helper to run async functions
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@report_api_bp.route('/reasons', methods=['GET'])
@login_required
def get_report_reasons():
    """Get available report reasons"""
    reasons = report_handler.get_report_reasons()
    return jsonify({
        'success': True,
        'reasons': reasons
    })

@report_api_bp.route('/login', methods=['POST'])
@login_required
def login_bot():
    """Login the report bot with session"""
    data = request.json
    phone_number = data.get('phone_number')
    session_string = data.get('session_string')
    
    try:
        # Save session to database
        session_obj = UserSession.query.filter_by(phone_number=phone_number).first()
        
        if session_string:
            # Use provided session string
            run_async(report_bot.login(session_string))
            if session_obj:
                session_obj.session_string = session_string
            else:
                session_obj = UserSession(
                    phone_number=phone_number,
                    session_string=session_string,
                    is_active=True
                )
                db.session.add(session_obj)
        else:
            # Login with phone (will need OTP)
            new_session = run_async(report_bot.login())
            if session_obj:
                session_obj.session_string = new_session
            else:
                session_obj = UserSession(
                    phone_number=phone_number,
                    session_string=new_session,
                    is_active=True
                )
                db.session.add(session_obj)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bot logged in successfully',
            'session_id': session_obj.id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@report_api_bp.route('/report', methods=['POST'])
@login_required
def make_report():
    """Make a report"""
    data = request.json
    
    identifier = data.get('identifier')
    report_type = data.get('report_type', 'channel')  # channel, message, user
    reason = data.get('reason', 'spam')
    message_id = data.get('message_id')
    additional_info = data.get('additional_info', '')
    session_id = data.get('session_id')
    
    if not identifier:
        return jsonify({
            'success': False,
            'error': 'Identifier (username/link/ID) is required'
        })
    
    # Get session
    session_obj = UserSession.query.get(session_id)
    if not session_obj:
        return jsonify({
            'success': False,
            'error': 'Invalid session. Please login first.'
        })
    
    try:
        # Login with session
        run_async(report_bot.login(session_obj.session_string))
        
        # Process report
        result = run_async(report_handler.process_report_request(
            identifier=identifier,
            report_type=report_type,
            reason=reason,
            message_id=message_id,
            additional_info=additional_info
        ))
        
        # Log the report
        log = SystemLog(
            log_type='info',
            message=f'Report made on {identifier}',
            details=json.dumps({
                'type': report_type,
                'reason': reason,
                'result': result
            }),
            admin_id=current_user.id
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@report_api_bp.route('/history', methods=['GET'])
@login_required
def get_report_history():
    """Get report history"""
    logs = SystemLog.query.filter(
        SystemLog.message.contains('Report made on')
    ).order_by(SystemLog.created_at.desc()).limit(50).all()
    
    history = []
    for log in logs:
        try:
            details = json.loads(log.details) if log.details else {}
        except:
            details = {}
            
        history.append({
            'id': log.id,
            'identifier': log.message.replace('Report made on ', ''),
            'type': details.get('type', 'unknown'),
            'reason': details.get('reason', 'unknown'),
            'success': details.get('result', {}).get('success', False),
            'time': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({
        'success': True,
        'history': history
    })

@report_api_bp.route('/verify', methods=['POST'])
@login_required
def verify_identifier():
    """Verify if an identifier exists"""
    data = request.json
    identifier = data.get('identifier')
    session_id = data.get('session_id')
    
    if not identifier:
        return jsonify({
            'success': False,
            'error': 'Identifier is required'
        })
    
    session_obj = UserSession.query.get(session_id)
    if not session_obj:
        return jsonify({
            'success': False,
            'error': 'Please login first'
        })
    
    try:
        run_async(report_bot.login(session_obj.session_string))
        entity = run_async(report_bot.get_entity(identifier))
        
        if entity:
            return jsonify({
                'success': True,
                'exists': True,
                'type': 'channel' if hasattr(entity, 'title') else 'user',
                'name': getattr(entity, 'title', getattr(entity, 'username', str(entity.id))),
                'id': entity.id
            })
        else:
            return jsonify({
                'success': True,
                'exists': False,
                'message': 'Identifier not found'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
