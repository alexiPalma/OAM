import random
from config import UNITS

def roll(p): return random.random() < p

def destroy(s, unit, amount):
    amount=min(max(0,int(amount)),s.get(unit,0))
    s[unit]=s.get(unit,0)-amount
    return amount

def artillery_target(d, base, label, events, kills, attacker_title):
    """Artillery is countered by normal combat units at 25% reduced output.
    Interceptors, soldiers and artillery never target artillery.
    """
    if not d.get('artillery', 0) or base <= 0:
        return
    amount=max(1, int(round(base * 0.75)))
    killed=destroy(d,'artillery',amount)
    if killed:
        kills['artillery']+=killed
        events.append(f'{label} {attacker_title} уничтожил до {killed} артиллерии (-25%)')

def artillery_phase(attacker, defender, events, label, kills):
    d=dict(defender)
    # Artillery does NOT counter artillery. It only attacks the listed targets.
    for _ in range(int(attacker.get('artillery',0))):
        if d.get('soldier',0):
            killed=destroy(d,'soldier',30); kills['soldier']+=killed
            events.append(f'{label} 💥 артиллерия уничтожила до 30 пехоты')
        if d.get('bmp',0):
            killed=destroy(d,'bmp',2); kills['bmp']+=killed
            events.append(f'{label} 💥 артиллерия уничтожила до 2 БМП')
        if d.get('tank',0) and roll(0.65):
            killed=destroy(d,'tank',1); kills['tank']+=killed
            events.append(f'{label} 💥 артиллерия уничтожила танк — 65%')
    return d

def side_attack(attacker, defender, events, label, kills):
    d=dict(defender)
    for _ in range(attacker['missile']):
        choices=[]
        if d['soldier']: choices.append(('soldier',350))
        if d['bmp']: choices.append(('bmp',22))
        if d['tank']: choices.append(('tank',random.randint(7,10)))
        if d['artillery']: choices.append(('artillery',22))
        if choices:
            unit,amount=random.choice(choices)
            if unit=='artillery':
                artillery_target(d,amount,label,events,kills,'🚀 ракета')
            else:
                killed=destroy(d,unit,amount); kills[unit]+=killed
                events.append(f'{label} 🚀 уничтожили {killed} {UNITS[unit]["title"]}')
        if d['helicopter'] and roll(.70):
            killed=destroy(d,'helicopter',1); kills['helicopter']+=killed
            events.append(f'{label} 🚀 сбили вертолёт — 70%')
    for _ in range(attacker['plane']):
        if d['plane'] and roll(.20):
            killed=destroy(d,'plane',1); kills['plane']+=killed
            events.append(f'{label} ✈️ самолёт сбил самолёт — 20%'); continue
        if roll(.70):
            choices=[x for x in [('soldier',150),('bmp',18),('tank',6),('drone',50),('helicopter',1)] if d[x[0]]]
            if d['artillery']: choices.append(('artillery',18))
            if choices:
                unit,amount=random.choice(choices)
                if unit=='artillery':
                    artillery_target(d,amount,label,events,kills,'✈️ самолёт')
                else:
                    killed=destroy(d,unit,amount); kills[unit]+=killed
                    events.append(f'{label} ✈️ уничтожили {killed} {UNITS[unit]["title"]} — 70%')
    for _ in range(attacker['helicopter']):
        if d['helicopter'] and roll(.40):
            killed=destroy(d,'helicopter',1); kills['helicopter']+=killed
            events.append(f'{label} 🚁 вертолёт контрит вертолёт — 40%'); continue
        choices=[x for x in [('soldier',80),('bmp',10),('tank',3),('drone',20)] if d[x[0]]]
        if d['artillery']: choices.append(('artillery',10))
        if choices:
            unit,amount=random.choice(choices)
            if unit=='artillery':
                artillery_target(d,amount,label,events,kills,'🚁 вертолёт')
            else:
                killed=destroy(d,unit,amount); kills[unit]+=killed
                events.append(f'{label} 🚁 уничтожили {killed} {UNITS[unit]["title"]}')
    for _ in range(attacker['tank']):
        if d['tank'] and roll(.70):
            killed=destroy(d,'tank',1); kills['tank']+=killed
            events.append(f'{label} 🛡 танк уничтожил танк — 70%')
        if d['bmp']:
            killed=destroy(d,'bmp',2); kills['bmp']+=killed
            events.append(f'{label} 🛡 танк уничтожил до 2 БМП')
        elif d['soldier']:
            killed=destroy(d,'soldier',40); kills['soldier']+=killed
            events.append(f'{label} 🛡 танк уничтожил до 40 пехоты')
        elif d['artillery']:
            artillery_target(d,2,label,events,kills,'🛡 танк')
    for _ in range(attacker['bmp']//3):
        if d['tank'] and roll(.65):
            killed=destroy(d,'tank',1); kills['tank']+=killed
            events.append(f'{label} 🚙 3 БМП контрят танк — 65%')
    for _ in range(attacker['bmp']):
        if d['bmp'] and roll(.90):
            killed=destroy(d,'bmp',1); kills['bmp']+=killed
            events.append(f'{label} 🚙 БМП контрит БМП — 90%')
        elif d['soldier']:
            killed=destroy(d,'soldier',10); kills['soldier']+=killed
            events.append(f'{label} 🚙 БМП уничтожила до 10 пехоты')
        elif d['artillery']:
            artillery_target(d,1,label,events,kills,'🚙 БМП')
    for _ in range(attacker['drone']//30):
        if d['helicopter'] and roll(.80):
            killed=destroy(d,'helicopter',1); kills['helicopter']+=killed
            events.append(f'{label} 🛩 30 БПЛА сбили вертолёт — 80%')
    for _ in range(attacker['drone']//2):
        if d['soldier']:
            killed=destroy(d,'soldier',15); kills['soldier']+=killed
            events.append(f'{label} 🛩 2 БПЛА уничтожили до 15 пехоты')
    for _ in range(attacker['interceptor']):
        # Interceptors do not counter artillery.
        if d['drone'] and roll(.05):
            killed=destroy(d,'drone',1); kills['drone']+=killed
            events.append(f'{label} 🎯 перехватчик сбил БПЛА — 5%')
    for _ in range(attacker['soldier']):
        # Soldiers do not counter artillery.
        if d['interceptor'] and roll(.50):
            killed=destroy(d,'interceptor',1); kills['interceptor']+=killed
            events.append(f'{label} 🪖 солдат уничтожил перехватчик — 50%')
    for _ in range(attacker['soldier']//7):
        if d['drone'] and roll(.70):
            killed=destroy(d,'drone',1); kills['drone']+=killed
            events.append(f'{label} 🪖 7 пехотинцев сбили БПЛА — 70%')
    if attacker['soldier'] and d['soldier']:
        killed=destroy(d,'soldier',min(attacker['soldier'],d['soldier'])); kills['soldier']+=killed
        events.append(f'{label} 🪖 пехота уничтожила {killed} пехоты')
    for _ in range(attacker['soldier']//15):
        if d['bmp']:
            killed=destroy(d,'bmp',1); kills['bmp']+=killed
            events.append(f'{label} 🪖 15 пехотинцев уничтожили БМП')
    return d

def resolve(attacker, defender, with_kills=False):
    a={k:int(attacker[k]) for k in UNITS}; d={k:int(defender[k]) for k in UNITS}
    events=[]; kills_a={k:0 for k in UNITS}; kills_d={k:0 for k in UNITS}
    d_after=artillery_phase(a,d,events,'🔴',kills_a); a_after=artillery_phase(d,a,events,'🔵',kills_d)
    d_after=side_attack(a,d_after,events,'🔴',kills_a); a_after=side_attack(d,a_after,events,'🔵',kills_d)
    power_a=sum(a_after[k] for k in UNITS if k!='artillery'); power_d=sum(d_after[k] for k in UNITS if k!='artillery')
    winner='attacker' if power_a>=power_d else 'defender'
    if with_kills: return a_after,d_after,winner,events,kills_a,kills_d
    return a_after,d_after,winner,events
