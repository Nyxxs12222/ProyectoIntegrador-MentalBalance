from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app import mysql
import re
import os
import json
import pathlib
import requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
from pathlib import Path
import jwt
from functools import wraps
from colorama import Fore, Style

SECRET_KEY = 'pswd'
ALGORITHM = 'HS256'

auth_bp = Blueprint('auth', __name__)


#------------------configuracion de token de seguridad con decoradores---------#
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = session.get('access_token')
        if not token:
            return jsonify({'Mensaje': 'Token de acceso requerido'}), 401

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            session['user_id'] = payload['sub']
            
            if 'google_id' in payload:
                session['google_id'] = payload['google_id']  # Almacenar en la sesión si lo necesitas

        except jwt.ExpiredSignatureError:
            return jsonify({'Mensaje': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'Mensaje': 'Token inválido'}), 401

        return f(*args, **kwargs)

    return decorated

# Solo para desarrollo - quitar en producción
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

BASE_DIR = Path(__file__).resolve().parent.parent.parent
google_client_id = "943817268512-n52mktn5vi475ajn5qv450cd74kgq4s1.apps.googleusercontent.com"
client_secrets_file = os.path.join(BASE_DIR, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", 
            "https://www.googleapis.com/auth/userinfo.email", 
            "openid"],
    redirect_uri="http://127.0.0.1:8090/callback"
)

@auth_bp.route('/login/google')
def google_login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)

@auth_bp.route('/callback')
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session.get("state") == request.args.get("state"):
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=google_client_id,
        clock_skew_in_seconds=60
    )
    
    email = id_info.get("email")
    name = id_info.get("name")
    google_id = id_info.get("sub")
    
    try:
        flash(f'¡Bienvenido/a {name}! Has iniciado sesión con Google.', 'success')
        
        print(f"Google ID: {google_id}")
        print(f"Email: {email}")
        print(f"Name: {name}")

        partes = name.split(' ')
        nombre = partes[0]
        apellido = ' '.join(partes[1:]) if len(partes) > 1 else ''  

        usuario_json_google = {
            "google_id": google_id,
            "email": email,
            "nombre": nombre,
            "apellido": apellido,
            "password": ""
        }

        url = "http://127.0.0.1:9080/Iniciar_Sesion_Google/"
        headers = {'Content-Type': 'application/json'}
        
        response = requests.post(url, json=usuario_json_google, headers=headers)
        
        # Verificar si la respuesta es exitosa (código 200)
        #aqio se valido el usuario
        if response.status_code == 200:
            session['access_token'] = response.json().get('access_token')
            session['google_id'] = google_id
            session['user_email'] = email
            session['user_name'] = f"{nombre} {apellido}"

            print(Fore.BLUE + "Usuario JSON: " + str(usuario_json_google) + Style.RESET_ALL)
            return redirect(url_for('general.inicio'))
        
        
        # Verificar si la respuesta es exitosa (código 201)
        #aqio se vcreo un nuevo usuario
        elif response.status_code == 201:
            session['access_token'] = response.json().get('access_token')
            session['google_id'] = google_id
            session['user_email'] = email
            session['user_name'] = f"{nombre} {apellido}"

            print(Fore.BLUE + "Usuario JSON: " + str(usuario_json_google) + Style.RESET_ALL)
            return redirect(url_for('general.inicio'))

    except Exception as e:
        flash(f'Error durante el login con Google: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))
    
    return redirect(url_for('general.inicio'))

@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form['first_name'].strip()
        apellido = request.form['last_name'].strip()
        email = request.form['email'].lower().strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        accept_terms = request.form.get('accept_terms') == 'on'

        # Validaciones
        if not all([nombre, apellido, email, password, confirm_password]):
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(request.url)

        if not accept_terms:
            flash('Debes aceptar terminos y condiciones', 'danger')
            return redirect(request.url)

        if password != confirm_password:
            flash('Contrasenas no coinciden', 'danger')
            return redirect(request.url)

        if len(password) < 8:
            flash('Contrasena debe ser mayor de 8 caracteres', 'danger')
            return redirect(request.url)

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Email no valido', 'danger')
            return redirect(request.url)

        especialista_data_u = {
            "nombre": nombre,
            "apellido": apellido,
            "email": email,
            "password": password,
        }

        
        especialista_json_u = json.dumps(especialista_data_u)
        print(especialista_json_u)
        # Enviar datos a FastAPI
        try:
            url = "http://127.0.0.1:9080/Crear_Usuario/"  
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, data=especialista_json_u, headers=headers)

            if response.status_code == 200:
                flash('Registro exitoso', 'success')
            else:
                flash(f'Error en la API: {response.text}', 'danger')

        except requests.exceptions.RequestException as e:
            flash(f'Error al conectar con la API: {str(e)}', 'danger')

        except Exception as e:
            mysql.connection.rollback()
            return jsonify({'Mensaje': 'Error en el servidor: ' + str(e)}), 500

    return render_template('auth/registro.html')

@auth_bp.route('/registroEspecialista', methods=['GET', 'POST'])
def registro_especialista():
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form['first_name'].strip()
        apellido = request.form['last_name'].strip()
        email = request.form['email'].lower().strip()
        genero = request.form['gender']
        licencia = request.form['license'].strip()
        especialidad = request.form['specialization']
        años_experiencia = request.form['experience']
        password = request.form['password']
        precio = int(request.form['precio'])
        confirm_password = request.form['confirm_password']
        accept_terms = request.form.get('accept_terms') == 'on'

        # Validaciones
        if not all([nombre, apellido, email, genero, licencia, especialidad, años_experiencia, password, confirm_password]):
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('auth.registro_especialista'))

        if not accept_terms:
            flash('Debes aceptar el código de ética profesional', 'danger')
            return redirect(url_for('auth.registro_especialista'))

        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'danger')
            return redirect(url_for('auth.registro_especialista'))

        if len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres', 'danger')
            return redirect(url_for('auth.registro_especialista'))

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Email no válido', 'danger')
            return redirect(url_for('auth.registro_especialista'))

        # Crear diccionario JSON
        especialista_data = {
            "nombre": nombre,
            "apellido": apellido,
            "email": email,
            "genero": genero,
            "licencia": licencia,
            "password": password,   
            "especialidad": especialidad,
            "años_experiencia": años_experiencia,
            "precio": precio
        }

        
        especialista_json = json.dumps(especialista_data)
        print(especialista_json)
        # Enviar datos a FastAPI
        try:
            url = "http://127.0.0.1:9080/Crear_Esp/"  
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, data=especialista_json, headers=headers)

            if response.status_code == 200:
                flash('Registro exitoso', 'success')
            else:
                flash(f'Error en la API: {response.text}', 'danger')

        except requests.exceptions.RequestException as e:
            flash(f'Error al conectar con la API: {str(e)}', 'danger')

    return render_template('auth/registroEspecialista.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['username'].lower().strip()
        password = request.form['password']

        try:
            response = requests.post('http://127.0.0.1:9080/Iniciar_Sesion/', 
                                     json={"email": email, "password": password})
            if response.status_code == 200:
                datos_devueltos = response.json()

                session['access_token'] = datos_devueltos['access_token']
                session['token_type'] = datos_devueltos['token_type']
                
                
                flash(f'Bienvenid@!', 'success')
                return redirect(url_for('general.inicio'))
            else:
                error_message = response.json().get('Mensaje', 'Correo incorrecto')
                flash(f'Error: {error_message}', 'danger')  
                return redirect(url_for('auth.login'))
            
        except requests.exceptions.RequestException as e:
            print(f"Error en la conexión: {str(e)}")
            flash('Hubo un problema con la conexión. Intenta más tarde.', 'danger')
            return redirect(url_for('auth.login'))
  
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('general.inicio'))