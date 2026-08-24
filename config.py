import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN=os.getenv('BOT_TOKEN','')
OWNER_ID=int(os.getenv('OWNER_ID') or os.getenv('ADMIN_ID') or '0')
ADMIN_ID=OWNER_ID
DB_PATH=os.getenv('DB_PATH','voennabot.db')
FARMS={0:{'income':0,'upgrade':500_000},1:{'income':15_000,'upgrade':500_000},2:{'income':36_000,'upgrade':900_000},3:{'income':50_000,'upgrade':1_000_000},4:{'income':50_000,'upgrade':2_000_000},5:{'income':100_000,'upgrade':3_000_000},6:{'income':140_000,'upgrade':6_000_000},7:{'income':220_000,'upgrade':9_000_000},8:{'income':333_000,'upgrade':11_000_000},9:{'income':777_000,'upgrade':18_000_000},10:{'income':899_000,'upgrade':30_000_000}}
UNITS={'soldier':{'id':1,'title':'🪖 Пехота','price':20_000,'loss':1_000},'interceptor':{'id':2,'title':'🎯 Дрон-перехватчик','price':4_000,'loss':4_000},'drone':{'id':3,'title':'🛩 БПЛА','price':120_000,'loss':20_000},'bmp':{'id':4,'title':'🚙 БМП','price':1_000_000,'loss':55_000},'tank':{'id':5,'title':'🛡 Танк','price':3_000_000,'loss':100_000},'helicopter':{'id':6,'title':'🚁 Вертолёт','price':4_000_000,'loss':100_000},'plane':{'id':7,'title':'✈️ Самолёт','price':6_000_000,'loss':500_000},'missile':{'id':8,'title':'🚀 Ракета','price':20_000_000,'loss':1_000_000},'artillery':{'id':9,'title':'💥 Артиллерия','price':0,'loss':250_000}}
UNIT_BY_ID={v['id']:k for k,v in UNITS.items()}
DONATIONS={50:5_000_000,100:11_000_000,500:100_000_000}
