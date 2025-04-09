from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from app import mysql
from datetime import datetime, date, timedelta
import json
from app.routes.auth import token_required
citas_bp = Blueprint('citas', __name__)

def generar_horarios_disponibles(id_especialista, fecha):
    try:
        cur = mysql.connection.cursor()
        
        cur.execute("""
            SELECT hora FROM CitasAgendadas 
            WHERE id_especialista = %s AND fecha = %s AND estado != 'cancelada'
            UNION
            SELECT hora FROM CitasDisponibles 
            WHERE id_especialista = %s AND fecha = %s AND disponible = FALSE
        """, (id_especialista, fecha, id_especialista, fecha))
        
        horas_ocupadas = {hora['hora'].strftime('%H:%M:%S') for hora in cur.fetchall()}
        
        horarios_posibles = [
            '09:00:00', '10:00:00', '11:00:00', '12:00:00',
            '13:00:00', '14:00:00', '15:00:00', '16:00:00', '17:00:00'
        ]
        
        return [h for h in horarios_posibles if h not in horas_ocupadas]
        
    except Exception as e:
        print(f"Error generando horarios: {str(e)}")
        return []
    finally:
        cur.close()

@citas_bp.route('/catalogo-citas')
def catalogo_citas():
    cur = mysql.connection.cursor()

    filtro_especialidad = request.args.get('especialidad', '')
    filtro_modelo = request.args.get('modelo', '')
    filtro_precio = request.args.get('precio', 2000)
    filtro_genero = request.args.get('genero', '')

    query = """
        SELECT id, nombre, apellido, email, genero, licencia, especialidad, 
               años_experiencia, modelo_terapeutico, precio
        FROM especialistas 
        WHERE verificado = TRUE 
        AND precio <= %s
    """
    params = [filtro_precio]

    if filtro_especialidad:
        query += " AND especialidad = %s"
        params.append(filtro_especialidad)
    if filtro_modelo:
        query += " AND modelo_terapeutico = %s"
        params.append(filtro_modelo)
    if filtro_genero:
        query += " AND genero = %s"
        params.append(filtro_genero)

    cur.execute(query, params)
    especialistas = cur.fetchall()

    cur.execute("SELECT DISTINCT especialidad FROM especialistas")
    especialidades = [e['especialidad'] for e in cur.fetchall()]

    cur.execute("SELECT DISTINCT modelo_terapeutico FROM especialistas")
    modelos = [m['modelo_terapeutico'] for m in cur.fetchall()]

    cur.execute("SELECT DISTINCT genero FROM especialistas")
    generos = [g['genero'] for g in cur.fetchall()]

    cur.close()

    return render_template('citas/catalogo.html',
        especialidades=especialidades,
        modelos=modelos,
        generos=generos,
        especialistas=especialistas,
        filtro_precio=filtro_precio,
        user_logged_in=session.get('user_id') is not None,
        today=date.today().strftime('%Y-%m-%d')
    )

@citas_bp.route('/get-horarios/<int:especialista_id>/<fecha>')
def get_horarios(especialista_id, fecha):
    horarios = generar_horarios_disponibles(especialista_id, fecha)
    return jsonify(horarios)

@citas_bp.route('/agendar-cita', methods=['POST'])
def agendar_cita():
    if not session.get('user_id'):
        flash('Por favor inicia sesión para agendar tu cita', 'info')
        session['cita_pendiente'] = {
            'id_especialista': request.form.get('id_especialista'),
            'fecha': request.form.get('fecha'),
            'hora': request.form.get('hora')
        }
        return redirect(url_for('auth.login', next=url_for('citas.catalogo_citas')))
    
    data = request.form
    id_usuario = session['user_id']
    id_especialista = data.get('id_especialista')
    fecha = data.get('fecha')
    hora = data.get('hora')
    estado = "pendiente"

    try:
        horarios_disponibles = generar_horarios_disponibles(id_especialista, fecha)
        if hora not in horarios_disponibles:
            flash('El horario seleccionado no está disponible.', 'danger')
            return redirect(url_for('citas.catalogo_citas'))

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO CitasAgendadas (id_usuario, id_especialista, fecha, hora, estado)
            VALUES (%s, %s, %s, %s, %s)
        """, (id_usuario, id_especialista, fecha, hora, estado))
        mysql.connection.commit()
        flash('Cita agendada exitosamente.', 'success')
        return redirect(url_for('citas.mis_citas'))

    except Exception as e:
        print(f"Error al agendar cita: {str(e)}")
        flash('Hubo un error al agendar la cita.', 'danger')
        return redirect(url_for('citas.catalogo_citas'))
    finally:
        cur.close()

@citas_bp.route('/cancelar-cita/<int:cita_id>', methods=['POST'])
def cancelar_cita(cita_id):
    if not session.get('user_id'):
        flash('Debes iniciar sesión para realizar esta acción', 'danger')
        return redirect(url_for('auth.login'))

    try:
        cur = mysql.connection.cursor()
        
        cur.execute("""
            SELECT * FROM CitasAgendadas 
            WHERE id = %s AND id_usuario = %s AND estado = 'pendiente'
        """, (cita_id, session['user_id']))
        
        if not cur.fetchone():
            flash('No puedes cancelar esta cita', 'danger')
            return redirect(url_for('citas.mis_citas'))

        cur.execute("""
            UPDATE CitasAgendadas 
            SET estado = 'cancelada'
            WHERE id = %s
        """, (cita_id,))
        
        mysql.connection.commit()
        flash('Cita cancelada exitosamente', 'success')
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al cancelar la cita: {str(e)}', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('citas.mis_citas'))

@citas_bp.route('/mis-citas')
@token_required
def mis_citas():
    if not session.get('user_id'):
        flash('Debes iniciar sesión para ver tus citas', 'danger')
        return redirect(url_for('auth.login'))

    cur = mysql.connection.cursor()
    
    try:
        # Obtener citas activas
        cur.execute("""
            SELECT CA.id, CA.fecha, TIME_FORMAT(CA.hora, '%%H:%%i') as hora_str, 
                   CA.estado, E.nombre, E.apellido, E.especialidad, E.precio
            FROM CitasAgendadas CA
            JOIN especialistas E ON CA.id_especialista = E.id
            WHERE CA.id_usuario = %s AND CA.estado != 'cancelada'
            ORDER BY CA.fecha, CA.hora
        """, (session['user_id'],))
        
        citas_activas = cur.fetchall()
        
        # Obtener historial de citas
        cur.execute("""
            SELECT CA.id, CA.fecha, TIME_FORMAT(CA.hora, '%%H:%%i') as hora_str, 
                   CA.estado, E.nombre, E.apellido, E.especialidad, E.precio
            FROM CitasAgendadas CA
            JOIN especialistas E ON CA.id_especialista = E.id
            WHERE CA.id_usuario = %s AND CA.estado = 'cancelada'
            ORDER BY CA.fecha DESC, CA.hora DESC
            LIMIT 10
        """, (session['user_id'],))
        
        historial_citas = cur.fetchall()
        
        return render_template('citas/mis_citas.html', 
                             citas_activas=citas_activas,
                             historial_citas=historial_citas)
        
    except Exception as e:
        flash(f'Error al obtener tus citas: {str(e)}', 'danger')
        return redirect(url_for('general.inicio'))
    finally:
        cur.close()