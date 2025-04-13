import streamlit as st
import pandas as pd
import re
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Configuración de la página
st.set_page_config(page_title="Gestor de Sugerencias Musicales", page_icon="🎵", layout="wide")

# Configuración de Google Sheets
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_name('config/credentials.json', SCOPE)
client = gspread.authorize(CREDS)

# Función para obtener la hoja de cálculo
def get_worksheet(sheet_name):
    try:
        return client.open("sugerencias").worksheet(sheet_name)
    except Exception as e:
        st.error(f"Error al acceder a la hoja de cálculo: {e}")
        return None

# Función para extraer el ID de YouTube de una URL
def extract_youtube_id(url):
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    
    youtube_regex_match = re.match(youtube_regex, url)
    if youtube_regex_match:
        return youtube_regex_match.group(6)
    
    if 'youtu.be' in url:
        parsed_url = urlparse(url)
        return parsed_url.path.lstrip('/')
    
    parsed_url = urlparse(url)
    if parsed_url.hostname in ('youtu.be', 'www.youtu.be', 'youtube.com', 'www.youtube.com'):
        if 'v' in parse_qs(parsed_url.query):
            return parse_qs(parsed_url.query)['v'][0]
    
    return None

# Función para obtener información básica del video
def get_video_info(video_id):
    try:
        if video_id and len(video_id) == 11:
            return {
                "id": video_id,
                "title": f"Video {video_id[:4]}...",  # Título simulado
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/0.jpg"
            }
    except Exception as e:
        st.error(f"Error al obtener información del video: {e}")
    
    return None

# Funciones para manejar usuarios
def load_users():
    worksheet = get_worksheet('Usuarios')
    if worksheet:
        data = worksheet.get_all_records()
        return {user['usuario']: user for user in data}
    return {}

def save_users(users):
    worksheet = get_worksheet('Usuarios')
    if worksheet:
        worksheet.clear()
        worksheet.append_row(['usuario', 'password', 'nombre', 'rol'])  # Encabezados
        for username, info in users.items():
            worksheet.append_row([username, info['password'], info['nombre'], info['rol']])
        return True
    return False

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_credentials(username, password):
    users = load_users()
    if username in users and users[username]["password"] == hash_password(password):
        return True
    return False

def get_user_info(username):
    users = load_users()
    return users.get(username, {})

def change_password(username, new_password):
    users = load_users()
    if username in users:
        users[username]["password"] = hash_password(new_password)
        return save_users(users)
    return False

def reset_password(username, new_password):
    return change_password(username, new_password)

# Funciones para manejar canciones
def load_data():
    worksheet = get_worksheet('Canciones')
    if worksheet:
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    return pd.DataFrame(columns=['youtube_id', 'url', 'titulo_cancion', 'artista', 'genero', 'dificultad', 'sugerido_por', 'fecha_sugerencia', 'notas', 'votos_count'])

def save_data(df):
    worksheet = get_worksheet('Canciones')
    if worksheet:
        worksheet.clear()
        worksheet.append_row(df.columns.tolist())  # Encabezados
        for index, row in df.iterrows():
            worksheet.append_row(row.tolist())
        return True
    return False

def video_exists(video_id, data):
    return video_id in data['youtube_id'].values

# Funciones para manejar votos
def load_votes():
    worksheet = get_worksheet('Votos')
    if worksheet:
        data = worksheet.get_all_records()
        return {vote['youtube_id']: {vote['usuario']: vote['voto']} for vote in data}
    return {}

def save_votes(votes):
    worksheet = get_worksheet('Votos')
    if worksheet:
        worksheet.clear()
        worksheet.append_row(['youtube_id', 'usuario', 'voto'])  # Encabezados
        for youtube_id, user_votes in votes.items():
            for user, vote in user_votes.items():
                worksheet.append_row([youtube_id, user, vote])
        return True
    return False

def vote_song(youtube_id, username, vote_value=True):
    votes = load_votes()
    if youtube_id not in votes:
        votes[youtube_id] = {}
    votes[youtube_id][username] = vote_value
    
    if save_votes(votes):
        update_vote_counts()
        return True
    return False

def get_vote_count(youtube_id):
    votes = load_votes()
    if youtube_id not in votes:
        return 0
    return sum(1 for v in votes[youtube_id].values() if v)

def user_has_voted(youtube_id, username):
    votes = load_votes()
    if youtube_id not in votes:
        return False
    return username in votes[youtube_id] and votes[youtube_id][username]

def update_vote_counts():
    data = load_data()
    votes = load_votes()
    
    if 'votos_count' not in data.columns:
        data['votos_count'] = 0
    
    for i, row in data.iterrows():
        youtube_id = row['youtube_id']
        if youtube_id in votes:
            data.at[i, 'votos_count'] = sum(1 for v in votes[youtube_id].values() if v)
        else:
            data.at[i, 'votos_count'] = 0
    
    save_data(data)

# Función para la página de inicio de sesión
def login_page():
    st.title("🎵 Gestor de Sugerencias Musicales")
    st.header("Iniciar Sesión")
    
    login_col1, login_col2 = st.columns([1, 1])
    
    with login_col1:
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Iniciar Sesión")
            
            if submitted:
                if check_credentials(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.user_info = get_user_info(username)
                    st.experimental_rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")
        
        st.markdown("---")
        st.markdown("¿Olvidaste tu contraseña? Contacta al administrador para restablecerla.")
    
    with login_col2:
        st.info("Si eres miembro del grupo y no tienes cuenta, contacta al administrador para que te registre.")

# Función para cambiar contraseña del usuario
def change_password_page():
    st.header("Cambiar Contraseña")
    
    with st.form("change_password_form"):
        current_password = st.text_input("Contraseña Actual", type="password")
        new_password = st.text_input("Nueva Contraseña", type="password")
        confirm_password = st.text_input("Confirmar Nueva Contraseña", type="password")
        
        submitted = st.form_submit_button("Cambiar Contraseña")
        
        if submitted:
            username = st.session_state.username
            
            if not check_credentials(username, current_password):
                st.error("La contraseña actual es incorrecta")
            elif new_password != confirm_password:
                st.error("Las nuevas contraseñas no coinciden")
            elif not new_password:
                st.error("La nueva contraseña no puede estar vacía")
            else:
                if change_password(username, new_password):
                    st.success("Contraseña cambiada correctamente")
                    st.session_state.user_info = get_user_info(username)
                else:
                    st.error("Error al cambiar la contraseña")

# Función para la página de administración de usuarios
def admin_page():
    st.title("Administración de Usuarios")
    
    users = load_users()
    
    st.header("Usuarios Registrados")
    
    user_df = pd.DataFrame([
        {"Usuario": username, "Nombre": info["nombre"], "Rol": info["rol"]}
        for username, info in users.items()
    ])
    
    st.table(user_df)
    
    st.header("Agregar Nuevo Usuario")
    
    with st.form("new_user_form"):
        new_username = st.text_input("Nombre de Usuario")
        new_password = st.text_input("Contraseña", type="password")
        new_nombre = st.text_input("Nombre Completo")
        new_rol = st.selectbox("Rol", ["miembro", "admin"])
        
        submit_new_user = st.form_submit_button("Registrar Usuario")
        
        if submit_new_user:
            if new_username in users:
                st.error("Este nombre de usuario ya está en uso")
            elif not new_username or not new_password or not new_nombre:
                st.error("Todos los campos son requeridos")
            else:
                users[new_username] = {
                    "password": hash_password(new_password),
                    "nombre": new_nombre,
                    "rol": new_rol
                }
                if save_users(users):
                    st.success(f"Usuario {new_username} registrado correctamente")
                    st.experimental_rerun()
                else:
                    st.error("Error al guardar el nuevo usuario")
    
    st.header("Restablecer Contraseña de Usuario")
    
    with st.form("reset_password_form"):
        username_to_reset = st.selectbox("Seleccionar Usuario", list(users.keys()))
        new_password_reset = st.text_input("Nueva Contraseña", type="password", key="reset_pwd")
        confirm_reset = st.text_input("Confirmar Nueva Contraseña", type="password", key="confirm_reset")
        
        submit_reset = st.form_submit_button("Restablecer Contraseña")
        
        if submit_reset:
            if not new_password_reset:
                st.error("La nueva contraseña no puede estar vacía")
            elif new_password_reset != confirm_reset:
                st.error("Las contraseñas no coinciden")
            else:
                if reset_password(username_to_reset, new_password_reset):
                    st.success(f"Contraseña del usuario {username_to_reset} restablecida correctamente")
                else:
                    st.error("Error al restablecer la contraseña")

# Función para la aplicación principal
def main_app():
    st.title("🎵 Gestor de Sugerencias Musicales")
    st.markdown(f"Bienvenido, {st.session_state.user_info['nombre']} | "
                f"[Cerrar Sesión](javascript:sessionStorage.clear();location.reload())")
    
    tabs = ["Nueva Sugerencia", "Ver Sugerencias", "Estadísticas", "Mi Cuenta"]
    
    if st.session_state.user_info.get("rol") == "admin":
        tabs.append("Administración")
    
    tab_selection = st.tabs(tabs)
    
    # Pestaña 1: Nueva Sugerencia
    with tab_selection[0]:
        st.header("Añadir Nueva Sugerencia")
        
        data = load_data()
        
        with st.form("nueva_sugerencia"):
            youtube_url = st.text_input("URL de YouTube:")
            titulo_cancion = st.text_input("Título de la Canción:")
            artista = st.text_input("Artista:")
            
            col1, col2 = st.columns(2)
            with col1:
                genero = st.selectbox("Género:", ["Rock", "Pop", "Metal", "Jazz", "Electrónica", "Folk", "Otro"])
                dificultad = st.select_slider("Dificultad estimada:", options=["Fácil", "Intermedia", "Difícil", "Muy difícil"])
            
            with col2:
                sugerido_por = st.session_state.user_info['nombre']
                st.write(f"Sugerido por: {sugerido_por}")
                notas = st.text_area("Notas adicionales:", height=100)
            
            submitted = st.form_submit_button("Enviar Sugerencia")
            
            if submitted:
                if not youtube_url:
                    st.error("Por favor, ingresa la URL de YouTube.")
                else:
                    video_id = extract_youtube_id(youtube_url)
                    
                    if not video_id:
                        st.error("URL de YouTube no válida. Por favor, verifica e intenta de nuevo.")
                    elif video_exists(video_id, data):
                        st.error("¡Esta canción ya ha sido sugerida! Revisa la lista de sugerencias existentes.")
                    else:
                        video_info = get_video_info(video_id)
                        
                        if not video_info:
                            st.error("No se pudo obtener información del video. Verifica la URL.")
                        else:
                            if not titulo_cancion:
                                titulo_cancion = video_info["title"]
                            
                            nueva_sugerencia = {
                                'youtube_id': video_id,
                                'url': youtube_url,
                                'titulo_cancion': titulo_cancion,
                                'artista': artista,
                                'genero': genero,
                                'dificultad': dificultad,
                                'sugerido_por': sugerido_por,
                                'fecha_sugerencia': datetime.now().strftime('%Y-%m-%d'),
                                'notas': notas,
                                'votos_count': 0
                            }
                            
                            data = pd.concat([data, pd.DataFrame([nueva_sugerencia])], ignore_index=True)
                            if save_data(data):
                                st.success("¡Sugerencia añadida correctamente!")
                                st.balloons()
                            else:
                                st.error("Error al guardar la sugerencia")
    
    # Pestaña 2: Ver Sugerencias
    with tab_selection[1]:
        st.header("Canciones Sugeridas")
        
        data = load_data()
        update_vote_counts()  # Actualizar conteo de votos
        
        if data.empty:
            st.info("Aún no hay sugerencias de canciones.")
        else:
            st.subheader("Filtros")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                filtro_genero = st.multiselect("Filtrar por género:", ["Todos"] + sorted(data['genero'].unique().tolist()))
            
            with col2:
                filtro_dificultad = st.multiselect("Filtrar por dificultad:", ["Todos"] + sorted(data['dificultad'].unique().tolist()))
            
            with col3:
                filtro_persona = st.multiselect("Filtrar por persona:", ["Todos"] + sorted(data['sugerido_por'].unique().tolist()))
            
            with col4:
                orden = st.selectbox("Ordenar por:", ["Más recientes", "Más antiguas", "Más votadas", "Título"])
            
            data_filtrada = data.copy()
            
            if filtro_genero and "Todos" not in filtro_genero:
                data_filtrada = data_filtrada[data_filtrada['genero'].isin(filtro_genero)]
            
            if filtro_dificultad and "Todos" not in filtro_dificultad:
                data_filtrada = data_filtrada[data_filtrada['dificultad'].isin(filtro_dificultad)]
            
            if filtro_persona and "Todos" not in filtro_persona:
                data_filtrada = data_filtrada[data_filtrada['sugerido_por'].isin(filtro_persona)]
            
            if orden == "Más recientes":
                data_filtrada = data_filtrada.sort_values('fecha_sugerencia', ascending=False)
            elif orden == "Más antiguas":
                data_filtrada = data_filtrada.sort_values('fecha_sugerencia', ascending=True)
            elif orden == "Más votadas":
                if 'votos_count' in data_filtrada.columns:
                    data_filtrada = data_filtrada.sort_values('votos_count', ascending=False)
            elif orden == "Título":
                data_filtrada = data_filtrada.sort_values('titulo_cancion', ascending=True)
            
            st.subheader(f"Mostrando {len(data_filtrada)} sugerencias")
            
            num_cols = 3
            cols = st.columns(num_cols)
            
            for i, (idx, row) in enumerate(data_filtrada.iterrows()):
                col = cols[i % num_cols]
                
                with col:
                    st.markdown("---")
                    video_id = row['youtube_id']
                    
                    st.markdown(f"[![Miniatura](https://img.youtube.com/vi/{video_id}/0.jpg)](https://www.youtube.com/watch?v={video_id})")
                    
                    st.markdown(f"**{row['titulo_cancion']}**")
                    st.markdown(f"Artista: {row['artista']}")
                    st.markdown(f"Género: {row['genero']} | Dificultad: {row['dificultad']}")
                    st.markdown(f"**👤 Sugerido por:** {row['sugerido_por']} ({row['fecha_sugerencia']})")
                    
                    votos = row.get('votos_count', 0)
                    st.markdown(f"👍 **{votos}** me gusta")
                    
                    username = st.session_state.username
                    already_voted = user_has_voted(video_id, username)
                    
                    if already_voted:
                        if st.button(f"Quitar me gusta 👎", key=f"vote_{video_id}"):
                            if vote_song(video_id, username, False):
                                st.experimental_rerun()
                    else:
                        if st.button(f"Me gusta 👍", key=f"vote_{video_id}"):
                            if vote_song(video_id, username, True):
                                st.experimental_rerun()
                    
                    if row['notas']:
                        with st.expander("Notas"):
                            st.write(row['notas'])
                    
                    st.markdown(f"[Ver en YouTube](https://www.youtube.com/watch?v={video_id})")
    
    # Pestaña 3: Estadísticas
    with tab_selection[2]:
        st.header("Estadísticas")
        
        data = load_data()
        
        if data.empty:
            st.info("No hay datos suficientes para mostrar estadísticas.")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Canciones por Género")
                genero_counts = data['genero'].value_counts()
                st.bar_chart(genero_counts)
            
            with col2:
                st.subheader("Canciones por Dificultad")
                dificultad_orden = {"Fácil": 1, "Intermedia": 2, "Difícil": 3, "Muy difícil": 4}
                dificultad_counts = data['dificultad'].value_counts().sort_index(key=lambda x: x.map(dificultad_orden))
                st.bar_chart(dificultad_counts)
            
            if 'votos_count' in data.columns:
                st.subheader("Top Canciones Más Populares")
                top_songs = data.sort_values('votos_count', ascending=False)[['titulo_cancion', 'artista', 'votos_count']].head(5)
                top_songs.columns = ['Canción', 'Artista', 'Votos']
                st.table(top_songs)
            
            st.subheader("Top Contribuyentes")
            contribuyentes = data['sugerido_por'].value_counts().reset_index()
            contribuyentes.columns = ['Persona', 'Canciones Sugeridas']
            st.table(contribuyentes.head(5))
            
            st.subheader("Sugerencias Recientes")
            recientes = data.sort_values('fecha_sugerencia', ascending=False)[['fecha_sugerencia', 'titulo_cancion', 'artista', 'sugerido_por']].head(5)
            st.table(recientes)
    
    # Pestaña 4: Mi Cuenta
    with tab_selection[3]:
        st.header("Mi Cuenta")
        
        st.subheader("Información de Usuario")
        st.write(f"**Usuario:** {st.session_state.username}")
        st.write(f"**Nombre:** {st.session_state.user_info['nombre']}")
        st.write(f"**Rol:** {st.session_state.user_info['rol']}")
        
        st.subheader("Cambiar Contraseña")
        change_password_page()
        
        st.subheader("Mis Sugerencias")
        
        data = load_data()
        user_suggestions = data[data['sugerido_por'] == st.session_state.user_info['nombre']]
        
        if user_suggestions.empty:
            st.info("Aún no has sugerido ninguna canción.")
        else:
            st.write(f"Has sugerido {len(user_suggestions)} canciones.")
            
            for _, row in user_suggestions.iterrows():
                with st.expander(f"{row['titulo_cancion']} - {row['artista']}"):
                    st.write(f"**Género:** {row['genero']}")
                    st.write(f"**Dificultad:** {row['dificultad']}")
                    st.write(f"**Fecha de sugerencia:** {row['fecha_sugerencia']}")
                    if 'votos_count' in row:
                        st.write(f"**Votos:** {row['votos_count']}")
                    if row['notas']:
                        st.write(f"**Notas:** {row['notas']}")
                    st.markdown(f"[Ver en YouTube](https://www.youtube.com/watch?v={row['youtube_id']})")
    
    # Pestaña 5: Administración (solo para admins)
    if st.session_state.user_info.get("rol") == "admin" and len(tab_selection) > 4:
        with tab_selection[4]:
            admin_page()

# Verificar estado de inicio de sesión
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Mostrar la página correspondiente
if st.session_state.logged_in:
    main_app()
else:
    login_page()

# Pie de página
st.markdown("---")
st.markdown("Desarrollado con ❤️ para nuestro grupo P27 | © 2025")
