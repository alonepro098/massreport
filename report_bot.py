import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonOther,
    InputReportReasonCopyright,
    InputReportReasonIllegalDrugs,
    InputReportReasonPersonalDetails
)
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.errors import FloodWaitError
import logging
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportBot:
    """Telegram Report Bot for reporting channels/groups/messages"""
    
    REPORT_REASONS = {
        'spam': {
            'label': 'Spam',
            'description': 'Unwanted promotional content',
            'type': InputReportReasonSpam
        },
        'violence': {
            'label': 'Violence',
            'description': 'Violent or threatening content',
            'type': InputReportReasonViolence
        },
        'pornography': {
            'label': 'Pornography',
            'description': 'Adult/NSFW content',
            'type': InputReportReasonPornography
        },
        'child_abuse': {
            'label': 'Child Abuse',
            'description': 'Content involving minors',
            'type': InputReportReasonChildAbuse
        },
        'copyright': {
            'label': 'Copyright',
            'description': 'Copyright infringement',
            'type': InputReportReasonCopyright
        },
        'illegal_drugs': {
            'label': 'Illegal Drugs',
            'description': 'Drug related content',
            'type': InputReportReasonIllegalDrugs
        },
        'personal_details': {
            'label': 'Personal Details',
            'description': 'Sharing personal information',
            'type': InputReportReasonPersonalDetails
        },
        'other': {
            'label': 'Other',
            'description': 'Other violation',
            'type': InputReportReasonOther
        }
    }
    
    def __init__(self, api_id, api_hash):
        self.api_id = api_id
        self.api_hash = api_hash
        self.client = None
        self.session_string = None
        
    async def login(self, session_string=None):
        """Login to Telegram"""
        from telethon.sessions import StringSession
        
        if session_string:
            self.client = TelegramClient(StringSession(session_string), self.api_id, self.api_hash)
        else:
            self.client = TelegramClient('report_session', self.api_id, self.api_hash)
        
        await self.client.start()
        return self.client.session.save()
    
    async def get_entity(self, identifier):
        """Get entity from username, phone, or ID"""
        try:
            entity = await self.client.get_entity(identifier)
            return entity
        except Exception as e:
            logger.error(f"Error getting entity: {e}")
            return None
    
    async def report_channel(self, channel_identifier, reason_type='spam', 
                            additional_info=None, message_ids=None):
        """Report a channel or group"""
        try:
            # Get entity
            entity = await self.get_entity(channel_identifier)
            if not entity:
                return {
                    'success': False,
                    'error': 'Could not find the channel/group'
                }
            
            # Get reason
            reason_class = self.REPORT_REASONS.get(reason_type, {}).get('type')
            if not reason_class:
                return {
                    'success': False,
                    'error': 'Invalid report reason'
                }
            
            reason = reason_class()
            
            # Prepare report
            if message_ids:
                # Report specific messages
                report = await self.client(ReportRequest(
                    peer=entity,
                    id=message_ids,
                    reason=reason,
                    message=additional_info or 'Reported by bot'
                ))
            else:
                # Report entire channel/group
                report = await self.client(ReportRequest(
                    peer=entity,
                    id=[],  # Empty list means report the whole chat
                    reason=reason,
                    message=additional_info or 'Reported by bot'
                ))
            
            return {
                'success': True,
                'message': f'Successfully reported {entity.title if hasattr(entity, "title") else entity.username}',
                'entity': entity
            }
            
        except FloodWaitError as e:
            return {
                'success': False,
                'error': f'Rate limited. Wait {e.seconds} seconds'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def report_message(self, channel_identifier, message_id, reason_type='spam',
                            additional_info=None):
        """Report a specific message"""
        try:
            entity = await self.get_entity(channel_identifier)
            if not entity:
                return {
                    'success': False,
                    'error': 'Could not find the channel/group'
                }
            
            reason_class = self.REPORT_REASONS.get(reason_type, {}).get('type')
            if not reason_class:
                return {
                    'success': False,
                    'error': 'Invalid report reason'
                }
            
            reason = reason_class()
            
            report = await self.client(ReportRequest(
                peer=entity,
                id=[message_id],
                reason=reason,
                message=additional_info or 'Reported by bot'
            ))
            
            return {
                'success': True,
                'message': f'Message {message_id} reported successfully',
                'entity': entity
            }
            
        except FloodWaitError as e:
            return {
                'success': False,
                'error': f'Rate limited. Wait {e.seconds} seconds'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def report_user(self, user_identifier, reason_type='spam', 
                         additional_info=None):
        """Report a user"""
        try:
            entity = await self.get_entity(user_identifier)
            if not entity:
                return {
                    'success': False,
                    'error': 'Could not find the user'
                }
            
            reason_class = self.REPORT_REASONS.get(reason_type, {}).get('type')
            if not reason_class:
                return {
                    'success': False,
                    'error': 'Invalid report reason'
                }
            
            reason = reason_class()
            
            report = await self.client(ReportRequest(
                peer=entity,
                id=[],  # Empty for user report
                reason=reason,
                message=additional_info or 'Reported by bot'
            ))
            
            return {
                'success': True,
                'message': f'User {entity.username or entity.id} reported successfully',
                'entity': entity
            }
            
        except FloodWaitError as e:
            return {
                'success': False,
                'error': f'Rate limited. Wait {e.seconds} seconds'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

class ReportBotHandler:
    """Handle report bot requests"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.report_history = []
        
    async def process_report_request(self, identifier, report_type='channel',
                                    reason='spam', message_id=None, 
                                    additional_info=None):
        """Process different types of report requests"""
        
        if report_type == 'channel':
            return await self.bot.report_channel(
                identifier, 
                reason, 
                additional_info
            )
        elif report_type == 'message':
            if not message_id:
                return {
                    'success': False,
                    'error': 'Message ID required for message report'
                }
            return await self.bot.report_message(
                identifier,
                message_id,
                reason,
                additional_info
            )
        elif report_type == 'user':
            return await self.bot.report_user(
                identifier,
                reason,
                additional_info
            )
        else:
            return {
                'success': False,
                'error': 'Invalid report type'
            }
    
    def get_report_reasons(self):
        """Get all available report reasons"""
        return {
            key: {
                'label': value['label'],
                'description': value['description']
            }
            for key, value in ReportBot.REPORT_REASONS.items()
        }
    
