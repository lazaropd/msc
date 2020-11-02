import os
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
from datetime import datetime, timedelta, time as ttime


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
PROCESSED   = r'processed/'

STYLE_FILE  = r'assets/styles/styles.css'
LOGO_FILE   = r'assets/images/logo_wide.png'
PAGE_TITLE  = 'MSC'
PAGE_ICON   = '👩‍⚕️'
PAGE_LAYOUT = 'centered' # wide or centered
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

def save_json(content, file_name, mode='w'):
    try:
        with open(file_name, mode, encoding='utf-8') as file:
            json.dump(content, file, indent=4)
        return True
    except Exception as e:        
        return e

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
        sched  = get_request('sched', user, period, period)
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

def get_availability(required_equips, agenda, restrictions, professionals=[], interval=30):
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
        for prof in professionals:
            if len(over.loc[over.id_usuario==prof]) > 0:
                name = over.loc[over.id_usuario==prof].profissional.iloc[0]
                conflicts.update({name: len(over.loc[over.id_usuario==prof])})
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
        df = df[['inicio','fim','profissional','descproc']].copy()
        df['date'] = df.inicio.dt.date
        df.reset_index(drop=True, inplace=True)
        fig, ax = plt.subplots(figsize=(6.4, 3.6))
        colors = plt.cm.Dark2(np.linspace(0,1,len(df)))
        for i, row in df.iterrows(): 
            # ax.plot([row['inicio'],row['fim']], [len(df)-i,len(df)-i], lw=10)
            ax.hlines(len(df)-i, row['inicio'], row['fim'], color=colors[i], lw=40)
            ax.text(row['inicio'], len(df)-i, row['descproc']+' - '+row['profissional'], va='center', ha='left')
        ax.set(title=datetime.strftime(df.iloc[0].date, '%d/%m/%Y'))
        ax.margins(0.0, 0.2)
        ax.set_yticks([])
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30)) 
        ax.grid(axis='x', linewidth=1, color='#000000', alpha=0.4)
        for spine in plt.gca().spines.values():
            spine.set_visible(False)
        return fig
    else:
        return None

def prepare_report(df, bycol, sortby, sortasc):
    dfagg = df.groupby(bycol).agg({"vl_real":sum, "vl_comissao":sum, "cancelado":sum, "processado":sum, "id":len})
    dfagg = dfagg.sort_values(by=sortby, ascending=sortasc)
    dfagg.rename(columns={"vl_real":"Valor Total", "vl_comissao":"Valor Comissão","cancelado":"Cancelamentos",
                          "processado":"Processados", "id":"Agendamentos"}, inplace=True)
    dfagg['% Cancelamentos'] = 100 * dfagg.Cancelamentos / dfagg.Agendamentos
    return dfagg


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
    users              = state.users

    # MENU BAR
    with st.sidebar:
        st.title('Menu') 
        state.page         = st.selectbox('Operação', ['Agenda','Atendimentos','Relatório'])
        period             = st.slider('Período', 1, 90, 6)
        procedures         = st.sidebar.multiselect('Procedimentos', procs.id_procedimento, 
                             format_func=lambda x:procs.loc[procs.id_procedimento==x]['procedimento'].values[0])
        required_equips    = list_equipments(';'.join(procedures), equip_restrictions)
        professional       = st.sidebar.multiselect('Profissional', users.id_usuario, 
                             format_func=lambda x:users.loc[users.id_usuario==x]['nome'].values[0])
        if state.page == 'Atendimentos':
            show_all       = st.checkbox('Mostrar processados', False)
        if state.page == 'Relatório':
            period         = st.date_input('Período', (datetime.today()-timedelta(days=30), datetime.today()))
        update_sched       = st.button('Atualizar Dados')

    if update_sched:
        load_data(period=period)
    procs  = state.procs
    agenda = state.sched

    st.title('{}'.format(state.page.upper()))        
    
    if state.page == 'Atendimentos':
        
        pending = agenda.loc[(agenda.id_usuario.isin(professional))&(agenda.fim<datetime.today())].copy()
        pending.inicio = pending.inicio.apply(lambda x: datetime.strftime(x, '%d/%m/%Y %H:%M'))
        pending.fim    = pending.fim.apply(lambda x: datetime.strftime(x, '%d/%m/%Y %H:%M'))
        pending.vl_procedimento = pending.vl_procedimento.astype(float)
        for i, row in pending.iterrows():
            file_name = os.path.join(PROCESSED, "{}.json".format(row['id']))
            if show_all or not os.path.isfile(file_name):
                st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
                st.success('Resumo da Operação') 
                with st.beta_container():
                    desc, form = st.beta_columns((1, 1))
                    with desc:
                        st.write(f"Profissional: {row['profissional']}")
                        st.write(f"Início: {row['inicio']}")
                        st.write(f"Término: {row['fim']}")
                        st.write(f"Paciente: {row['paciente']}")
                        st.write(f"Procedimentos: {row['descproc']}")
                        st.write(f"Valor Total: R$ {row['vl_procedimento']:.2f}") 
                        if os.path.isfile(file_name):
                            curr_content = json.loads(load_file(file_name))
                            st.write(f"Valor Real: R$ {curr_content['vl_total']:.2f}")
                            st.write(f"Tipo de Comissão: {curr_content['tp']}")
                            st.write(f"Forma de Pagamento: {curr_content['fmt']}") 
                            st.write(f"Valor da Comissão: R$ {curr_content['vl_comissao']:.2f}")
                    with form:                    
                        vlb = st.number_input('Valor Real:', 0., 10000., row['vl_procedimento'], key=f'vlb{i}')
                        tp  = st.selectbox('Tipo de Comissão:', ['R$', '%'], key=f'tp{i}')
                        fmt = st.selectbox('Forma de Pagamento:', ['Dinheiro', 'Maquininha'], key=f'fmt{i}')
                        pct = st.number_input('Valor:', 50 if tp == 'R$' else 70 if fmt == 'Dinheiro' else 60, key=f'pct{i}')
                        vlr = round(vlb * pct / 100 if tp == '%' else pct, 2)
                with st.beta_container():
                    if os.path.isfile(file_name):
                        if "cancelado" in curr_content:
                            if curr_content['cancelado']:
                                st.error(f"Comissão: R$ {vlr} (CANCELADO)")
                            else:
                                st.success(f"Comissão: R$ {vlr} (PROCESSADO)")  
                    else:             
                        st.warning(f"Comissão: R$ {vlr} (PENDENTE)")
                    l, bt1, bt2, r = st.beta_columns((3, 1, 1, 3))  
                    if bt1.button('Processar', key=f'btn{i}'):                    
                        content = {"id": row['id'], "id_usuario": row['id_usuario'], 
                                    "id_paciente": row['id_paciente'], "tp": tp, "fmt": fmt, "pct": pct, 
                                    "vl_total": vlb, "vl_comissao": vlr
                                    }
                        save = save_json(content, file_name)
                        if save == True:  
                            st.success('Salvo') 
                        else:
                            st.error(save)
                        st.experimental_rerun()
                    if bt2.button('Desmarcar', key=f'btnc{i}'):                    
                        content = {"id": row['id'], "id_usuario": row['id_usuario'], 
                                    "id_paciente": row['id_paciente'], "tp": tp, "fmt": fmt, "pct": 0, 
                                    "vl_total": 0, "vl_comissao": 0, "cancelado": True
                                    }
                        if save_json(content, file_name):
                            st.success('Salvo')
                        st.experimental_rerun()


    elif state.page == 'Agenda':
            
        df_incoming = agenda.loc[agenda.inicio>=datetime.today().replace(hour=0, minute=0)]

        # list all conflicts for rooms or equipments        
        conflicts = df_incoming.copy()
        conflicts = conflicts[['simult_list','simultproc_list','conflicts']]
        conflicts['hash1'] = conflicts['simult_list'].apply(lambda x: str(np.array(x)))
        conflicts['hash2'] = conflicts['simultproc_list'].apply(lambda x: str(np.array(x)))
        conflicts.drop_duplicates(inplace=True, subset=['hash1','hash2'])
        conflicts['conflict_room'] = conflicts.simult_list.apply(lambda x: format_simultlist(x))
        conflicts['conflict_proc'] = conflicts.simultproc_list.apply(lambda x: format_simultlist(x))
        conflicts.dropna(subset=['conflict_room', 'conflict_proc'], how='all', inplace=True)
        conflicts.reset_index(drop=True, inplace=True)
        if len(conflicts) > 0:
            st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
            st.subheader('Conflitos de sala e equipamentos') 
            st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
            cols = st.beta_columns(2)
            for idx, conflict in conflicts.iterrows():
                if conflict['conflict_room'] or conflict['conflict_proc']:
                    if conflict['conflict_room']:
                        cols[idx%2].pyplot(conflict['conflict_room'])
                    if conflict['conflict_proc']:
                        cols[idx%2].pyplot(conflict['conflict_proc'])
                        # cols[idx%2].write('Conflito para os seguintes equipamentos: {}'.format(list(conflict['conflicts'].keys())))
        
        # list availability        
        st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
        st.subheader('Disponibilidade de sala e equipamentos')
        st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
        available = get_availability(required_equips, df_incoming, restrictions, professional)
        order = [7 + i * 0.5 for i in range(2*(21-7))]
        g = sns.catplot(data=available, x='time', y='value', col='restriction', row='date', 
                        kind='bar', order=order, height=1.8, aspect=2.0) 
        (g.set_axis_labels('','').set_titles('{col_name}|{row_name}'))
        # g.set_xticklabels(rotation=90)  
        g.fig.subplots_adjust(hspace=.5) 
        for ax in g.axes.flat:                
            ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True)) 
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True)) 
            ax.xaxis.set_major_locator(ticker.MultipleLocator(2)) 
            ax.tick_params(labelbottom=True, labelsize='xx-small')
            title = ax.get_title().upper().split('|')
            aux   = title[1].split('-')
            ax.set_title('{} ({}/{}/{})'.format(title[0], aux[2], aux[1], aux[0]), fontsize='small')   
            ax.grid(axis='y', linewidth=1, color='#000000', alpha=0.2)
        st.pyplot(g)


    elif state.page == 'Relatório':

        if len(period) == 2:
            inicio = datetime.combine(period[0], ttime.min)
            fim    = datetime.combine(period[1], ttime.max)
        else:
            inicio = datetime.combine(period[0], ttime.min)
            fim    = datetime.combine(period[0], ttime.max)
        st.subheader('Período de {} a {}'.format(datetime.strftime(inicio, '%d/%m/%Y'), datetime.strftime(fim, '%d/%m/%Y')))
        report = agenda.loc[(agenda.id_usuario.isin(professional))].copy()
        report = report.loc[(report.inicio>=inicio)&(report.fim<=fim)]
        report['vl_real'] = 0
        report['vl_comissao'] = 0
        report['pct'] = 0
        report['tp'] = ''
        report['fmt'] = ''
        report['cancelado'] = False
        report['processado'] = False
        for i, row in report.iterrows():
            file_name = os.path.join(PROCESSED, "{}.json".format(row['id']))
            if os.path.isfile(file_name):
                curr_content = json.loads(load_file(file_name))
                if not "cancelado" in curr_content.keys():
                    curr_content.update({"cancelado": False})
                report.loc[i, 'vl_real']     = curr_content['vl_total']
                report.loc[i, 'vl_comissao'] = curr_content['vl_comissao']
                report.loc[i, 'pct']         = curr_content['pct']
                report.loc[i, 'tp']          = curr_content['tp']
                report.loc[i, 'fmt']         = curr_content['fmt']
                report.loc[i, 'cancelado']   = curr_content['cancelado']
                report.loc[i, 'processado']  = True
        results = prepare_report(report, 'profissional', 'vl_real', False)
        if len(results) > 0:
            st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
            for i, row in results.iterrows():
                with st.beta_container():
                    prof, vlb, vlc, ag, proc, canc = st.beta_columns((2,1,1,1,1,1))
                    prof.success('**Profissional**  \n{}'.format(i))
                    vlb.success('**Faturamento**  \nR$ {:.2f}'.format(row['Valor Total']))
                    vlc.success('**Comissão**  \nR$ {:.2f}'.format(row['Valor Comissão']))
                    ag.success('**Agendamentos**  \n{:.0f}'.format(row['Agendamentos']))
                    proc.success('**Processado**  \n{:.2f} %'.format(100*row['Processados']/row['Agendamentos']))
                    canc.success('**Cancelados**  \n{:.2f} %'.format(row['% Cancelamentos']))
            st.subheader('Melhores clientes')
            st.table(prepare_report(report, 'paciente', 'vl_comissao', False).head(10))
            st.subheader('Procedimentos mais executados')
            st.table(prepare_report(report, 'descproc', 'id', False).head(10))  
            st.subheader('Comissão por tipo')
            st.table(prepare_report(report, 'tp', 'id', False))  
            st.subheader('Atendimentos')
            report.rename(columns={'inicio':'Data','paciente':'Paciente','descproc':'Procedimentos',
                                    'vl_comissao':'Comissão'}, inplace=True)      
            report.Data = report.Data.apply(lambda x: datetime.strftime(x, '%d/%m/%Y %H:%M'))
            report.set_index(pd.Index([i for i in range(1, len(report)+1)]), drop=True, inplace=True)
            st.write(report.loc[report.cancelado==0][['Data','Paciente','Procedimentos','Comissão']]) 
            # st.table(report.loc[report.cancelado==0][['Data','Paciente','Procedimentos','Comissão']])        


    with st.sidebar:
        if state.authorized:
            st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
            st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
            st.markdown("<div class='spacediv'></div>", unsafe_allow_html=True)
            if st.button('Desconectar'):
                disconnect_database()



 












