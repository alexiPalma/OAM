import aiosqlite
from datetime import datetime, timezone
from config import DB_PATH, UNITS

KILL_COLS = {k: f'kill_{k}' for k in UNITS}

async def connect():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute('PRAGMA foreign_keys=ON')
    return db

async def init_db():
    db = await connect()
    cols = ', '.join(f'{k} INTEGER NOT NULL DEFAULT 0' for k in UNITS)
    kills = ', '.join(f'kill_{k} INTEGER NOT NULL DEFAULT 0' for k in UNITS)
    await db.execute(f'''CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT NOT NULL DEFAULT '',balance INTEGER NOT NULL DEFAULT 0,farm_level INTEGER NOT NULL DEFAULT 0,tax INTEGER NOT NULL DEFAULT 0,last_payout TEXT NOT NULL DEFAULT '',daily_claim TEXT NOT NULL DEFAULT '',sub_claim INTEGER NOT NULL DEFAULT 0,last_attack TEXT NOT NULL DEFAULT '',attacks_won INTEGER NOT NULL DEFAULT 0,attacks_lost INTEGER NOT NULL DEFAULT 0,{cols},{kills})''')
    cur = await db.execute('PRAGMA table_info(users)')
    existing = {r[1] for r in await cur.fetchall()}
    base = {'username':"TEXT NOT NULL DEFAULT ''",'balance':'INTEGER NOT NULL DEFAULT 0','farm_level':'INTEGER NOT NULL DEFAULT 0','tax':'INTEGER NOT NULL DEFAULT 0','last_payout':"TEXT NOT NULL DEFAULT ''",'daily_claim':"TEXT NOT NULL DEFAULT ''",'sub_claim':'INTEGER NOT NULL DEFAULT 0','last_attack':"TEXT NOT NULL DEFAULT ''",'attacks_won':'INTEGER NOT NULL DEFAULT 0','attacks_lost':'INTEGER NOT NULL DEFAULT 0'}
    for k,v in {**{x:'INTEGER NOT NULL DEFAULT 0' for x in UNITS},**{f'kill_{x}':'INTEGER NOT NULL DEFAULT 0' for x in UNITS},**base}.items():
        if k not in existing: await db.execute(f'ALTER TABLE users ADD COLUMN {k} {v}')
    cur = await db.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='users'")
    for name, sql in await cur.fetchall():
        if sql and 'invalid user state' in sql.lower():
            safe_name = name.replace('"', '""')
            await db.execute(f'DROP TRIGGER IF EXISTS "{safe_name}"')
    tables=[
        'CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)',
        'CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY)',
        'CREATE TABLE IF NOT EXISTS promos(code TEXT PRIMARY KEY,amount INTEGER NOT NULL DEFAULT 0,uses INTEGER NOT NULL DEFAULT 0,max_uses INTEGER NOT NULL DEFAULT 1,reward_type TEXT NOT NULL DEFAULT "money",reward_amount INTEGER NOT NULL DEFAULT 0)',
        'CREATE TABLE IF NOT EXISTS promo_uses(code TEXT,user_id INTEGER,PRIMARY KEY(code,user_id))',
        'CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,title TEXT NOT NULL,price INTEGER NOT NULL,stars INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1)',
        'CREATE TABLE IF NOT EXISTS case_prizes(case_id TEXT,unit TEXT,amount INTEGER,weight REAL)',
        'CREATE TABLE IF NOT EXISTS battle_log(id INTEGER PRIMARY KEY AUTOINCREMENT,attacker INTEGER,defender INTEGER,winner INTEGER,report TEXT,created_at TEXT)',
        'CREATE TABLE IF NOT EXISTS message_templates(key TEXT PRIMARY KEY,text TEXT NOT NULL)',
        'CREATE TABLE IF NOT EXISTS earn_tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,url TEXT NOT NULL UNIQUE,reward INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1)',
        'CREATE TABLE IF NOT EXISTS earn_claims(user_id INTEGER,task_id INTEGER,PRIMARY KEY(user_id,task_id))',
        'CREATE TABLE IF NOT EXISTS quest_claims(user_id INTEGER,quest_id TEXT,PRIMARY KEY(user_id,quest_id))']
    for sql in tables: await db.execute(sql)

    cur = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='earn_claims'")
    if await cur.fetchone():
        cur = await db.execute('PRAGMA table_info(earn_claims)')
        earn_cols = {r[1] for r in await cur.fetchall()}
        if 'task_id' not in earn_cols:
            await db.execute('ALTER TABLE earn_claims RENAME TO earn_claims_legacy')
            await db.execute('CREATE TABLE earn_claims(user_id INTEGER,task_id INTEGER,PRIMARY KEY(user_id,task_id))')

    cur = await db.execute('PRAGMA table_info(promos)')
    promo_cols={r[1] for r in await cur.fetchall()}
    if 'reward_type' not in promo_cols: await db.execute('ALTER TABLE promos ADD COLUMN reward_type TEXT NOT NULL DEFAULT "money"')
    if 'reward_amount' not in promo_cols: await db.execute('ALTER TABLE promos ADD COLUMN reward_amount INTEGER NOT NULL DEFAULT 0')
    await db.execute('UPDATE promos SET reward_amount=amount WHERE reward_type="money" AND reward_amount=0')
    await db.commit(); await db.close()

async def ensure_user(uid, username=''):
    db = await connect(); stamp = datetime.now(timezone.utc).isoformat()
    try:
        cur = await db.execute('SELECT user_id FROM users WHERE user_id=?', (uid,))
        exists = await cur.fetchone()
        if exists: await db.execute('UPDATE users SET username=? WHERE user_id=?', (username or '', uid))
        else: await db.execute('INSERT INTO users(user_id,username,last_payout,farm_level) VALUES(?,?,?,0)', (uid, username or '', stamp))
        await db.commit()
    finally: await db.close()

async def user(uid):
    db=await connect(); cur=await db.execute('SELECT * FROM users WHERE user_id=?',(uid,)); row=await cur.fetchone(); await db.close(); return row
async def setting(key,default=None):
    db=await connect(); cur=await db.execute('SELECT value FROM settings WHERE key=?',(key,)); row=await cur.fetchone(); await db.close(); return row['value'] if row else default
async def set_setting(key,value):
    db=await connect(); await db.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value))); await db.commit(); await db.close()
async def is_admin(uid,owner_id):
    if uid==owner_id:return True
    db=await connect(); cur=await db.execute('SELECT 1 FROM admins WHERE user_id=?',(uid,)); row=await cur.fetchone(); await db.close(); return bool(row)

RATING_WEIGHTS = {'soldier':1,'interceptor':1,'drone':3,'bmp':7,'artillery':8,'tank':10,'helicopter':15,'plane':25,'missile':50}

async def top_users(limit=50):
    db=await connect()
    expr=' + '.join(f'COALESCE({k},0)*{weight}' for k,weight in RATING_WEIGHTS.items())
    cur=await db.execute(f'SELECT user_id,username,balance,farm_level,{expr} AS army_total FROM users ORDER BY army_total DESC, attacks_won DESC, user_id ASC LIMIT ?',(max(1,min(50,int(limit))),))
    rows=await cur.fetchall(); await db.close(); return rows

async def all_user_ids():
    db=await connect(); cur=await db.execute('SELECT user_id FROM users'); rows=await cur.fetchall(); await db.close(); return [x[0] for x in rows]
async def users_count():
    db=await connect(); cur=await db.execute('SELECT COUNT(*) c FROM users'); row=await cur.fetchone(); await db.close(); return row['c']
