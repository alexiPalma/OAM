"""Make Top Fighters rank by accumulated kills, preserving existing UI."""
import fix

try:
    from db import top_users
except Exception:
    top_users = None

# Keep the existing top_users API/UI shape, but replace the ranking source.
# kill_* fields are accumulated by the battle logic.
KILL_FIELDS = (
    "kill_soldier", "kill_interceptor", "kill_drone", "kill_bmp",
    "kill_artillery", "kill_tank", "kill_helicopter", "kill_aircraft",
    "kill_rocket",
)

async def top_kill_users(limit=50):
    import db
    dbconn = await db.connect()
    try:
        cur = await dbconn.execute("SELECT id, username, " + ",".join(KILL_FIELDS) + " FROM users")
        rows = await cur.fetchall()
        def score(row):
            return sum(int(row[i] or 0) for i in range(2, len(row)))
        rows.sort(key=score, reverse=True)
        return [(r[0], r[1], score(r)) for r in rows[:limit]]
    finally:
        await dbconn.close()

# Expose the new source for the existing top UI without changing its markup.
fix.top_kill_users = top_kill_users
fix.TOP_KILLS_MODE = True
