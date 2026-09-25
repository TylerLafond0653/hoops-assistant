"""Send a phone alert through Discord (a webhook) or your Telegram bot.

Secrets come from environment variables (GitHub Actions) or inseason/secrets.local.json (your laptop):
  DISCORD_WEBHOOK   a Discord channel webhook URL (used if set)
  TELEGRAM_TOKEN    the token BotFather gave you
  TELEGRAM_CHAT_ID  found automatically the first time (send your bot a message first)

Test:  python inseason/notify.py "Test alert"
"""
import json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(HERE, 'secrets.local.json')


def load():
    cfg = {}
    if os.path.exists(LOCAL):
        cfg = json.load(open(LOCAL, encoding='utf-8'))
    for k in ('DISCORD_WEBHOOK', 'DISCORD_USER_ID', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'):
        if os.environ.get(k): cfg[k] = os.environ[k]
    return cfg


def api(token, method, **params):
    url = f'https://api.telegram.org/bot{token}/{method}'
    data = urllib.parse.urlencode(params).encode() if params else None
    with urllib.request.urlopen(url, data=data, timeout=20) as r:
        return json.load(r)


def chat_id(cfg):
    if cfg.get('TELEGRAM_CHAT_ID'): return cfg['TELEGRAM_CHAT_ID']
    ups = api(cfg['TELEGRAM_TOKEN'], 'getUpdates').get('result', [])
    ids = [u['message']['chat']['id'] for u in ups if 'message' in u]
    if not ids: sys.exit('No chat found: open your bot in Telegram, send it "hi", then run this again.')
    cfg['TELEGRAM_CHAT_ID'] = str(ids[-1])
    if os.path.exists(LOCAL):   # remember it so we don't have to look it up again
        saved = json.load(open(LOCAL, encoding='utf-8')); saved['TELEGRAM_CHAT_ID'] = cfg['TELEGRAM_CHAT_ID']
        json.dump(saved, open(LOCAL, 'w', encoding='utf-8'), indent=2)
    return cfg['TELEGRAM_CHAT_ID']


def send_discord(url, text, user_id=''):
    # an @mention makes it a priority ping on your phone
    uid = str(user_id).strip()
    body = {'content': (f'<@{uid}> ' if uid.isdigit() else '') + text[:1900]}
    if uid.isdigit(): body['allowed_mentions'] = {'users': [uid]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'User-Agent': 'hoops-assistant'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status in (200, 204)


def send(text):
    cfg = load()
    hook = cfg.get('DISCORD_WEBHOOK', '')
    if hook.startswith('https://'):
        return send_discord(hook, text, cfg.get('DISCORD_USER_ID', ''))
    if not cfg.get('TELEGRAM_TOKEN') or 'PASTE' in cfg['TELEGRAM_TOKEN']:
        sys.exit('Add your Discord webhook (or Telegram token) to inseason/secrets.local.json first.')
    r = api(cfg['TELEGRAM_TOKEN'], 'sendMessage', chat_id=chat_id(cfg), text=text)
    return r.get('ok', False)


if __name__ == '__main__':
    msg = ' '.join(sys.argv[1:]) or 'Test from your Hoops assistant: alerts are working!'
    print('sent' if send(msg) else 'failed')
