from fastapi import  HTTPException,Depends,FastAPI,Request
from fastapi.responses import JSONResponse
from fastapi import APIRouter
from jose import jwt
from typing import List
import httpx
from datetime import datetime, timedelta
from PDT_Models.ModelEspecialista import ModelEspecialista,HorariosResponse
from PDT_Models.ModelUsuario import ModelUsuario_Google
from PDT_Models.ModelLogin import ModelLogin,ModelToken
from DB.conexion import  Session
from DB_Models.DBM_Usuarios import Usuario
from DB_Models.DBM_Especialista import Especialista
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# from PDT_Models.ModelCita import (
#     CitaCreate, CitaResponse, CitaCancel, FiltrosCitas, EspecialistaResponse
# )

# security = HTTPBearer()

SECRET_KEY = 'pswd'
ALGORITHM = 'HS256'

#-------------validar fastapi------------------
app = FastAPI(
    title='Mental Balance FastAPI',
    description='Api de fastapi que enlaza a la base de datos',
    version='0.0.1'
)


@app.get("/",tags=['Raiz'])
def main():
    return {'Hola FastAPI!':' Hola Richy'}

#----------metodos--------------

#crear token para login

def crear_token(email, google_id=None):
    expire = datetime.utcnow() + timedelta(minutes=30)
    payload = {"sub": email, "exp": expire}
    if google_id:
        payload["google_id"] = google_id
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)




# async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
#     token = credentials.credentials
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         email: str = payload.get("sub")
#         if email is None:
#             raise HTTPException(status_code=401, detail="Token inválido")
#         return email
#     except jwt.ExpiredSignatureError:
#         raise HTTPException(status_code=401, detail="Token expirado")
#     except jwt.JWTError:
#         raise HTTPException(status_code=401, detail="Token inválido")

# ---------------Crear un nuevo usuario -----------------------------
@app.post("/Crear_Usuario/", response_model=ModelUsuario_Google, tags=['Usuarios'])
def Crear_u(usuario_nuevo:ModelUsuario_Google):
    db = Session()
    try:
        
        consulta = db.query(Usuario).filter(Usuario.email == usuario_nuevo.email).first()
        if consulta:
            return JSONResponse(status_code=201,content={"Mensaje":"Correo Ya registrado"})
        
        
        if usuario_nuevo.google_id:  
            consulta2 = db.query(Usuario).filter(Usuario.google_id == usuario_nuevo.google_id).first()
            if consulta2:
                return JSONResponse(status_code=201, content={"Mensaje": "Correo ya registrado, inicia sesion "})
            
        db.add(Usuario(**usuario_nuevo.model_dump()))
        db.commit()
        return JSONResponse(status_code=200,
                             content={
                                 "Mensaje": "Usuario Guardado Correctamente",
                                 "Usuario": usuario_nuevo.model_dump()  
                             })
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500,  
                             content={
                                 "Mensaje": "Ha ocurrido un error al Guardar el usuario",
                                 "Excepcion": str(e)
                             })
    finally:
        db.close()
 
# ---------------Crear un nuevo especialista -----------------------------
@app.post("/Crear_Esp/", response_model=ModelEspecialista, tags=['Especialistas'])
def Crear_e(esp_nuevo:ModelEspecialista):
    db = Session()
    try:
      
        existe_email = db.query(Especialista).filter_by(email=esp_nuevo.email).first()
        if existe_email:
            raise HTTPException(status_code=400, detail="Ya existe un especialista con este email")

    
        existe_licencia = db.query(Especialista).filter_by(licencia=esp_nuevo.licencia).first()
        if existe_licencia:
            raise HTTPException(status_code=400, detail="Ya existe un especialista con esta licencia")

    
        nuevo_especialista = Especialista(**esp_nuevo.model_dump())
        db.add(nuevo_especialista)
        db.commit()
        db.refresh(nuevo_especialista)

        return JSONResponse(
            status_code=201,
            content={
                "Mensaje": "Especialista Guardado Correctamente",
                "Usuario": esp_nuevo.model_dump()
            }
        )
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500,  
                             content={
                                 "Mensaje": "Ha ocurrido un error al Guardar el Especialista",
                                 "Excepcion": str(e)
                             })
    finally:
        db.close()


# ---------------Iniciar sesion-----------------------------
@app.post("/Iniciar_Sesion/",response_model=ModelToken,tags=['Usuarios'])
def Iniciar_s(sesion:ModelLogin):
    db = Session()
    try:
        consulta = db.query(Usuario).filter(Usuario.email == sesion.email).first()
        if consulta:
                if consulta and consulta.password.lower() == sesion.password.lower():
                    token = crear_token(consulta.email)
                    return {'access_token': token, 'token_type': 'bearer'}
                else:
                    return JSONResponse(status_code=401, content={"Mensaje": "Contraseña Incorrecta"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"Mensaje": "Error en el servidor", "Excepcion": str(e)})
    finally:
        db.close()

#---------------------registro con google---------------------
@app.post("/Iniciar_Sesion_Google/", response_model=ModelUsuario_Google, tags=['Usuarios'])
async def Iniciar_s_google(usuario_nuevo: ModelUsuario_Google):
    db = Session()
    try:
        consulta = db.query(Usuario).filter(Usuario.email == usuario_nuevo.email).first()
         
        if consulta:
            # Si el usuario existe, verifica su google_id
            if consulta.google_id == usuario_nuevo.google_id:
                # Ya está vinculado correctamente
                token = crear_token(consulta.email)
                return JSONResponse(status_code=200, content={
                    "Mensaje": "Usuario autenticado con Google",
                    "Usuario": usuario_nuevo.model_dump(),
                    "access_token": token,
                    "token_type": "bearer"
                })
            elif consulta.google_id is None:
                # Solo actualizar si el google_id no está en uso
                existe_google = db.query(Usuario).filter(Usuario.google_id == usuario_nuevo.google_id).first()
                if existe_google:
                    return JSONResponse(status_code=400, content={
                        "Mensaje": "Este Google ID ya está vinculado a otra cuenta."
                    })

                consulta.google_id = usuario_nuevo.google_id
                db.commit()

                token = crear_token(consulta.email)
                return JSONResponse(status_code=200, content={
                    "Mensaje": "Google ID vinculado exitosamente",
                    "Usuario": usuario_nuevo.model_dump(),
                    "access_token": token,
                    "token_type": "bearer"
                })
            else:
                return JSONResponse(status_code=400, content={
                    "Mensaje": "El correo ya está vinculado a otra cuenta de Google"
                })

        else:
            # Usuario nuevo, se registra
            db.add(Usuario(**usuario_nuevo.model_dump()))
            db.commit()
            token = crear_token(usuario_nuevo.email)
            return JSONResponse(status_code=201, content={
                "Mensaje": "Usuario registrado con Google",
                "Usuario": usuario_nuevo.model_dump(),
                "access_token": token,
                "token_type": "bearer"
            })
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={
            "Mensaje": "Error durante el inicio de sesión con Google",
            "Excepcion": str(e)
        })
    finally:
        db.close()
#---------------------actualizar google id--------------------
#esto es por si un usuario registrado sin google, inicia sesion con google y se le asigna un google id
@app.put("/Actualizar_Google_ID/{email}", response_model=ModelUsuario_Google, tags=['Usuarios'])
def Actualizar_google_id(email:str, usuario_nuevo:ModelUsuario_Google):
    db = Session()
    
    try:
        usuario_existente = db.query(Usuario).filter(Usuario.google_id == usuario_nuevo.google_id).first()
        if usuario_existente:
            return JSONResponse(status_code=400, content={
                "Mensaje": "Este Google ID ya está vinculado a otro usuario."
            })
        consulta = db.query(Usuario).filter(Usuario.email == email).first()  
        if consulta:
            if consulta.google_id is None:
                consulta.google_id = usuario_nuevo.google_id
                db.commit()
                return JSONResponse(status_code=201, content={"Mensaje": "Google ID actualizado correctamente"})
            else:
                return JSONResponse(status_code=400, content={"Mensaje": "El usuario ya tiene un Google ID asignado"})
        else:
            return JSONResponse(status_code=404, content={"Mensaje": "Usuario no encontrado"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"Mensaje": "Error en el servidor", "Excepcion": str(e)})
    finally:
        db.close()

@app.delete("/Eliminar_Usuario/{id}", tags=['Usuarios'])
def Eliminar_usuario(id:int):
    db = Session()
    try:
        consulta = db.query(Usuario).filter(Usuario.id == id).first()
        if consulta:
            db.delete(consulta)
            db.commit()
            return JSONResponse(status_code=200, content={"Mensaje": "Usuario eliminado correctamente"})
        else:
            return JSONResponse(status_code=404, content={"Mensaje": "Usuario no encontrado"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"Mensaje": "Error en el servidor", "Excepcion": str(e)})
    finally:
        db.close()

# #---------------------citas-------------------------------------------
# @app.get("/catalogo-citas/", response_model=List[EspecialistaResponse], tags=['Citas'])
# async def catalogo_citas(filtros: FiltrosCitas = Depends()):
#     db = Session()
#     try:
#         query = db.query(Especialista).filter(
#             Especialista.verificado == True,
#             Especialista.precio <= filtros.precio
#         )
        
#         if filtros.especialidad:
#             query = query.filter(Especialista.especialidad == filtros.especialidad)
#         if filtros.modelo:
#             query = query.filter(Especialista.modelo_terapeutico == filtros.modelo)
#         if filtros.genero:
#             query = query.filter(Especialista.genero == filtros.genero)
            
#         especialistas = query.all()
        
#         # Obtener opciones de filtro
#         especialidades = db.query(Especialista.especialidad).distinct().all()
#         modelos = db.query(Especialista.modelo_terapeutico).distinct().all()
#         generos = db.query(Especialista.genero).distinct().all()
        
#         return JSONResponse(status_code=200, content={
#             "especialistas": [especialista.__dict__ for especialista in especialistas],
#             "filtros": {
#                 "especialidades": [e[0] for e in especialidades],
#                 "modelos": [m[0] for m in modelos],
#                 "generos": [g[0] for g in generos]
#             },
#             "today": date.today().strftime('%Y-%m-%d')
#         })
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error al obtener catálogo: {str(e)}")
#     finally:
#         db.close()

# # Endpoint para agendar una cita
# @app.post("/agendar-cita/", response_model=CitaResponse, tags=['Citas'])
# async def agendar_cita(cita: CitaCreate, email: str = Depends(get_current_user)):
#     db = Session()
#     try:
#         # Verificar si el usuario existe
#         usuario = db.query(Usuario).filter(Usuario.email == email).first()
#         if not usuario:
#             raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
#         # Verificar si el horario está disponible
#         horarios = generar_horarios_disponibles(cita.id_especialista, cita.fecha)
#         if cita.hora not in horarios.horarios_disponibles:
#             raise HTTPException(status_code=400, detail="Este horario ya está ocupado")
        
#         # Crear la cita (aquí va tu lógica para insertar en la base de datos)
#         # Ejemplo:
#         nueva_cita = CitasAgendadas(
#             id_usuario=usuario.id,
#             id_especialista=cita.id_especialista,
#             fecha=cita.fecha,
#             hora=cita.hora,
#             estado=cita.estado
#         )
#         db.add(nueva_cita)
#         db.commit()
#         db.refresh(nueva_cita)
        
#         # Obtener información del especialista para la respuesta
#         especialista = db.query(Especialista).filter(Especialista.id == cita.id_especialista).first()
        
#         return JSONResponse(status_code=201, content={
#             "id": nueva_cita.id,
#             "id_usuario": usuario.id,
#             "id_especialista": cita.id_especialista,
#             "fecha": cita.fecha.strftime('%Y-%m-%d'),
#             "hora": cita.hora,
#             "estado": cita.estado,
#             "nombre_especialista": especialista.nombre,
#             "apellido_especialista": especialista.apellido,
#             "especialidad": especialista.especialidad,
#             "precio": especialista.precio
#         })
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Error al agendar la cita: {str(e)}")
#     finally:
#         db.close()

# # Endpoint para cancelar una cita
# @app.post("/cancelar-cita/", tags=['Citas'])
# async def cancelar_cita(cita: CitaCancel, email: str = Depends(get_current_user)):
#     db = Session()
#     try:
#         # Verificar si el usuario existe
#         usuario = db.query(Usuario).filter(Usuario.email == email).first()
#         if not usuario:
#             raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
#         # Verificar si la cita existe y pertenece al usuario
#         cita_existente = db.query(CitasAgendadas).filter(
#             CitasAgendadas.id == cita.cita_id,
#             CitasAgendadas.id_usuario == usuario.id,
#             CitasAgendadas.estado == "pendiente"
#         ).first()
        
#         if not cita_existente:
#             raise HTTPException(status_code=404, detail="No puedes cancelar esta cita")
        
#         # Actualizar el estado de la cita
#         cita_existente.estado = "cancelada"
#         db.commit()
        
#         return JSONResponse(status_code=200, content={"message": "Cita cancelada exitosamente"})
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Error al cancelar la cita: {str(e)}")
#     finally:
#         db.close()

# # Endpoint para obtener las citas del usuario
# @app.get("/mis-citas/", response_model=dict, tags=['Citas'])
# async def mis_citas(email: str = Depends(get_current_user)):
#     db = Session()
#     try:
#         # Verificar si el usuario existe
#         usuario = db.query(Usuario).filter(Usuario.email == email).first()
#         if not usuario:
#             raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
#         # Obtener citas activas
#         citas_activas = db.query(
#             CitasAgendadas.id,
#             CitasAgendadas.fecha,
#             CitasAgendadas.hora,
#             CitasAgendadas.estado,
#             Especialista.nombre,
#             Especialista.apellido,
#             Especialista.especialidad,
#             Especialista.precio
#         ).join(
#             Especialista, CitasAgendadas.id_especialista == Especialista.id
#         ).filter(
#             CitasAgendadas.id_usuario == usuario.id,
#             CitasAgendadas.estado != "cancelada"
#         ).order_by(
#             CitasAgendadas.fecha,
#             CitasAgendadas.hora
#         ).all()
        
#         # Obtener historial de citas
#         historial_citas = db.query(
#             CitasAgendadas.id,
#             CitasAgendadas.fecha,
#             CitasAgendadas.hora,
#             CitasAgendadas.estado,
#             Especialista.nombre,
#             Especialista.apellido,
#             Especialista.especialidad,
#             Especialista.precio
#         ).join(
#             Especialista, CitasAgendadas.id_especialista == Especialista.id
#         ).filter(
#             CitasAgendadas.id_usuario == usuario.id,
#             CitasAgendadas.estado == "cancelada"
#         ).order_by(
#             CitasAgendadas.fecha.desc(),
#             CitasAgendadas.hora.desc()
#         ).limit(10).all()
        
#         # Convertir resultados a formato JSON
#         def format_cita(cita):
#             return {
#                 "id": cita.id,
#                 "fecha": cita.fecha.strftime('%Y-%m-%d'),
#                 "hora": str(cita.hora),
#                 "estado": cita.estado,
#                 "nombre_especialista": cita.nombre,
#                 "apellido_especialista": cita.apellido,
#                 "especialidad": cita.especialidad,
#                 "precio": float(cita.precio)
#             }
        
#         return JSONResponse(status_code=200, content={
#             "citas_activas": [format_cita(c) for c in citas_activas],
#             "historial_citas": [format_cita(c) for c in historial_citas]
#         })
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error al obtener tus citas: {str(e)}")
#     finally:
#         db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast:app", host="127.0.0.1", port=9080, reload=True)

