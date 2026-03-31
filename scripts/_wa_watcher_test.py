import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from src.watchers.whatsapp_watcher import WhatsAppWatcher

print('Initializing WhatsAppWatcher...')
w = WhatsAppWatcher(check_interval=30)
print('Init OK, session:', w.session_path)
print('Checking for updates (will open browser)...')
try:
    items = w.check_for_updates()
    print(f'Urgent messages found: {len(items)}')
    if items:
        for item in items:
            print('  -', item.get('chat_name'), ':', item.get('message_preview','')[:80])
    print('PASS')
except Exception as e:
    print(f'FAIL: {type(e).__name__}: {e}')
    import traceback; traceback.print_exc()
