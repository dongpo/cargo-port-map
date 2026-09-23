"""Regenerate the published JSON Schema contracts."""
import json
from pathlib import Path
S={'type':'string'};N={'type':['number','null']};NS={'type':['string','null']};I={'type':'integer','minimum':1}
def obj(props,required=None):return {'type':'object','properties':props,'required':list(props) if required is None else required,'additionalProperties':False}
provenance=obj({'provider':{'const':'Global Fishing Watch'},'dataset':S,'source_event_id':S},['provider','dataset'])
port=obj({'id':S,'name':NS,'flag':NS,'longitude':{'type':'number','minimum':-180,'maximum':180},'latitude':{'type':'number','minimum':-90,'maximum':90},'anchorage_id':NS})
edge=obj({'origin_id':S,'destination_id':S,'voyage_count':I,'teu':N,'cargo_tonnes':N,'trade_value_usd':N})
visit=obj({'event_id':S,'visit_id':NS,'vessel_id':S,'ssvid':NS,'vessel_type':S,'port_id':NS,'port_name':NS,'port_flag':NS,'anchorage_id':NS,'longitude':N,'latitude':N,'arrival':S,'departure':S,'confidence':{'type':['number','string','null']},'rejection':NS,'provenance':provenance})
visit={'oneOf':[visit,obj({'event_id':S,'vessel_id':S,'arrival':{'const':''},'rejection':{'const':'unorderable'}})]}
voyage=obj({'voyage_id':S,'vessel_id':S,'ssvid':NS,'origin_id':S,'destination_id':S,'origin_arrival':S,'departure':S,'arrival':S,'destination_departure':S,'origin_event_id':S,'destination_event_id':S,'year':{'type':'integer'},'month':{'type':'string','pattern':'^[0-9]{4}-(0[1-9]|1[0-2])$'},'voyage_count':{'const':1},'teu':N,'cargo_tonnes':N,'trade_value_usd':N,'provenance':obj({'provider':{'const':'Global Fishing Watch'},'dataset':S,'method':{'const':'consecutive_distinct_port_visits'}})})
for name,schema in {'ports':{'type':'array','items':port},'period':obj({'period':S,'edges':{'type':'array','items':edge}}),'visit':visit,'voyage':voyage}.items():
 Path(f'schemas/{name}.schema.json').write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema','title':name,**schema},indent=2)+'\n')
