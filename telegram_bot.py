import re
import asyncio
import datetime
from telethon import TelegramClient, events
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import InputPeerUser, InputPeerChannel
import pytz

from config import API_ID, API_HASH, TARGET_GROUP, ADMIN_ID, CHANNEL_ID
from database import Database
from cas_checker import CASChecker

class TelegramBot:
    def __init__(self):
        self.client = TelegramClient('herman_session', API_ID, API_HASH)
        self.db = None
        self.target_group = TARGET_GROUP
        self.admin_id = ADMIN_ID
        self.channel_id = CHANNEL_ID
        self.last_weekly_report = None
        self.source_groups = []
        self.debug_mode = True  # Включаем режим отладки по умолчанию

    async def start(self):
        await self.client.start()
        self.db = await Database.create()
        
        # Load source groups from database
        self.source_groups = await self.db.get_source_groups()
        print(f"Monitoring source groups: {self.source_groups}")
        
        # Register event handlers
        self.client.add_event_handler(self.handle_message, events.NewMessage(incoming=True))
        self.client.add_event_handler(self.handle_admin_command, events.NewMessage(from_users=self.admin_id))
        
        # Подписываемся на события канала CAS
        self.client.add_event_handler(
            self.process_cas_ban_message, 
            events.NewMessage(chats=[self.channel_id])
        )
        
        print("Bot started successfully!")
        
        # Отправляем уведомление администратору о запуске бота
        try:
            message = (f"🤖 Бот запущен и готов к работе!\n\n"
                f"Отслеживаемый канал CAS: {self.channel_id}\n"
                f"Целевая группа: {self.target_group}\n"
                f"Режим отладки: {'Включен' if self.debug_mode else 'Выключен'}\n\n"
                f"Используйте /help для просмотра доступных команд")
            
            success = await self.safe_send_to_admin(message)
            if not success:
                print("⚠️ Не удалось отправить сообщение администратору. "
                      "Убедитесь, что ID администратора правильный и "
                      "он ранее взаимодействовал с ботом.")
                print(f"ID администратора: {self.admin_id}")
        except Exception as e:
            print(f"Ошибка отправки уведомления администратору: {e}")
        
        # Start weekly report scheduler
        asyncio.create_task(self.weekly_report_scheduler())
        
        await self.client.run_until_disconnected()

    async def handle_message(self, event):
        """Handle incoming messages"""
        try:
            chat_id = event.chat_id
            sender_id = event.sender_id
            
            if hasattr(event.message, 'text'):
                message_text = event.message.text
                print(f"Message from {sender_id} in chat {chat_id}: {message_text[:50]}...")
                
                # Отладочное сообщение при режиме отладки
                if self.debug_mode and chat_id == self.channel_id:
                    await self.safe_send_to_admin(f"🔍 Сообщение из канала CAS Feed:\n{message_text[:200]}")
            
            # Check if message is from MissRose bot (ID: 609517172) and in one of our source groups
            if sender_id == 609517172 and chat_id in self.source_groups:  # MissRose_bot ID
                print(f"Processing message from MissRose bot in group {chat_id}")
                await self.process_rose_message(event)
                
            # Check if message is from the monitored channel for CAS bans
            elif chat_id == self.channel_id:
                print(f"Processing message from channel {self.channel_id}")
                await self.process_cas_ban_message(event)
                
        except Exception as e:
            print(f"Error handling message: {e}")
            import traceback
            print(traceback.format_exc())
            
            # Отправляем сообщение об ошибке администратору
            error_msg = f"❌ Ошибка при обработке сообщения:\n{str(e)}\n\n{traceback.format_exc()[:500]}"
            await self.safe_send_to_admin(error_msg)

    async def handle_admin_command(self, event):
        """Handle admin commands"""
        try:
            text = event.text.lower()
            
            # Command to refresh blacklist counter in admin panel: /refresh_panel
            if text == '/refresh_panel':
                try:
                    await event.respond("🔄 Обновление данных в панели администратора...")
                    
                    # Получаем текущий список заблокированных пользователей
                    if self.db.use_postgres:
                        blacklist_count = await self.db.conn.fetchval("SELECT COUNT(*) FROM users WHERE is_blacklisted = TRUE")
                    else:
                        cursor = await self.db.conn.execute("SELECT COUNT(*) FROM users WHERE is_blacklisted = 1")
                        blacklist_count = await cursor.fetchone()
                        blacklist_count = blacklist_count[0] if blacklist_count else 0
                    
                    await event.respond(f"✅ Обновление завершено. В черном списке пользователей: {blacklist_count}")
                    await event.respond("⚠️ Перезагрузите страницу админ-панели, чтобы увидеть изменения.")
                except Exception as e:
                    await event.respond(f"❌ Ошибка при обновлении панели: {str(e)}")
            
            # Command to toggle debug mode: /debug on or /debug off
            elif text.startswith('/debug'):
                parts = text.split()
                if len(parts) == 2:
                    if parts[1] == 'on':
                        self.debug_mode = True
                        await event.respond("🔍 Режим отладки включен. Вы будете получать все сообщения с канала CAS.")
                    elif parts[1] == 'off':
                        self.debug_mode = False
                        await event.respond("🔍 Режим отладки выключен.")
                    else:
                        await event.respond("Использование: /debug [on|off]")
                else:
                    await event.respond(f"Текущий статус режима отладки: {'Включен' if self.debug_mode else 'Выключен'}\nИспользование: /debug [on|off]")
            
            # Command to add a new source group: /add_group -123456789
            elif text.startswith('/add_group'):
                parts = text.split()
                if len(parts) == 2:
                    try:
                        group_id = int(parts[1])
                        if await self.db.add_source_group(group_id):
                            # Refresh our local list
                            self.source_groups = await self.db.get_source_groups()
                            await event.respond(f"Group {group_id} added to monitoring list.")
                        else:
                            await event.respond(f"Group {group_id} is already in the monitoring list.")
                    except ValueError:
                        await event.respond("Invalid group ID. Please use a valid integer ID.")
                else:
                    await event.respond("Usage: /add_group [group_id]")
                    
            # Command to check if channel is being monitored
            elif text == '/check_channel':
                try:
                    channel_entity = await self.client.get_entity(self.channel_id)
                    channel_name = getattr(channel_entity, 'title', str(self.channel_id))
                    
                    await event.respond(f"🔍 Проверка канала:\n\n"
                                       f"ID канала: {self.channel_id}\n"
                                       f"Название канала: {channel_name}\n"
                                       f"Отслеживается: Да\n"
                                       f"Режим отладки: {'Включен' if self.debug_mode else 'Выключен'}")
                    
                    # Try to fetch the last message from channel
                    try:
                        messages = await self.client.get_messages(self.channel_id, limit=3)
                        if messages and len(messages) > 0:
                            await event.respond(f"Последние сообщения в канале:")
                            
                            for i, msg in enumerate(messages):
                                msg_content = msg.text if hasattr(msg, 'text') else "[Не текстовое сообщение]"
                                await event.respond(f"Сообщение {i+1}:\n"
                                                  f"{msg_content[:200]}{'...' if len(msg_content) > 200 else ''}")
                                
                                # Test if this message would match our patterns
                                await self.test_message_patterns(event, msg_content)
                    except Exception as e:
                        await event.respond(f"Ошибка при получении сообщений: {str(e)}")
                
                except Exception as e:
                    await event.respond(f"Ошибка при проверке канала: {str(e)}")
            
            # Command to list all source groups: /list_groups
            elif text == '/list_groups':
                if self.source_groups:
                    groups_text = "\n".join([f"- {group}" for group in self.source_groups])
                    await event.respond(f"Monitoring the following groups:\n{groups_text}")
                else:
                    await event.respond("No groups are being monitored.")
            
            # Command to test with exact CAS message format from the screenshot
            elif text.startswith('/test_cas_exact'):
                parts = text.split(maxsplit=1)
                user_id = parts[1] if len(parts) > 1 else "123926479"  # Default to ID from screenshot
                
                # Create a fake event with the exact format shown in the screenshot
                test_text = f"User #{user_id} has been banned"
                await event.respond(f"Testing with exact CAS format: {test_text}")
                
                # Directly process this message
                success = await self.db.blacklist_user(int(user_id))
                await event.respond(f"Added user {user_id} to blacklist. Success: {success}")
                
                # Verify blacklisting worked
                is_blacklisted = await self.db.is_blacklisted(int(user_id))
                await event.respond(f"Verification: User {user_id} is blacklisted: {is_blacklisted}")
                
                # Get current blacklist count
                try:
                    if self.db.use_postgres:
                        blacklist_count = await self.db.conn.fetchval("SELECT COUNT(*) FROM users WHERE is_blacklisted = TRUE")
                    else:
                        cursor = await self.db.conn.execute("SELECT COUNT(*) FROM users WHERE is_blacklisted = 1")
                        blacklist_count = await cursor.fetchone()
                        blacklist_count = blacklist_count[0] if blacklist_count else 0
                        
                    await event.respond(f"Current blacklist count: {blacklist_count}")
                except Exception as e:
                    await event.respond(f"Error getting blacklist count: {e}")
            
            # Command to check blacklist status: /blacklist_status
            elif text == '/blacklist_status':
                try:
                    if self.db.use_postgres:
                        blacklist_count = await self.db.conn.fetchval("SELECT COUNT(*) FROM users WHERE is_blacklisted = TRUE")
                    else:
                        cursor = await self.db.conn.execute("SELECT COUNT(*) FROM users WHERE is_blacklisted = 1")
                        blacklist_count = await cursor.fetchone()
                        blacklist_count = blacklist_count[0] if blacklist_count else 0
                    
                    # Get a few recent entries
                    if self.db.use_postgres:
                        recent_users = await self.db.conn.fetch(
                            "SELECT user_id, date_added FROM users WHERE is_blacklisted = TRUE ORDER BY date_added DESC LIMIT 5"
                        )
                        recent_list = "\n".join([f"- User {user['user_id']} (added on {user['date_added']})" for user in recent_users])
                    else:
                        cursor = await self.db.conn.execute(
                            "SELECT user_id, date_added FROM users WHERE is_blacklisted = 1 ORDER BY date_added DESC LIMIT 5"
                        )
                        recent_users = await cursor.fetchall()
                        recent_list = "\n".join([f"- User {user[0]} (added on {user[1]})" for user in recent_users])
                    
                    status_message = f"📊 Blacklist Status:\n\n"
                    status_message += f"Total blacklisted users: {blacklist_count}\n\n"
                    
                    if recent_users:
                        status_message += f"Recent additions:\n{recent_list}"
                    else:
                        status_message += "No users in blacklist."
                    
                    await event.respond(status_message)
                except Exception as e:
                    await event.respond(f"Error getting blacklist status: {e}")
                    
            # Command to test CAS detection: /test_cas_detection Message text here
            elif text.startswith('/test_cas_detection'):
                test_message = event.text[len('/test_cas_detection'):].strip()
                if not test_message:
                    await event.respond("Please provide a test message. Usage: /test_cas_detection Test message with user ID")
                    return
                    
                await event.respond(f"Testing CAS ban detection on: {test_message}")
                await self.test_message_patterns(event, test_message)
                
            # Command to manually add to blacklist: /blacklist [user_id]
            elif text.startswith('/blacklist'):
                parts = text.split()
                if len(parts) == 2:
                    try:
                        user_id = int(parts[1])
                        await self.db.blacklist_user(user_id)
                        await event.respond(f"User {user_id} added to blacklist")
                    except ValueError:
                        await event.respond("Invalid user ID. Please use a valid integer ID.")
                else:
                    await event.respond("Usage: /blacklist [user_id]")
            
            # Command to get help: /help
            elif text == '/help':
                help_text = (
                    "Available commands:\n"
                    "/debug [on|off] - Включить/выключить режим отладки\n"
                    "/add_group [group_id] - Add a group to the monitoring list\n"
                    "/list_groups - List all groups being monitored\n"
                    "/blacklist_status - Check the current blacklist status\n"
                    "/test_cas_detection [message] - Test CAS ban detection patterns\n"
                    "/test_cas_exact [user_id] - Directly test adding a user to blacklist\n"
                    "/check_channel - Verify channel monitoring is working\n"
                    "/blacklist [user_id] - Manually add a user to blacklist\n"
                    "/refresh_panel - Refresh blacklist counter in admin panel\n"
                    "/help - Show this help message"
                )
                await event.respond(help_text)
                
        except Exception as e:
            print(f"Error handling admin command: {e}")
            await event.respond(f"Error processing command: {str(e)}")

    async def process_rose_message(self, event):
        """Process messages from MissRose bot"""
        # Example: "Hey there, Herman (@Anthony_Mackie_0, 7679028304)! Please, press the button, so we know, you are a real human being."
        message_text = event.message.text
        # Extract user ID using regex
        user_id_match = re.search(r'\(@[\w_]+, (\d+)\)', message_text)
        
        if user_id_match:
            user_id = int(user_id_match.group(1))
            # Check if user is blacklisted
            if not await self.db.is_blacklisted(user_id):
                # Extract username
                username_match = re.search(r'\((@[\w_]+), \d+\)', message_text)
                username = username_match.group(1) if username_match else None
                
                # Optional: check CAS as a fallback
                if CASChecker.is_banned(user_id):
                    await self.db.blacklist_user(user_id)
                    print(f"User {user_id} is CAS banned, added to blacklist")
                    return
                
                # Add user to our group
                await self.add_user_to_group(user_id, username)

    async def process_cas_ban_message(self, event):
        """Process CAS ban messages"""
        # Example: "User #6224871113 has been CAS banned!"
        message_text = event.message.text
        print(f"Received message from channel {self.channel_id}: {message_text}")
        
        # Расширенные шаблоны для разных форматов сообщений о банах
        ban_patterns = [
            r'User #(\d+) has been CAS banned!',      # Standard format
            r'#(\d+) has been banned',                # Alternative format
            r'User (\d+) has been banned',            # Another format
            r'(\d+) has been added to CAS',           # Possible format
            r'#(\d+)',                                # Simple format - just a number with #
            r'User #(\d+)',                           # Even simpler format
            r'User (\d+)',                            # Just "User" followed by ID
            r'[Uu]ser.*?(\d{9,})',                    # Any text with "user" and a long number
            r'(\d{9,})',                              # Any 9+ digit number (likely a Telegram ID)
            r'.*?(\d{9,}).*?banned',                  # Any number with "banned" nearby
            r'.*?banned.*?(\d{9,})',                  # "banned" followed by number
            r'CAS.*?(\d{9,})',                        # "CAS" followed by number
            r'(\d{9,}).*?CAS',                        # Number followed by "CAS"
        ]
        
        user_id = None
        matched_pattern = None
        
        for pattern in ban_patterns:
            match = re.search(pattern, message_text)
            if match:
                user_id = int(match.group(1))
                matched_pattern = pattern
                print(f"Found user ID {user_id} using pattern: {pattern}")
                break
        
        if user_id:
            # Проверка через CAS API перед добавлением в черный список
            is_cas_banned = CASChecker.is_banned(user_id)
            
            # Add to blacklist
            success = await self.db.blacklist_user(user_id)
            print(f"User {user_id} added to blacklist due to CAS ban. Success: {success}")
            
            # Check if blacklisting worked by querying the database
            is_blacklisted = await self.db.is_blacklisted(user_id)
            print(f"Verification: User {user_id} is blacklisted: {is_blacklisted}")
            
            # Send confirmation message to admin
            await self.safe_send_to_admin(f"✅ Пользователь {user_id} добавлен в черный список\n"
                                           f"Источник: канал CAS Feed\n"
                                           f"Шаблон: {matched_pattern}\n"
                                           f"CAS API проверка: {'В черном списке CAS' if is_cas_banned else 'Не в черном списке CAS, но добавлен как превентивная мера'}")
        else:
            print(f"Could not extract user ID from message: {message_text}")
            
            # Send debug info to admin if message couldn't be parsed
            if self.debug_mode:
                await self.safe_send_to_admin(f"⚠️ Не удалось извлечь ID пользователя из сообщения CAS:\n{message_text}")
            
        # Print current blacklist count - for debugging
        try:
            if self.db.use_postgres:
                blacklist_count = await self.db.conn.fetchval("SELECT COUNT(*) FROM users WHERE is_blacklisted = TRUE")
            else:
                cursor = await self.db.conn.execute("SELECT COUNT(*) FROM users WHERE is_blacklisted = 1")
                blacklist_count = await cursor.fetchone()
                blacklist_count = blacklist_count[0] if blacklist_count else 0
                
            print(f"Current blacklist count: {blacklist_count}")
        except Exception as e:
            print(f"Error getting blacklist count: {e}")

    async def add_user_to_group(self, user_id, username=None):
        """Add a user to the target group"""
        try:
            user = await self.client.get_entity(user_id)
            target_group = await self.client.get_entity(self.target_group)
            
            await self.client(InviteToChannelRequest(
                channel=target_group,
                users=[user]
            ))
            
            await self.db.add_user(user_id, username)
            print(f"Added user {user_id} to group {self.target_group}")
            
        except Exception as e:
            print(f"Error adding user {user_id} to group: {e}")

    async def send_weekly_report(self):
        """Send weekly report to admin"""
        try:
            stats = await self.db.get_weekly_stats()
            
            report = (
                f"📊 Weekly Report:\n\n"
                f"<blockquote>"
                f"👥 Users added: {stats['users_added']}\n"
                f"🚫 Users blacklisted: {stats['users_blacklisted']}\n"
                f"</blockquote>\n"
                f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await self.client.send_message(self.admin_id, report, parse_mode='html')
            print(f"Sent weekly report to admin {self.admin_id}")
            
        except Exception as e:
            print(f"Error sending weekly report: {e}")

    async def weekly_report_scheduler(self):
        """Schedule weekly reports"""
        while True:
            now = datetime.datetime.now()
            current_day = now.weekday()  # Monday is 0, Sunday is 6
            
            # If it's Sunday and we haven't sent a report yet this week
            if current_day == 6:
                # Check if we already sent a report today
                if (self.last_weekly_report is None or 
                    (now - self.last_weekly_report).days >= 7):
                    await self.send_weekly_report()
                    self.last_weekly_report = now
            
            # Wait for 12 hours before checking again
            await asyncio.sleep(12 * 60 * 60)

    async def test_message_patterns(self, event, test_message):
        """Test if a message matches any of the CAS ban patterns"""
        # Use the same patterns as in process_cas_ban_message
        ban_patterns = [
            r'User #(\d+) has been CAS banned!',
            r'#(\d+) has been banned',
            r'User (\d+) has been banned',
            r'(\d+) has been added to CAS',
            r'#(\d+)',
            r'User (\d+)',
            r'[Uu]ser.*?(\d{9,})',
            r'(\d{9,})',
            r'User #(\d+) has been',
            r'User #(\d+)',
        ]
        
        results = []
        for pattern in ban_patterns:
            match = re.search(pattern, test_message)
            if match:
                user_id = match.group(1)
                results.append(f"✅ Pattern: {pattern} -> Found user ID: {user_id}")
            else:
                results.append(f"❌ Pattern: {pattern} -> No match")
        
        await event.respond("\n".join(results))

    async def safe_send_to_admin(self, message):
        """Безопасная отправка сообщения администратору с обработкой ошибок"""
        try:
            # Проверка существования администратора перед отправкой
            try:
                admin = await self.client.get_entity(self.admin_id)
                await self.client.send_message(admin, message)
                return True
            except ValueError:
                # Если не можем найти администратора по ID, попробуем по username
                print(f"Невозможно найти администратора по ID {self.admin_id}. Проверьте ID или добавьте бота в контакты администратора.")
                return False
        except Exception as e:
            print(f"Ошибка при отправке сообщения администратору: {e}")
            return False

async def main():
    bot = TelegramBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main()) 