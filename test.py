import pandas as pd
import json


data = [{'user': 1,'query': 'abc', 'Filters': {}},
              {'user': 1,'query': 'efg', 'Filters': {u'Op': u'and', u'Type': u'date', u'Val': u'2000'}},
              {'user': 1,'query': 'fgs', 'Filters': {u'Op': u'and', u'Type': u'date', u'Val': u'2001'}},
              {'user': 2 ,'query': 'hij', 'Filters': {u'Op': u'and', u'Type': u'date', u'Val': u'2002'}},
              {'user': 2 ,'query': 'dcv', 'Filters': {u'Op': u'and', u'Type': u'date', u'Val': u'2001'}},
              {'user': 2 ,'query': 'tyu', 'Filters':{u'Op': u'and', u'Type': u'date', u'Val': u'1999'}},
              {'user': 3 ,'query': 'jhg', 'Filters':{u'Op': u'and', u'Type': u'date', u'Val': u'2001'}},
              {'user': 4 ,'query': 'mlh', 'Filters':{u'Op': u'and', u'Type': u'date', u'Val': u'2001'}},
             ]

data = pd.DataFrame(data).set_index('query')
print(data)

df_final = pd.concat([data, data['Filters'].apply(pd.Series)], axis=1).drop('Filters', axis=1)
print(df_final)

# df_pollutants = pd.DataFrame(data['Filters'].values.tolist(), index=data.index)
# print(df_pollutants)

# print(data.join(pd.DataFrame(data['Filters'].values.tolist())))

# df = pd.json_normalize(data['Filters'])
# print(df)

# data.Filters = data.Filters.apply(lambda x: json.dumps(x))
# print(data)

# print(pd.json_normalize(data['Filters']))