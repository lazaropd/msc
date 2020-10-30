import json
import time
import base64 
import requests
import SessionState
import numpy as np
import pandas as pd
import streamlit as st
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from collections import Counter
from datetime import datetime, timedelta


# FIXED PARAMS INSIDE CODE
# - filtering cd_perfil != MED in the method login_widget
# - filtering cd_status != DE and cd_tipo != BA in the method load_data
# - filtering procedimento != 7a9b35196d16151fc2ea6958b1e96acf in the method load_data


# ENDPOINTS 
login_path  = 'https://app.mysmartclinic.com.br/API/controllers/user/login.php'
cookie_path = 'https://app.mysmartclinic.com.br/ajax/session.php'
jwtval_path = 'https://app.mysmartclinic.com.br/ajax/login.php'
cirgs_path  = 'https://app.mysmartclinic.com.br/ajax/cirurgia-list.php'
procs_path  = 'https://app.mysmartclinic.com.br/ajax/procedimento-list.php'
users_path  = 'https://app.mysmartclinic.com.br/ajax/usuario-list.php'
sched_path  = 'https://app.mysmartclinic.com.br/ajax/agenda-list.php?tp=l&de=FROM&ate=TO&usr=USER'

# CERTIFICATE = r'resources/msc.pem'

EQUIPS_FILE = r'data/equip_restrictions.json'
RESTR_FILE  = r'data/restrictions.json'

STYLE_FILE  = r'assets/styles/styles.css'
LOGO_FILE   = r'assets/images/logo_wide.png'
PAGE_TITLE  = 'MSC'
PAGE_ICON   = '👩‍⚕️'
PAGE_LAYOUT = 'wide' # wide or centered
state       = SessionState.get(authorized=False, page='home', cookie=None,
                users=None, procs=None, cirgs=None, sched=None)




##############################################################################
#
# UTILS
#
##############################################################################

def load_file(file_name, mode='r'):
    with open(file_name, mode) as file:
        content = file.read()
    return content

def encode_file(file_name, mime_type='image/jpeg'):
    fig      = file_name
    content  = load_file(fig, mode='rb')
    encoded  = base64.b64encode(content).decode()
    data_url = 'data:{};base64,{}'.format(mime_type, encoded)
    return data_url

def execute_request(endpoint):
    cookies = {"PHPSESSID": state.cookie}    
    response = requests.get(endpoint, cookies=cookies, verify=False) 
    print('GET request executed!')
    return response

def validate_jwt():
    endpoint = jwtval_path
    data = {
        "email" : state.email,
        "senha" : state.pwd,
        "jwt"   : state.jwt
    }
    print('\nValidating JWT')
    response = requests.post(endpoint, json=data, verify=False)
    if response.status_code == 200:
        # state.cookie  = s.cookies.get_dict()
        return True
    return False

def connect_database_old():
    # couldnt figure out how to keep Session alive from Python, 
    #   using PHPSESSID of an active and manually set browser session instead
    endpoint = login_path
    data = {
        "email"   : state.email,
        "password": state.pwd
    }
    print('\nConnecting to database')
    response = requests.post(endpoint, json=data, verify=False)
    if response.status_code == 200:
        state.jwt     = json.loads(response.content.decode('utf-8'))["jwt"]
        return True #validate_jwt()
    return False 

def connect_database():
    endpoint = cookie_path
    response = execute_request(endpoint)
    if response.status_code == 200:        
        try:
            result = json.loads(response.content.decode('utf-8'))["result"]
            if result:
                return True
        except:
            pass
    return False

def connection_expired(now):
    exp = jwt.decode(state.jwt, verify=False)["exp"]
    return True if now > exp else False

def disconnect_database():
    state.authorized = False
    state.cookie     = None
    state.users      = None
    state.procs      = None
    state.cirgs      = None
    state.sched      = None
    st.experimental_rerun()

def get_request(event, user=None, periodb=30, perioda=30):
    if event == 'users':
        endpoint = users_path
    elif event == 'procs':
        endpoint = procs_path
    elif event == 'cirgs':
        endpoint = cirgs_path
    elif event == 'sched':
        endpoint = sched_path
        dt_from = datetime.now() - timedelta(days=periodb)
        dt_to   = datetime.now() + timedelta(days=perioda)
        endpoint = endpoint.replace('FROM', datetime.strftime(dt_from, '%Y-%m-%d'))
        endpoint = endpoint.replace(  'TO', datetime.strftime(dt_to  , '%Y-%m-%d'))
        endpoint = endpoint.replace('USER', user)
    print('\nRequesting data for {}'.format(event))
    response = execute_request(endpoint)
    if response.status_code == 200:
        result = json.loads(response.content.decode('utf-8'))
        if isinstance(result, list):
            return result
        else:
            return {'error': response.content}
    else:
        return {'error': response.content}
    return {'error': 'no data available'}

def list_equipments(x, equip_restrictions):
    procs  = x.split(';')
    equips = []
    for proc in procs:
        if proc in equip_restrictions.keys():
            equips.append(equip_restrictions[proc])
    return list(np.array(equips).flatten())

def load_data(period=6):
    # restrictions
    equip_restrictions = json.loads(load_file(EQUIPS_FILE)) 
    restrictions       = json.loads(load_file(RESTR_FILE))

    # users
    users = get_request('users')
    if isinstance(users, list):
        users = pd.DataFrame.from_dict(users)
        users = users.loc[users.cd_perfil!='MED']
        users.rename(columns={'id':'id_usuario'}, inplace=True)
        state.users = users

    # procedures
    procs = get_request('procs')
    if isinstance(procs, list):
        state.procs = pd.DataFrame.from_dict(procs)

    # cirgs
    cirgs = get_request('cirgs')
    if isinstance(cirgs, list):
        state.cirgs = pd.DataFrame.from_dict(cirgs)

    # schedules
    agenda = pd.DataFrame()
    for user in users.id_usuario.unique():
        sched  = get_request('sched', user, 0, period)
        agenda = pd.concat([agenda, pd.DataFrame.from_dict(sched)], axis=0)
    cols_drop  = ['nf','min_hour','cd_tipo2','local','desccir','tisstuss',
                  'telefone','celular','orcamento','vl_orcamento','conferido',
                  'link','cpf_pac','tags','proc_valor_pago','vl_atendimento',
                  'vl_desconto','vl_pago']
    agenda['inicio'] = pd.to_datetime(agenda.inicio)
    agenda['fim']    = pd.to_datetime(agenda.fim)
    agenda = agenda.loc[(agenda.cd_status!='DE')&(agenda.cd_tipo!='BA')]
    agenda = agenda.loc[agenda.procedimentos!='7a9b35196d16151fc2ea6958b1e96acf']             
    agenda['equips'] = agenda.procedimentos.apply(lambda x: list_equipments(x, equip_restrictions))
    agenda.sort_values(by=['inicio','fim'], inplace=True)
    agenda.reset_index(drop=True, inplace=True)    
    agenda[['simult','simultproc','simult_list','simultproc_list','conflicts']] = \
        agenda['id'].apply(lambda x: get_intersections(x, agenda, restrictions))
    agenda.drop(cols_drop, inplace=True, axis=1)
    state.sched = agenda

def get_intersections(curr_id, agenda, restrictions, interval=30):
    current = agenda.loc[agenda.id==curr_id].iloc[0]
    t1, t2  = current.inicio, current.fim
    cur_eqs = current.equips
    s       = agenda.loc[(t2>agenda.inicio)&(t1<agenda.fim)].copy().reset_index(drop=True)
    sb      = s.copy()
    mt, Mt  = s.inicio.min(), s.fim.max()
    equips       = [item for sublist in s.equips for item in sublist if item in cur_eqs]
    equips_count = dict(Counter(equips))
    ct = mt
    bigger = 0
    while ct < Mt:
        over = s.loc[(ct+timedelta(minutes=interval)>s.inicio)&(ct<s.fim)]
        if len(over) > bigger:
            bigger = len(over)
            rows = over.index
        ct += timedelta(minutes=interval)
    if bigger > 0:
        s = s.loc[s.index.isin(rows)]
    sl, spl, conflicts = pd.DataFrame(), pd.DataFrame(), {}
    for k, v in restrictions.items():
        if k == 'simult':
            if 'max' in v.keys() and len(s) > v["max"]:
                sl = s
        if k == 'equips':
            for equip in v.keys():
                if equip in equips_count:
                    if equips_count[equip] > v[equip]:
                        spl = sb
                        conflicts.update({equip: equips_count[equip]})
    return pd.Series([len(s), len(conflicts), sl, spl, conflicts])

def get_availability(required_equips, agenda, restrictions, interval=30):
    mt, Mt  = agenda.inicio.min(), agenda.fim.max()
    ct = mt
    available = []
    while ct < Mt:
        conflicts = {}
        over      = agenda.loc[(ct+timedelta(minutes=interval)>agenda.inicio)&(ct<agenda.fim)]
        equips    = [item for sublist in over.equips for item in sublist if item in required_equips]
        equips_count = dict(Counter(equips))
        for k, v in restrictions.items():
            if k == 'equips':
                for equip in v.keys():
                    if equip in equips_count:
                        if equips_count[equip] >= v[equip]:
                            conflicts.update({equip: equips_count[equip]})
        available.append([ct, len(over), conflicts])
        ct += timedelta(minutes=interval)
    available = pd.DataFrame(available, columns=['datetime','rooms','equips'])
    available = pd.concat([available, available['equips'].apply(pd.Series)], axis=1).drop('equips', axis=1).fillna(0)
    available = available.melt(id_vars='datetime', var_name='restriction')
    available['date'] = available.datetime.dt.date
    available['time'] = available.datetime.dt.time
    available = available.loc[(available.time>=agenda.inicio.dt.time.min())&(available.time<=agenda.fim.dt.time.max())]
    available['time'] = available.datetime.dt.hour + available.datetime.dt.minute / 60
    return available

def format_simultlist(df):
    if len(df) > 0:
        df = df[['inicio','fim','profissional','descproc']]
        df['date'] = df.inicio.dt.date
        df['times'] = df.inicio
        df['timee'] = df.fim
        fig, ax = plt.subplots()
        for i, row in df.iterrows():
            ax.plot([row['times'],row['timee']], [len(df)-i,len(df)-i], lw=40)
            ax.text(row['times'], len(df)-i, row['descproc']+' - '+row['profissional'], va='center', ha='left')
        ax.set(ylabel=datetime.strftime(df.iloc[0].date, '%d/%m/%Y'))
        ax.margins(0.0, 0.2)
        ax.set_yticks([])
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        for spine in plt.gca().spines.values():
            spine.set_visible(False)
        return fig
    else:
        return None



##############################################################################
#
# WIDGETS
#
##############################################################################

def login_widget():
    st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
    st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
    st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
    with st.beta_container():
        lph, title, rph = st.beta_columns((1, 2, 1))
        with title:
            st.header('Login')
    with st.beta_container():
        lph, title, rph = st.beta_columns((1, 2, 1))
        with title:            
            cookie = st.text_input('Cookie')
    with st.beta_container():
        lph, but, rph = st.beta_columns((10, 1, 10))
        with but:
            if st.button('Entrar'):
                state.cookie     = cookie
                state.authorized = connect_database() 
                if state.authorized:
                    load_data()
                st.experimental_rerun()
    st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True) 
    st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)  
    st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)          
    
#@st.cache
def css_widget(file_name, logo_file_name, page_title='MyAPP', page_icon='🛠', layout='centered'): 
    st.beta_set_page_config(page_title=page_title, page_icon=page_icon, layout=layout, initial_sidebar_state='auto')
    style = '<style>{}</style>'.format(load_file(file_name))
    style = style.replace('LOGO_WIDE', encode_file(logo_file_name, 'image/png'))
    style_materials = "<style><link href='https://fonts.googleapis.com/icon?family=Material+Icons' rel='stylesheet'></style>"
    style_showcontrols = """<style>.toolbar, .instructions{ visibility: visible;display: block;}</style>"""   
    st.markdown(style + style_materials + style_showcontrols, unsafe_allow_html=True)


 
##############################################################################
#
# MY APP
#
##############################################################################
 
css_widget(STYLE_FILE, LOGO_FILE, page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=PAGE_LAYOUT)
     
if not state.authorized:
    login_widget()    
    
# elif not connect_database():
#     disconnect_database()
#     login_widget()

else:
    # restrictions
    equip_restrictions = json.loads(load_file(EQUIPS_FILE)) 
    restrictions       = json.loads(load_file(RESTR_FILE))
    procs              = state.procs

    # MENU BAR
    with st.sidebar:
        st.title('Menu') 
        state.page         = st.selectbox('Operação', ['Agenda','Atendimentos','Relatório'])
        period             = st.slider('Período', 1, 30, 6)
        procedures         = st.sidebar.multiselect('Procedimentos', procs.id_procedimento, 
                             format_func=lambda x:procs.loc[procs.id_procedimento==x]['procedimento'].values[0])
        required_equips    = list_equipments(';'.join(procedures), equip_restrictions)
        update_sched       = st.button('Atualizar Dados')

    if update_sched:
        load_data(period=period)
    procs  = state.procs
    agenda = state.sched

    st.title('{}'.format(state.page.upper()))        
    
    if state.page == 'Atendimentos':
        st.write(state.page)
       
    elif state.page == 'Agenda':
            
        st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
        st.subheader('Conflitos de sala e equipamentos')
        # list all conflicts for rooms or equipments        
        conflicts = agenda[['simult_list','simultproc_list','conflicts']].copy()
        conflicts['hash1'] = conflicts['simult_list'].apply(lambda x: str(np.array(x)))
        conflicts['hash2'] = conflicts['simultproc_list'].apply(lambda x: str(np.array(x)))
        conflicts.drop_duplicates(inplace=True, subset=['hash1','hash2'])
        conflicts['conflict_room'] = conflicts.simult_list.apply(lambda x: format_simultlist(x))
        conflicts['conflict_proc'] = conflicts.simultproc_list.apply(lambda x: format_simultlist(x))
        for idx, conflict in conflicts.iterrows():
            if conflict['conflict_room'] or conflict['conflict_proc']:
                col1, col2 = st.beta_columns(2)
                if conflict['conflict_room']:
                    col1.pyplot(conflict['conflict_room'])
                if conflict['conflict_proc']:
                    col1.pyplot(conflict['conflict_proc'])
                    col2.warning('Conflito para os seguintes equipamentos: {}'.format(list(conflict['conflicts'].keys())))
        
        st.subheader('Disponibilidade de sala e equipamentos')
        # list availability            
        available = get_availability(required_equips, agenda, restrictions)
        order = [7 + i * 0.5 for i in range(2*(21-7))]
        g = sns.catplot(data=available, x='time', y='value', col='restriction', row='date', kind='bar', order=order, height=4) 
        # g.set_xticklabels(rotation=90)  
        g.fig.subplots_adjust(hspace=.2) 
        for ax in g.axes.flat:                
            ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True)) 
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True)) 
            ax.set(xlabel='', ylabel='')
            ax.xaxis.set_major_locator(ticker.MultipleLocator(2)) 
            ax.tick_params(labelbottom=True, labelsize='xx-small')
            ax.set_title(ax.get_title(), fontsize='small')   
            ax.grid(axis='y', linewidth=1, color='#000000', alpha=0.2)
        st.pyplot(g)

    elif state.page == 'Relatório':
        st.write(state.users)
        st.write(state.procs)
        st.write(state.cirgs)
        st.write(state.sched)   


    with st.sidebar:
        if state.authorized:
            st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
            st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
            st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
            if st.button('Desconectar'):
                disconnect_database()



 












