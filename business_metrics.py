"""Company-scoped, defined metrics. Missing data is never zero."""
import datetime as dt,json,math,re
from pathlib import Path
from decimal import Decimal,InvalidOperation
JST=dt.timezone(dt.timedelta(hours=9))

def aggregate_ml(rows,now=None):
 now=now or dt.datetime.now(JST);periods={};seen=set();duplicates=set();invalid=set()
 for row in rows:
  period=None
  if not isinstance(row,list) or len(row)<4:continue
  if len(row)<5 and row[3] in ('予定売上','予定利益','買取件数'):raise ValueError('missing metric value')
  if len(row)<5:continue
  store,channel,serial,metric,amount=row[:5]
  if metric not in ('予定売上','予定利益','買取件数'):continue
  try:
   if isinstance(serial,str) and re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}',serial):day=dt.datetime.strptime(serial,'%Y/%m/%d').date()
   else:
    if isinstance(serial,bool) or not isinstance(serial,(int,float)) or not math.isfinite(serial):raise ValueError()
    day=dt.date(1899,12,30)+dt.timedelta(days=serial)
   period=day.strftime('%Y-%m')
   if day.day!=1 or day>now.date():continue
   if isinstance(amount,bool):raise ValueError()
   if isinstance(amount,str) and re.fullmatch(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?',amount):amount=amount.replace(',','')
   value=Decimal(str(amount))
   if not value.is_finite() or abs(value)>Decimal('1e18'):raise ValueError()
  except (ValueError,OverflowError,InvalidOperation):
   if period:invalid.add(period)
   continue
  key=(str(store),str(channel),period,metric)
  if key in seen:duplicates.add(period)
  seen.add(key);bucket=periods.setdefault(period,{})
  bucket[metric]=bucket.get(metric,Decimal(0))+value
 result=[]
 for period in sorted(set(periods)|invalid,reverse=True)[:3]:
  values=periods.get(period,{});bad=period in duplicates or period in invalid
  result.append({'period':period,'partial':period==now.strftime('%Y-%m'),'status':'ambiguous' if bad else 'observed','values':{} if bad else {k:float(v) for k,v in values.items()},'definition':'予定売上・予定利益は将来見込みであり、確定売上・確定利益ではありません。買取件数の集計定義は別途照合が必要。','closed_confirmed':False})
 return result

def cohort_comparison(rows,now=None):
 now=now or dt.datetime.now(JST)
 eligible=sorted([p['period'] for p in aggregate_ml(rows,now) if p['status']=='observed' and not p['partial']])[-2:]
 if len(eligible)!=2:return None
 maps={p:{} for p in eligible}
 for row in rows:
  if not isinstance(row,list) or len(row)<5 or row[3] not in ('予定売上','予定利益','買取件数'):continue
  try:
   serial=row[2];day=dt.datetime.strptime(serial,'%Y/%m/%d').date() if isinstance(serial,str) else dt.date(1899,12,30)+dt.timedelta(days=serial)
   period=day.strftime('%Y-%m')
   if day.day!=1:continue
   if period not in maps:continue
   value=Decimal(str(row[4]).replace(',',''));key=(str(row[0]),str(row[1]));maps[period].setdefault(key,{})[row[3]]=value
  except (ValueError,TypeError,InvalidOperation,OverflowError):return None
 before,after=eligible;metrics=('予定売上','予定利益','買取件数')
 common=[k for k in maps[before] if k in maps[after] and all(m in maps[before][k] and m in maps[after][k] for m in metrics)]
 if not common:return None
 totals={p:{m:float(sum((maps[p][k][m] for k in common),Decimal(0))) for m in metrics} for p in eligible}
 losses=sorted([{'store':k[0],'channel':k[1],'planned_profit_change':float(maps[after][k]['予定利益']-maps[before][k]['予定利益'])} for k in common if maps[after][k]['予定利益']<maps[before][k]['予定利益']],key=lambda r:r['planned_profit_change'])
 return {'before':before,'after':after,'pairs':len(common),'totals':totals,'negative_pairs':len(losses),'largest_decreases':losses[:10],'definition':'同一店舗×取引経路・3指標が両月に揃った組だけ。過去月も確定状態は未確認。施策の因果効果は示しません。'}

def proposals(periods):
 rows=[]
 for p in periods:
  if p['status']!='observed':rows.append({'title':'重複の原因を確認','reason':p['period']+'は店舗・経路・月・指標が重複しているため、合計を表示しません。','kind':'data_quality'});continue
  if p['partial']:rows.append({'title':'同じ店舗・同じ経過日数で比較する','reason':p['period']+'は月途中です。前月の月間合計との差だけで業績悪化と判定せず、買取件数・一件あたり予定利益・経路構成に分解します。','kind':'analysis_proposal'})
  v=p['values'];sales=v.get('予定売上');profit=v.get('予定利益')
  if sales and profit is not None:rows.append({'title':p['period']+'の利益構成を店舗・経路別に分解','reason':'予定利益÷予定売上は '+format(profit/sales*100,'.1f')+'%。確定利益率とは区別し、粗利額の寄与と店舗構成を検証してから改善施策を決めます。','kind':'hypothesis','evidence':{'period':p['period'],'numerator':profit,'denominator':sales}})
 return rows

def decode(result):
 if result.get('isError'):raise ValueError('read failed')
 if isinstance(result.get('structuredContent'),dict):return result['structuredContent']
 for c in result.get('content',[]):
  if c.get('type')=='text':
   try:
    d=json.loads(c['text'])
    if isinstance(d,dict):return d
   except ValueError:pass
 raise ValueError('missing structured response')

def refresh(data,home):
 data=Path(data);config=data/'business_sources.json'
 if not config.exists():return
 if config.is_symlink() or config.stat().st_size>128000:raise ValueError('invalid registry')
 sources=json.loads(config.read_text());output=[]
 from tool_gateway import Client
 client=None
 try:
  for source in sources:
   company=source['company']
   try:
    if source.get('adapter')!='ml_planned' or not re.fullmatch(r'[A-Za-z0-9_-]{10,}',source['spreadsheet_id']) or source.get('sheet')!='実績DB':raise ValueError()
    limit=source['row_count']
    if type(limit)!=int or not 2<=limit<=50000:raise ValueError()
    if client is None:client=Client(json.loads((Path(home)/'.claude.json').read_text())['mcpServers']['google-services'])
    def get(r):return decode(client.call('tools/call',{'name':'sheets_read','arguments':{'spreadsheet_id':source['spreadsheet_id'],'range':"'実績DB'!"+r}})).get('values',[])
    if get('A1:E1')!=[['店名','取引経路','月','区分','金額']]:raise ValueError('header changed')
    rows=[];last=1
    for start in range(2,limit+1,5000):
     page=get('A'+str(start)+':E'+str(min(start+4999,limit)));rows.extend(page)
     for i,r in enumerate(page):
      if r:last=start+i
    if last>=limit-100:raise ValueError('registered scope may be incomplete')
    periods=aggregate_ml(rows)
    if not periods:raise ValueError('no defined metrics')
    output.append({'company':company,'state':'observed','periods':periods,'cohort':cohort_comparison(rows),'proposals':proposals(periods),'source_url':'https://docs.google.com/spreadsheets/d/'+source['spreadsheet_id']+'/edit','range':'実績DB!A1:E'+str(limit),'coverage':'登録範囲内の集計。上限に近づいた場合は表示を停止します。','captured_at':dt.datetime.now(dt.timezone.utc).isoformat()})
   except Exception:output.append({'company':company,'state':'error','periods':[],'proposals':[],'detail':'参照権限・列定義・取得範囲の確認が必要です。前回の数値を最新として流用していません。'})
 finally:
  if client:client.close()
 from claude_bridge import atomic
 atomic(data/'business_metrics.json',{'companies':output,'captured_at':dt.datetime.now(dt.timezone.utc).isoformat()})

def snapshot(data,projects):
 try:
  p=Path(data)/'business_metrics.json'
  if p.is_symlink() or p.stat().st_size>1024*1024:raise ValueError()
  report=json.loads(p.read_text())
 except (OSError,ValueError):report={'companies':[]}
 for c in report.get('companies',[]):
  if c.get('state')=='observed':
   try:
    age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(c['captured_at'])).total_seconds()
    if not 0<=age<=7200:c['state']='stale';c['proposals']=[]
   except (ValueError,KeyError,TypeError):c['state']='stale';c['proposals']=[]
 registered={c.get('company') for c in report.get('companies',[])}
 for company in sorted({p['company'] for p in projects}-registered):report['companies'].append({'company':company,'state':'missing','periods':[],'proposals':[],'detail':'数値の参照元・指標定義が未登録です。ゼロではありません。'})
 return report
