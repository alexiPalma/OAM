import random
from config import UNITS

def roll(p): return random.random() < p
def destroy(s, unit, amount):
    amount=min(max(0,int(amount)),s.get(unit,0)); s[unit]=s.get(unit,0)-amount; return amount

def side_attack(attacker, defender, events, label):
    d=dict(defender)
    for _ in range(attacker['missile']):
        choices=[]
        if d['soldier']: choices.append(('soldier',350))
        if d['bmp']: choices.append(('bmp',22))
        if d['tank']: choices.append(('tank',random.randint(7,10)))
        if choices:
            unit,amount=random.choice(choices); killed=destroy(d,unit,amount); events.append(f'{label} 🚀 уничтожили {killed} {UNITS[unit]["title"]}')
        if d['helicopter'] and roll(.70): destroy(d,'helicopter',1); events.append(f'{label} 🚀 сбили вертолёт — 70%')
    for _ in range(attacker['plane']):
        if d['plane'] and roll(.20): destroy(d,'plane',1); events.append(f'{label} ✈️ самолёт сбил самолёт — 20%'); continue
        if roll(.70):
            choices=[x for x in [('soldier',150),('bmp',18),('tank',6),('drone',50),('helicopter',1)] if d[x[0]]]
            if choices:
                unit,amount=random.choice(choices); killed=destroy(d,unit,amount); events.append(f'{label} ✈️ уничтожили {killed} {UNITS[unit]["title"]} — 70%')
    for _ in range(attacker['helicopter']):
        if d['helicopter'] and roll(.40): destroy(d,'helicopter',1); events.append(f'{label} 🚁 вертолёт контрит вертолёт — 40%'); continue
        choices=[x for x in [('soldier',80),('bmp',10),('tank',3),('drone',20)] if d[x[0]]]
        if choices:
            unit,amount=random.choice(choices); killed=destroy(d,unit,amount); events.append(f'{label} 🚁 уничтожили {killed} {UNITS[unit]["title"]}')
    for _ in range(attacker['tank']):
        if d['tank'] and roll(.70): destroy(d,'tank',1); events.append(f'{label} 🛡 танк уничтожил танк — 70%')
        if d['bmp']: destroy(d,'bmp',2); events.append(f'{label} 🛡 танк уничтожил до 2 БМП')
        elif d['soldier']: destroy(d,'soldier',40); events.append(f'{label} 🛡 танк уничтожил до 40 пехоты')
    for _ in range(attacker['bmp']//3):
        if d['tank'] and roll(.65): destroy(d,'tank',1); events.append(f'{label} 🚙 3 БМП контрят танк — 65%')
    for _ in range(attacker['bmp']):
        if d['bmp'] and roll(.90): destroy(d,'bmp',1); events.append(f'{label} 🚙 БМП контрит БМП — 90%')
        elif d['soldier']: destroy(d,'soldier',10); events.append(f'{label} 🚙 БМП уничтожила до 10 пехоты')
    for _ in range(attacker['drone']//30):
        if d['helicopter'] and roll(.80): destroy(d,'helicopter',1); events.append(f'{label} 🛩 30 БПЛА сбили вертолёт — 80%')
    for _ in range(attacker['drone']//2):
        if d['soldier']: destroy(d,'soldier',15); events.append(f'{label} 🛩 2 БПЛА уничтожили до 15 пехоты')
    for _ in range(attacker['interceptor']):
        if d['drone'] and roll(.05): destroy(d,'drone',1); events.append(f'{label} 🎯 перехватчик сбил БПЛА — 5%')
    for _ in range(attacker['soldier']//7):
        if d['drone'] and roll(.70): destroy(d,'drone',1); events.append(f'{label} 🪖 7 пехотинцев сбили БПЛА — 70%')
    if attacker['soldier'] and d['soldier']:
        killed=destroy(d,'soldier',min(attacker['soldier'],d['soldier'])); events.append(f'{label} 🪖 пехота уничтожила {killed} пехоты')
    for _ in range(attacker['soldier']//15):
        if d['bmp']: destroy(d,'bmp',1); events.append(f'{label} 🪖 15 пехотинцев уничтожили БМП')
    return d

def resolve(attacker,defender):
    a={k:int(attacker[k]) for k in UNITS}; d={k:int(defender[k]) for k in UNITS}; events=[]
    d_after=side_attack(a,d,events,'🔴'); a_after=side_attack(d,a,events,'🔵')
    power_a=sum(a_after[k] for k in UNITS if k!='artillery'); power_d=sum(d_after[k] for k in UNITS if k!='artillery')
    winner='attacker' if power_a>=power_d else 'defender'
    return a_after,d_after,winner,events
