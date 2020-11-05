import pandas as pd
import json
import requests


import browser_cookie3
cookies = browser_cookie3.chrome(domain_name='.google.com')
# print(cookies)

# import os
# import json
# import base64 
# import win32crypt
# from Crypto.Cipher import AES

# path = r'%LocalAppData%\Google\Chrome\User Data\Local State'
# path = os.path.expandvars(path)
# with open(path, 'r') as file:
#     encrypted_key = json.loads(file.read())['os_crypt']['encrypted_key']
#     key = encrypted_key
# encrypted_key = base64.b64decode(encrypted_key)                                       # Base64 decoding
# encrypted_key = encrypted_key[5:]                                                     # Remove DPAPI
# decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

# print(encrypted_key)
# print(decrypted_key)

# print(encrypted_key.decode('utf-8'))
# data = bytes.fromhex(decrypted_key.decode('utf-8')) # the encrypted cookie
# print(data)

# nonce = data[3:3+12]
# ciphertext = data[3+12:-16]
# tag = data[-16:]

# cipher = AES.new(decrypted_key, AES.MODE_GCM, nonce=nonce)
# print(cipher)

# plaintext = cipher.decrypt_and_verify(ciphertext, tag)
# print(plaintext)



# import browsercookie



url = 'https://app.mysmartclinic.com.br/bem-vindo.php'

# cj = browsercookie.chrome()
# response = requests.get(url, cookies=cj)

cookies = browser_cookie3.chrome(domain_name='.mysmartclinic.com.br')
cookies = requests.utils.dict_from_cookiejar(cookies)

print(cookies['PHPSESSID'])
# print(cookies)


# # response = execute_request(ep)
# session  = requests.Session()
# print(session.cookies.get_dict())

# # response = session.get(ep)
# print(response)
# print(response.headers)
# print(response.content)
# print(session.cookies.get_dict())



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
# print(data)

df_final = pd.concat([data, data['Filters'].apply(pd.Series)], axis=1).drop('Filters', axis=1)
# print(df_final)

# df_pollutants = pd.DataFrame(data['Filters'].values.tolist(), index=data.index)
# print(df_pollutants)

# print(data.join(pd.DataFrame(data['Filters'].values.tolist())))

# df = pd.json_normalize(data['Filters'])
# print(df)

# data.Filters = data.Filters.apply(lambda x: json.dumps(x))
# print(data)

# print(pd.json_normalize(data['Filters']))