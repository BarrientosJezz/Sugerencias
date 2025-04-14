import streamlit as st
import pandas as pd
import re
import json
import hashlib
import base64
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import io

# Configuración de la página
st.set_page_config(page_title="Gestor de Sugerencias Musicales", page_icon="🎵", layout="wide")

# Configuración de GitHub - Estos valores deben estar en tu archivo secrets.toml
if 'github' not in st.secrets:
    st.error("Se requiere configuración de GitHub en secrets.toml")
    st.stop()

GITHUB_TOKEN = st.secrets["github"]["token"]
GITHUB_REPO = st.secrets["github"]["repo"]
GITHUB_OWNER = st.secrets["github"]["owner"]
GITHUB_BRANCH = st.secrets.get("github", {}).get("branch", "main")

# Función para extraer el ID de YouTube de una URL
def extract_youtube_id(url):
    # Patrones comunes de URLs de YouTube
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    
    youtube_regex_match = re.match(youtube_regex, url)
    if youtube_regex_match:
        return youtube_regex_match.group(6)
    
    # Para URLs acortadas (youtu.be)
    if 'youtu.be' in url:
        parsed_url = urlparse(url)
        return parsed_url.path.lstrip('/')
    
    # Para URLs normales (youtube.com/watch?v=)
    parsed_url = urlparse(url)
    if parsed_url.hostname in ('youtu.be', 'www.youtu.be', 'youtube.com', 'www.youtube.com'):
        if 'v' in parse_qs(parsed_url.query):
            return parse_qs(parsed_url.query)['v'][0]
    
    return None

# Función para obtener información básica del video
def get_video_info(video_id):
    # En una implementación real se usaría la API de YouTube
    # Implementación simulada para el ejemplo
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

# Funciones para manejar GitHub como almacenamiento
def get_github_file(file_path):
    """Obtiene el contenido de un archivo desde GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{file_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    params = {"ref": GITHUB_BRANCH}
    
    try:
        # Establecer un timeout para evitar esperas infinitas
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            content = response.json()
            file_content = base64.b64decode(content["content"]).decode("utf-8")
            return file_content, content["sha"]
        elif response.status_code == 404:
            # El archivo no existe
            st.info(f"El archivo {file_path} no existe en el repositorio. Se creará uno nuevo.")
            return None, None
        else:
            st.error(f"Error al obtener archivo de GitHub: {response.status_code} - {response.text}")
            return None, None
    except requests.exceptions.Timeout:
        st.error("Tiempo de espera agotado al conectar con GitHub. Verifica tu conexión a internet.")
        return None, None
    except Exception as e:
        st.error(f"Error inesperado al obtener archivo de GitHub: {str(e)}")
        return None, None

def update_github_file(file_path, content, sha=None, commit_message=None):
    """Actualiza o crea un archivo en GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{file_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    if not commit_message:
        commit_message = f"Actualización automática de {file_path}"
    
    data = {
        "message": commit_message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": GITHUB_BRANCH
    }
    
    # Si no se proporciona SHA, intentar obtenerlo primero
    if sha is None:
        try:
            # Verificar si el archivo existe y obtener su SHA
            check_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{file_path}"
            check_response = requests.get(check_url, headers=headers, params={"ref": GITHUB_BRANCH})
            
            if check_response.status_code == 200:
                # El archivo existe, obtener el SHA
                existing_file = check_response.json()
                sha = existing_file["sha"]
                data["sha"] = sha
            elif check_response.status_code != 404:
                # Si no es 404 (archivo no encontrado), hay un error diferente
                st.error(f"Error al verificar archivo: {check_response.status_code} - {check_response.text}")
                return False
            # Si es 404, el archivo no existe y es correcto no incluir SHA
        except Exception as e:
            st.error(f"Error al verificar SHA del archivo: {e}")
            return False
    else:
        data["sha"] = sha
    
    try:
        response = requests.put(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            return True
        else:
            details = {}
            try:
                details = response.json()
            except:
                details = {"text": response.text}
            
            error_msg = f"Error al actualizar archivo en GitHub: {response.status_code}"
            if details:
                error_msg += f"\nDetalles: {details}"
            
            st.error(error_msg)
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Error de conexión: {e}")
        return False

# Verificar configuración de GitHub
if 'github' not in st.secrets:
    st.error("No se encontró la configuración de GitHub en secrets.toml")
    st.stop()

GITHUB_TOKEN = st.secrets["github"]["token"]
GITHUB_REPO = st.secrets["github"]["repo"]
GITHUB_OWNER = st.secrets["github"]["owner"]
GITHUB_BRANCH = st.secrets.get("github", {}).get("branch", "main")

# Verificar que los valores no estén vacíos
if not GITHUB_TOKEN or not GITHUB_REPO or not GITHUB_OWNER:
    st.error("Configuración de GitHub incompleta en secrets.toml")
    st.write("Por favor, verifica los siguientes valores:")
    if not GITHUB_TOKEN:
        st.write("- Token de GitHub")
    if not GITHUB_REPO:
        st.write("- Nombre del repositorio")
    if not GITHUB_OWNER:
        st.write("- Nombre del propietario")
    st.stop()

# Verificar la conexión a GitHub
test_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

try:
    response = requests.get(test_url, headers=headers)
    response.raise_for_status()
    st.success("Conexión a GitHub establecida correctamente")
except Exception as e:
    st.error(f"Error al conectar con GitHub: {e}")
    st.write("Por favor, verifica la configuración en secrets.toml")
    st.stop()

# Funciones para manejar usuarios
@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_users():
    # Intentar obtener el archivo de GitHub
    try:
        content, sha = get_github_file('usuarios.json')
        
        if content:
            users = json.loads(content)
            # Guardar el SHA para futuras actualizaciones
            st.session_state['users_sha'] = sha
            return users
        else:
            # Usuario admin por defecto
            default_users = {
                "admin": {
                    "password": hashlib.sha256("admin123".encode()).hexdigest(),
                    "nombre": "JeZz Barrientos",
                    "rol": "admin"
                }
            }
            
            # Intentar crear el archivo en GitHub, pero no reintentar si falla
            try:
                json_content = json.dumps(default_users, indent=2)
                update_github_file('usuarios.json', json_content, commit_message="Creación inicial de usuarios.json")
                # No llamar a load_users() de nuevo para evitar recursión
            except Exception as e:
                st.warning(f"No se pudo crear el archivo de usuarios en GitHub: {str(e)}")
                st.info("Usando usuarios predeterminados en memoria temporalmente")
            
            return default_users
    except Exception as e:
        st.error(f"Error al cargar usuarios: {str(e)}")
        # Devolver un conjunto predeterminado de usuarios para que la aplicación funcione
        return {
            "admin": {
                "password": hashlib.sha256("admin123".encode()).hexdigest(),
                "nombre": "Administrador",
                "rol": "admin"
            }
        }
def save_users(users):
    """Guarda el diccionario de usuarios en GitHub"""
    # Obtener el SHA del estado de sesión o establecer como None si no existe
    sha = st.session_state.get('users_sha')
    json_content = json.dumps(users, indent=2)
    
    if update_github_file('usuarios.json', json_content, sha):
        # Limpiar cache para forzar recarga en próxima llamada
        load_users.clear()
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

# Función auxiliar para crear un DataFrame vacío con la estructura correcta
def create_empty_songs_dataframe():
    return pd.DataFrame({
        'youtube_id': [],
        'url': [],
        'titulo_cancion': [],
        'artista': [],
        'genero': [],
        'dificultad': [],
        'sugerido_por': [],
        'fecha_sugerencia': [],
        'notas': [],
        'votos_count': []
    })
    
# Funciones para manejar canciones
@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_data():
    try:
        content, sha = get_github_file('canciones_sugeridas.csv')
        
        if content and sha:
            # Guardar el SHA para futuras actualizaciones
            st.session_state['canciones_sha'] = sha
            try:
                return pd.read_csv(io.StringIO(content))
            except Exception as e:
                st.error(f"Error al parsear el CSV: {str(e)}")
                # Crear un DataFrame vacío como fallback
                df = create_empty_songs_dataframe()
                return df
        else:
            # Crear DataFrame vacío
            df = create_empty_songs_dataframe()
            
            # Guardar el archivo vacío en GitHub
            csv_content = df.to_csv(index=False)
            # No proporcionar SHA para la creación inicial
            update_github_file('canciones_sugeridas.csv', csv_content, sha=None, commit_message="Creación inicial de canciones_sugeridas.csv")
            
            # Intentar cargar de nuevo después de crear
            return load_data()
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        # En caso de error, devolver un DataFrame vacío
        return create_empty_songs_dataframe()

# Función auxiliar para crear un DataFrame vacío con la estructura correcta
def create_empty_songs_dataframe():
    return pd.DataFrame({
        'youtube_id': [],
        'url': [],
        'titulo_cancion': [],
        'artista': [],
        'genero': [],
        'dificultad': [],
        'sugerido_por': [],
        'fecha_sugerencia': [],
        'notas': [],
        'votos_count': []
    })

def save_data(df):
    """Guarda el DataFrame de canciones en GitHub"""
    # Obtener el SHA del estado de sesión o establecer como None si no existe
    sha = st.session_state.get('canciones_sha')
    csv_content = df.to_csv(index=False)
    
    if update_github_file('canciones_sugeridas.csv', csv_content, sha):
        # Limpiar cache para forzar recarga en próxima llamada
        load_data.clear()
        return True
    return False

def video_exists(video_id, data):
    return video_id in data['youtube_id'].values

@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_votes():
    try:
        content, sha = get_github_file('votos.json')
        
        if content:
            try:
                votes = json.loads(content)
                # Guardar el SHA para futuras actualizaciones
                st.session_state['votos_sha'] = sha
                return votes
            except json.JSONDecodeError as e:
                st.error(f"Error al decodificar JSON de votos: {str(e)}")
                return {}
        else:
            # Crear objeto vacío
            empty_votes = {}
            
            # Guardar el archivo vacío en GitHub
            json_content = json.dumps(empty_votes, indent=2)
            update_github_file('votos.json', json_content, commit_message="Creación inicial de votos.json")
            
            return empty_votes
    except Exception as e:
        st.error(f"Error al cargar votos: {str(e)}")
        return {}

def save_votes(votes):
    """Guarda el diccionario de votos en GitHub"""
    # Obtener el SHA del estado de sesión o establecer como None si no existe
    sha = st.session_state.get('votos_sha')
    json_content = json.dumps(votes, indent=2)
    
    if update_github_file('votos.json', json_content, sha):
        # Limpiar cache para forzar recarga en próxima llamada
        load_votes.clear()
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
    
    # Asegurarse de que la columna de votos existe
    if 'votos_count' not in data.columns:
        data['votos_count'] = 0
    
    # Actualizar conteo de votos
    for i, row in data.iterrows():
        youtube_id = row['youtube_id']
        if youtube_id in votes:
            data.at[i, 'votos_count'] = sum(1 for v in votes[youtube_id].values() if v)
        else:
            data.at[i, 'votos_count'] = 0
    
    save_data(data)

# Función para la página de inicio de sesión
def login_page():
    st.title("🎵 P27 - Gestor de Sugerencias")
    st.header("Iniciar Sesión")
    
    # Verificar si hay un mensaje de redirección
    if 'show_login_message' in st.session_state and st.session_state.show_login_message:
        st.success("Inicio de sesión exitoso! Redirigiendo...")
        # Limpiar el flag después de mostrar el mensaje
        st.session_state.show_login_message = False
        # Código JavaScript para recargar después de 1 segundo
        st.markdown(
            """
            <script>
                setTimeout(function() {
                    window.location.reload();
                }, 1000);
            </script>
            """,
            unsafe_allow_html=True
        )
    
    login_col1, login_col2 = st.columns([1, 1])
    
    with login_col1:
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Iniciar Sesión")
            
            if submitted:
                if check_credentials(username, password):
                    # Actualizar estado de sesión
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.user_info = get_user_info(username)
                    st.session_state.show_login_message = True
                    st.rerun()  # Intentar rerun aquí es más seguro ahora
                else:
                    st.error("Usuario o contraseña incorrectos")
        
        # Enlace para recuperar contraseña
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
                    # Actualizar información de sesión
                    st.session_state.user_info = get_user_info(username)
                else:
                    st.error("Error al cambiar la contraseña")

# Función para la página de administración de usuarios
def admin_page():
    st.title("Administración de Usuarios")
    
    # Mostrar usuarios existentes
    users = load_users()
    
    st.header("Usuarios Registrados")
    
    user_df = pd.DataFrame([
        {"Usuario": username, "Nombre": info["nombre"], "Rol": info["rol"]}
        for username, info in users.items()
    ])
    
    st.table(user_df)
    
    # Agregar nuevo usuario
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
                    # En lugar de usar st.experimental_rerun() directamente
                    st.session_state.admin_refresh = True
                else:
                    st.error("Error al guardar el nuevo usuario")
        
        # Al inicio de la función, verificar si necesitamos recargar
        if 'admin_refresh' in st.session_state and st.session_state.admin_refresh:
            st.session_state.admin_refresh = False
            st.rerun()
    
    # Sección para restablecer contraseñas
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
    # Título y pestañas principales
    st.title("🎵 Gestor de Sugerencias Musicales")
    st.markdown(f"Bienvenido, {st.session_state.user_info['nombre']} | "
                f"[Cerrar Sesión](javascript:sessionStorage.clear();location.reload())")
    
    tabs = ["Nueva Sugerencia", "Ver Sugerencias", "Estadísticas", "Mi Cuenta"]
    
    # Si es administrador, mostrar pestaña de administración
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
                # El nombre del usuario se obtiene automáticamente
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
            # Filtros
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
            
            # Aplicar filtros
            data_filtrada = data.copy()
            
            if filtro_genero and "Todos" not in filtro_genero:
                data_filtrada = data_filtrada[data_filtrada['genero'].isin(filtro_genero)]
            
            if filtro_dificultad and "Todos" not in filtro_dificultad:
                data_filtrada = data_filtrada[data_filtrada['dificultad'].isin(filtro_dificultad)]
            
            if filtro_persona and "Todos" not in filtro_persona:
                data_filtrada = data_filtrada[data_filtrada['sugerido_por'].isin(filtro_persona)]
            
            # Aplicar ordenamiento
            if orden == "Más recientes":
                data_filtrada = data_filtrada.sort_values('fecha_sugerencia', ascending=False)
            elif orden == "Más antiguas":
                data_filtrada = data_filtrada.sort_values('fecha_sugerencia', ascending=True)
            elif orden == "Más votadas":
                if 'votos_count' in data_filtrada.columns:
                    data_filtrada = data_filtrada.sort_values('votos_count', ascending=False)
            elif orden == "Título":
                data_filtrada = data_filtrada.sort_values('titulo_cancion', ascending=True)
            
            # Mostrar resultados
            st.subheader(f"Mostrando {len(data_filtrada)} sugerencias")
            
            # Mostrar en tarjetas
            num_cols = 3
            cols = st.columns(num_cols)
            
            for i, (idx, row) in enumerate(data_filtrada.iterrows()):
                col = cols[i % num_cols]
                
                with col:
                    st.markdown("---")
                    video_id = row['youtube_id']
                    
                    # Mostrar miniatura clicable
                    st.markdown(f"[![Miniatura](https://img.youtube.com/vi/{video_id}/0.jpg)](https://www.youtube.com/watch?v={video_id})")
                    
                    # Información de la canción
                    st.markdown(f"**{row['titulo_cancion']}**")
                    st.markdown(f"Artista: {row['artista']}")
                    st.markdown(f"Género: {row['genero']} | Dificultad: {row['dificultad']}")
                    
                    # Destacar quién sugirió la canción con estilo mejorado
                    st.markdown(f"**👤 Sugerido por:** {row['sugerido_por']} ({row['fecha_sugerencia']})")
                    
                    # Sistema de votos
                    votos = row.get('votos_count', 0)
                    st.markdown(f"👍 **{votos}** me gusta")
                    
                    # Verificar si el usuario ya votó
                    username = st.session_state.username
                    already_voted = user_has_voted(video_id, username)
                    
                    # Botón para votar/quitar voto
                    if already_voted:
                        if st.button(f"Quitar me gusta 👎", key=f"vote_{video_id}"):
                            if vote_song(video_id, username, False):
                                st.rerun()
                    else:
                        if st.button(f"Me gusta 👍", key=f"vote_{video_id}"):
                            if vote_song(video_id, username, True):
                                st.rerun()
                    
                    if row['notas']:
                        with st.expander("Notas"):
                            st.write(row['notas'])
                    
                    # Botón para ver en YouTube
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
                # Gráfico de canciones por género
                st.subheader("Canciones por Género")
                genero_counts = data['genero'].value_counts()
                st.bar_chart(genero_counts)
            
            with col2:
                # Gráfico de canciones por dificultad
                st.subheader("Canciones por Dificultad")
                dificultad_orden = {"Fácil": 1, "Intermedia": 2, "Difícil": 3, "Muy difícil": 4}
                dificultad_counts = data['dificultad'].value_counts().sort_index(key=lambda x: x.map(dificultad_orden))
                st.bar_chart(dificultad_counts)
            
            # Top canciones más votadas
            if 'votos_count' in data.columns:
                st.subheader("Top Canciones Más Populares")
                top_songs = data.sort_values('votos_count', ascending=False)[['titulo_cancion', 'artista', 'votos_count']].head(5)
                top_songs.columns = ['Canción', 'Artista', 'Votos']
                st.table(top_songs)
            
            # Top contribuyentes
            st.subheader("Top Contribuyentes")
            contribuyentes = data['sugerido_por'].value_counts().reset_index()
            contribuyentes.columns = ['Persona', 'Canciones Sugeridas']
            st.table(contribuyentes.head(5))
            
            # Sugerencias recientes
            st.subheader("Sugerencias Recientes")
            recientes = data.sort_values('fecha_sugerencia', ascending=False)[['fecha_sugerencia', 'titulo_cancion', 'artista', 'sugerido_por']].head(5)
            st.table(recientes)
    
    # Pestaña 4: Mi Cuenta
    with tab_selection[3]:
        st.header("Mi Cuenta")
        
        # Mostrar información del usuario
        st.subheader("Información de Usuario")
        st.write(f"**Usuario:** {st.session_state.username}")
        st.write(f"**Nombre:** {st.session_state.user_info['nombre']}")
        st.write(f"**Rol:** {st.session_state.user_info['rol']}")
        
        # Sección para cambiar contraseña
        st.subheader("Cambiar Contraseña")
        change_password_page()
        
        # Mostrar sugerencias del usuario
        st.subheader("Mis Sugerencias")
        
        data = load_data()
        user_suggestions = data[data['sugerido_por'] == st.session_state.user_info['nombre']]
        
        if user_suggestions.empty:
            st.info("Aún no has sugerido ninguna canción.")
        else:
            st.write(f"Has sugerido {len(user_suggestions)} canciones.")
            
            # Mostrar lista de sugerencias del usuario
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
