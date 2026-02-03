from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
from sqlalchemy import func, and_, desc
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
from typing import List, Optional
import json

from .database import Base, engine, get_db, SessionLocal
from .models import User, Tema, Pregunta, ResultadoQuiz
from .schemas import (
    UserCreate, UserLogin, TokenResponse, UserOut, PromoteRole, UserUpdate,
    ChangePassword, ResetPassword, AdminChangePassword,
    CalificarQuizRequest, ResultadoQuizCreate
)
from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin
)

# ========================================
# HELPER FUNCTIONS
# ========================================

def require_docente_or_admin(current_user: User = Depends(get_current_user)):
    """
    Permite acceso a docentes y administradores
    """
    if current_user.role not in ["docente", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Solo docentes y administradores."
        )
    return current_user

# ========================================
# SEED FUNCTIONS
# ========================================

def seed_admin(db: Session):
    admin_email = "admin@ug.edu.ec"
    admin_password = "Admin1234"

    exists = db.query(User).filter(
        (User.correo == admin_email) | (User.nombre == "Administrador")
    ).first()
    
    if not exists:
        admin = User(
            nombre="Administrador",
            correo=admin_email,
            password_hash=hash_password(admin_password),
            role="admin",
        )
        db.add(admin)
        db.commit()
        print("✅ Admin seeded successfully")
    else:
        if exists.correo != admin_email:
            exists.correo = admin_email
            exists.password_hash = hash_password(admin_password)
            db.commit()
            print("✅ Admin updated successfully")
        else:
            print("✅ Admin already exists")

def seed_temas(db: Session):
    """
    Crear los temas básicos si no existen
    """
    temas_basicos = [
        {
            "nombre": "Álgebra y Funciones",
            "codigo": "algebra",
            "descripcion": "Ecuaciones, funciones y expresiones algebraicas"
        },
        {
            "nombre": "Geometría y Medida",
            "codigo": "geometria",
            "descripcion": "Figuras, áreas, volúmenes y teorema de Pitágoras"
        },
        {
            "nombre": "Estadística y Probabilidad",
            "codigo": "estadistica",
            "descripcion": "Media, mediana, moda y cálculo de probabilidades"
        },
        {
            "nombre": "Evaluación Docente",
            "codigo": "evaluacion-docente",
            "descripcion": "Preguntas de evaluación cargadas por docentes"
        }
    ]
    
    for tema_data in temas_basicos:
        existe = db.query(Tema).filter(Tema.codigo == tema_data["codigo"]).first()
        
        if not existe:
            tema = Tema(**tema_data)
            db.add(tema)
            print(f"✅ Tema creado: {tema_data['nombre']}")
    
    try:
        db.commit()
        print("✅ Temas básicos creados/verificados")
    except Exception as e:
        db.rollback()
        print(f"⚠️ Error al crear temas: {e}")

# ========================================
# LIFECYCLE
# ========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting lifespan")
    try:
        print("Creating tables")
        Base.metadata.create_all(bind=engine)
        print("Seeding admin and temas")
        db = SessionLocal()
        try:
            seed_admin(db)
            seed_temas(db)  # ✅ NUEVO: Crear temas automáticamente
        finally:
            db.close()
        print("Lifespan startup complete")
    except Exception as e:
        print(f"Error in startup: {e}")
        import traceback
        traceback.print_exc()
    yield
    print("Lifespan shutdown")

app = FastAPI(title="Backend Competencias", version="1.0", lifespan=lifespan)

@app.get("/")
def root():
    return {"ok": True, "message": "API Competencias OK", "timestamp": "2026-01-28"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# AUTH ENDPOINTS
# ========================================

@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.correo == payload.correo).first()
    if exists:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    user = User(
        nombre=payload.nombre,
        correo=payload.correo,
        password_hash=hash_password(payload.password),
        role="estudiante"
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.post("/auth/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.correo == payload.correo).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no existe")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    
    token = create_access_token({
        "sub": str(user.id),
        "id": user.id,
        "nombre": user.nombre,
        "correo": user.correo,
        "role": user.role
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": user.id,
            "nombre": user.nombre,
            "correo": user.correo,
            "role": user.role
        }
    }

@app.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/auth/change-password", response_model=dict)
def change_password(
    payload: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Usuario autenticado cambia su propia contraseña"""
    print(f"🔐 Cambiando contraseña para usuario: {current_user.nombre}")
    
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente")
    
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(current_user)
    print(f"✅ Contraseña actualizada para {current_user.nombre}")
    
    return {"message": "Contraseña actualizada exitosamente"}

@app.post("/auth/reset-password", response_model=dict)
def reset_password(payload: ResetPassword, db: Session = Depends(get_db)):
    """Recuperar contraseña sin autenticación"""
    print(f"🔐 Reset password para correo: {payload.correo}")
    
    if not payload.correo:
        raise HTTPException(status_code=400, detail="El correo es obligatorio")
    
    if not payload.new_password or len(payload.new_password) < 4:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 4 caracteres")
    
    user = db.query(User).filter(User.correo == payload.correo).first()
    
    if not user:
        print(f"⚠️ Correo no encontrado: {payload.correo}")
        return {"message": "Si el correo existe, se ha actualizado la contraseña"}
    
    try:
        user.password_hash = hash_password(payload.new_password)
        db.commit()
        db.refresh(user)
        print(f"✅ Contraseña actualizada para {user.nombre}")
        return {"message": "Contraseña actualizada exitosamente"}
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al actualizar la contraseña")

@app.put("/admin/users/{user_id}/password", response_model=dict)
def admin_change_user_password(
    user_id: int,
    payload: AdminChangePassword,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin cambia la contraseña de cualquier usuario"""
    print(f"🔐 Admin cambio de contraseña para usuario ID: {user_id}")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    print(f"✅ Contraseña actualizada para {user.nombre}")
    
    return {"message": f"Contraseña de {user.nombre} actualizada exitosamente"}

# ========================================
# ADMIN ENDPOINTS
# ========================================

@app.get("/admin/users", response_model=list[UserOut])
def get_all_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Obtener todos los usuarios (solo admin)"""
    users = db.query(User).all()
    return users

@app.put("/admin/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: int,
    payload: PromoteRole,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Cambiar rol de usuario (solo admin)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if payload.role not in ["estudiante", "docente", "admin"]:
        raise HTTPException(status_code=400, detail="Rol inválido")
    
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user

@app.put("/admin/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Actualizar información de usuario (solo admin)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if payload.nombre:
        user.nombre = payload.nombre
    if payload.correo:
        user.correo = payload.correo
    if payload.role:
        user.role = payload.role
    
    db.commit()
    db.refresh(user)
    return user

@app.delete("/admin/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Eliminar usuario (solo admin)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    db.delete(user)
    db.commit()
    return None

# ========================================
# DOCENTE ENDPOINTS
# ========================================

@app.get("/docente/estudiantes")
def get_estudiantes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_docente_or_admin)
):
    """Obtener lista de estudiantes"""
    estudiantes = db.query(User).filter(User.role == "estudiante").all()
    return [
        {
            "id": e.id,
            "nombre": e.nombre,
            "correo": e.correo,
            "created_at": e.created_at
        }
        for e in estudiantes
    ]

# ========================================
# TEMAS ENDPOINTS
# ========================================

@app.get("/temas")
def obtener_temas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener lista de temas disponibles"""
    temas = db.query(Tema).filter(Tema.activo == True).all()
    
    return [
        {
            "id": t.id,
            "codigo": t.codigo,
            "nombre": t.nombre,
            "descripcion": t.descripcion
        }
        for t in temas
    ]

# ========================================
# PREGUNTAS ENDPOINTS
# ========================================

@app.post("/preguntas/importar-excel")
def importar_preguntas_excel(
    tema_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_docente_or_admin)
):
    """
    Importar preguntas desde Excel
    
    Soporta dos formatos:
    
    Formato 1 (Simple):
    - Pregunta, Opción A, Opción B, Opción C, Opción D, Respuesta Correcta, Nivel
    
    Formato 2 (Completo - tu caso):
    - Pregunta, a, b, c, d, Respuesta_Correcta, Dificultad
    """
    print(f"📤 Importando preguntas - Docente: {current_user.nombre}, Tema: {tema_id}")
    
    # Buscar tema por código
    tema = db.query(Tema).filter(Tema.codigo == tema_id).first()
    if not tema:
        raise HTTPException(status_code=404, detail=f"Tema '{tema_id}' no encontrado")
    
    # Leer archivo Excel
    try:
        contents = file.file.read()
        df = pd.read_excel(BytesIO(contents))
        print(f"📊 Archivo leído: {len(df)} filas")
        print(f"📋 Columnas encontradas: {list(df.columns)}")
    except Exception as e:
        print(f"❌ Error leyendo Excel: {e}")
        raise HTTPException(status_code=400, detail=f"Error al leer el archivo Excel: {str(e)}")
    
    # Detectar formato del Excel
    formato_simple = all(col in df.columns for col in ['Pregunta', 'Opción A', 'Opción B', 'Opción C', 'Opción D'])
    formato_completo = all(col in df.columns for col in ['Pregunta', 'a', 'b', 'c', 'd'])
    
    if not formato_simple and not formato_completo:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de Excel no válido. Debe contener: Pregunta, a/b/c/d o Opción A/B/C/D. Columnas encontradas: {list(df.columns)}"
        )
    
    print(f"✅ Formato detectado: {'Simple' if formato_simple else 'Completo'}")
    
    # Procesar preguntas
    preguntas_insertadas = []
    errores = []
    
    for index, row in df.iterrows():
        fila_numero = index + 2
        
        try:
            pregunta_texto = str(row['Pregunta']).strip()
            
            # Detectar opciones según formato
            if formato_simple:
                opcion_a = str(row['Opción A']).strip()
                opcion_b = str(row['Opción B']).strip()
                opcion_c = str(row['Opción C']).strip()
                opcion_d = str(row['Opción D']).strip()
                respuesta = str(row.get('Respuesta Correcta', '')).strip().upper()
                nivel = str(row.get('Nivel', 'Medio')).strip().capitalize()
            else:  # formato_completo
                opcion_a = str(row['a']).strip()
                opcion_b = str(row['b']).strip()
                opcion_c = str(row['c']).strip()
                opcion_d = str(row['d']).strip()
                
                # Mapear respuesta (a,b,c,d → A,B,C,D)
                respuesta_raw = str(row.get('Respuesta_Correcta', '')).strip().lower()
                if respuesta_raw in ['a', 'b', 'c', 'd']:
                    respuesta = respuesta_raw.upper()
                else:
                    respuesta = respuesta_raw.upper()
                
                # Mapear dificultad
                nivel = str(row.get('Dificultad', 'Medio')).strip().capitalize()
            
            # Validaciones
            if not pregunta_texto or pregunta_texto == 'nan':
                errores.append(f"Fila {fila_numero}: Pregunta vacía")
                continue
            
            if not all([opcion_a, opcion_b, opcion_c, opcion_d]) or 'nan' in [opcion_a, opcion_b, opcion_c, opcion_d]:
                errores.append(f"Fila {fila_numero}: Opciones incompletas")
                continue
            
            if respuesta not in ['A', 'B', 'C', 'D']:
                errores.append(f"Fila {fila_numero}: Respuesta debe ser A, B, C o D (recibido: '{respuesta}')")
                continue
            
            # Normalizar nivel
            nivel_lower = nivel.lower()
            if 'fac' in nivel_lower or 'fácil' in nivel_lower:
                nivel = 'Fácil'
            elif 'med' in nivel_lower:
                nivel = 'Medio'
            elif 'dif' in nivel_lower or 'difícil' in nivel_lower:
                nivel = 'Difícil'
            else:
                # Si no se reconoce, usar "Medio" por defecto
                nivel = 'Medio'
            
            # Crear pregunta
            nueva_pregunta = Pregunta(
                pregunta=pregunta_texto[:500],
                opcion_a=opcion_a[:200],
                opcion_b=opcion_b[:200],
                opcion_c=opcion_c[:200],
                opcion_d=opcion_d[:200],
                respuesta_correcta=respuesta,
                nivel=nivel,
                tema_id=tema.id,
                es_evaluacion_docente=(tema_id == 'evaluacion-docente'),
                created_by=current_user.id,
                activo=True
            )
            
            db.add(nueva_pregunta)
            preguntas_insertadas.append(nueva_pregunta)
            
        except Exception as e:
            errores.append(f"Fila {fila_numero}: {str(e)}")
    
    # Guardar en BD
    if not preguntas_insertadas:
        error_msg = "No se pudo importar ninguna pregunta."
        if errores:
            error_msg += f" Errores: {'; '.join(errores[:5])}"
        raise HTTPException(status_code=400, detail=error_msg)
    
    try:
        db.commit()
        print(f"✅ {len(preguntas_insertadas)} preguntas guardadas")
        
        for p in preguntas_insertadas:
            db.refresh(p)
    except Exception as e:
        db.rollback()
        print(f"❌ Error guardando: {e}")
        raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")
    
    # Respuesta
    preguntas_out = [
        {
            "id": p.id,
            "pregunta": p.pregunta,
            "opcion_a": p.opcion_a,
            "opcion_b": p.opcion_b,
            "opcion_c": p.opcion_c,
            "opcion_d": p.opcion_d,
            "respuesta_correcta": p.respuesta_correcta,
            "nivel": p.nivel,
            "tema_id": p.tema_id,
            "activo": p.activo,
            "es_evaluacion_docente": p.es_evaluacion_docente,
            "created_at": p.created_at
        }
        for p in preguntas_insertadas
    ]
    
    mensaje = f"✅ {len(preguntas_insertadas)} preguntas importadas"
    if errores:
        mensaje += f". ⚠️ {len(errores)} filas omitidas"
    
    return {
        "mensaje": mensaje,
        "tema": tema.nombre,
        "cantidad": len(preguntas_insertadas),
        "preguntas": preguntas_out,
        "errores": errores[:10] if errores else []
    }

@app.get("/preguntas/tema/{tema_id}/quiz")
def obtener_preguntas_por_tema(
    tema_id: int,
    cantidad: int = 10,
    nivel: str = None,
    solo_activas: bool = True,
    excluir_evaluacion: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener preguntas aleatorias de un tema específico para quiz
    
    Parámetros:
    - tema_id: ID del tema
    - cantidad: Número de preguntas (default: 10)
    - nivel: Filtro de dificultad (Fácil, Medio, Difícil, o todas)
    - solo_activas: Solo preguntas activas (default: True)
    - excluir_evaluacion: Excluir preguntas de evaluación docente (default: True)
    """
    print(f"📚 Obteniendo preguntas - Tema: {tema_id}, Nivel: {nivel}, Cantidad: {cantidad}")
    
    # Verificar tema
    tema = db.query(Tema).filter(Tema.id == tema_id).first()
    if not tema:
        raise HTTPException(status_code=404, detail=f"Tema con ID {tema_id} no encontrado")
    
    # Construir query
    query = db.query(Pregunta).filter(Pregunta.tema_id == tema_id)
    
    if solo_activas:
        query = query.filter(Pregunta.activo == True)
    
    if excluir_evaluacion:
        query = query.filter(Pregunta.es_evaluacion_docente == False)
    
    if nivel and nivel.lower() not in ['todas', 'all']:
        query = query.filter(Pregunta.nivel == nivel)
    
    # Obtener preguntas aleatorias
    preguntas = query.order_by(func.random()).limit(cantidad).all()
    
    if not preguntas:
        raise HTTPException(
            status_code=404,
            detail=f"No hay preguntas disponibles para '{tema.nombre}' con los filtros especificados"
        )
    
    print(f"✅ {len(preguntas)} preguntas encontradas")
    
    return {
        "tema": tema.nombre,
        "tema_id": tema.id,
        "cantidad": len(preguntas),
        "preguntas": [
            {
                "id": p.id,
                "pregunta": p.pregunta,
                "opcion_a": p.opcion_a,
                "opcion_b": p.opcion_b,
                "opcion_c": p.opcion_c,
                "opcion_d": p.opcion_d,
                "respuesta_correcta": p.respuesta_correcta,
                "nivel": p.nivel,
                "tema_id": p.tema_id,
                "es_evaluacion_docente": p.es_evaluacion_docente
            }
            for p in preguntas
        ]
    }

@app.get("/preguntas/tema/{tema_id}/quiz")
def obtener_preguntas_por_tema(
    tema_id: int,
    cantidad: int = Query(10, ge=1, le=50),
    nivel: str = Query("todas"),
    solo_activas: bool = Query(True),
    excluir_evaluacion: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener preguntas aleatorias de un tema específico para quiz
    """
    tema = db.query(Tema).filter(Tema.id == tema_id).first()
    if not tema:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    
    query = db.query(Pregunta).filter(Pregunta.tema_id == tema_id)
    
    if solo_activas:
        query = query.filter(Pregunta.activo == True)
    
    if excluir_evaluacion:
        query = query.filter(Pregunta.es_evaluacion_docente == False)
    
    if nivel and nivel.lower() != 'todas':
        query = query.filter(Pregunta.nivel == nivel)
    
    preguntas = query.order_by(func.random()).limit(cantidad).all()
    
    if not preguntas:
        raise HTTPException(
            status_code=404, 
            detail=f"No hay preguntas disponibles para el tema '{tema.nombre}'"
        )
    
    return {
        "tema": tema.nombre,
        "cantidad": len(preguntas),
        "preguntas": [
            {
                "id": p.id,
                "pregunta": p.pregunta,
                "opcion_a": p.opcion_a,
                "opcion_b": p.opcion_b,
                "opcion_c": p.opcion_c,
                "opcion_d": p.opcion_d,
                "respuesta_correcta": p.respuesta_correcta,
                "nivel": p.nivel,
                "tema_id": p.tema_id,
                "es_evaluacion_docente": p.es_evaluacion_docente
            }
            for p in preguntas
        ]
    }


@app.get("/preguntas/evaluacion-docente")
def obtener_preguntas_evaluacion_docente(
    cantidad: int = 10,
    nivel: str = None,
    solo_activas: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener preguntas de evaluación docente
    
    Estas son las preguntas que los docentes han importado
    específicamente para evaluar a los estudiantes
    """
    print(f"📝 Obteniendo preguntas de evaluación docente - Cantidad: {cantidad}")
    
    # Query para evaluación docente
    query = db.query(Pregunta).filter(Pregunta.es_evaluacion_docente == True)
    
    if solo_activas:
        query = query.filter(Pregunta.activo == True)
    
    if nivel and nivel.lower() not in ['todas', 'all']:
        query = query.filter(Pregunta.nivel == nivel)
    
    # Obtener preguntas aleatorias
    preguntas = query.order_by(func.random()).limit(cantidad).all()
    
    if not preguntas:
        raise HTTPException(
            status_code=404,
            detail="No hay preguntas de evaluación docente disponibles. El docente aún no ha cargado preguntas."
        )
    
    print(f"✅ {len(preguntas)} preguntas de evaluación encontradas")
    
    return {
        "tipo": "Evaluación Docente",
        "cantidad": len(preguntas),
        "preguntas": [
            {
                "id": p.id,
                "pregunta": p.pregunta,
                "opcion_a": p.opcion_a,
                "opcion_b": p.opcion_b,
                "opcion_c": p.opcion_c,
                "opcion_d": p.opcion_d,
                "respuesta_correcta": p.respuesta_correcta,
                "nivel": p.nivel,
                "tema_id": p.tema_id,
                "es_evaluacion_docente": p.es_evaluacion_docente
            }
            for p in preguntas
        ]
    }

# ========================================
# QUIZ ENDPOINTS
# ========================================

@app.post("/quiz/calificar")
def calificar_quiz(
    payload: CalificarQuizRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calificar un quiz completo
    
    Payload:
    {
        "tema_id": 1,
        "respuestas": [
            {"pregunta_id": 1, "respuesta": "A"},
            {"pregunta_id": 2, "respuesta": "B"},
            ...
        ]
    }
    """
    print(f"📝 Calificando quiz - Usuario: {current_user.nombre}, Tema: {payload.tema_id}")
    
    # Verificar tema
    tema = db.query(Tema).filter(Tema.id == payload.tema_id).first()
    if not tema:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    
    correctas = 0
    resultados_detallados = []
    
    # Calificar cada respuesta
    for respuesta in payload.respuestas:
        pregunta = db.query(Pregunta).filter(Pregunta.id == respuesta.pregunta_id).first()
        
        if not pregunta:
            continue
        
        es_correcta = (pregunta.respuesta_correcta == respuesta.respuesta)
        
        if es_correcta:
            correctas += 1
        
        resultados_detallados.append({
            "pregunta_id": respuesta.pregunta_id,
            "respuesta_usuario": respuesta.respuesta,
            "respuesta_correcta": pregunta.respuesta_correcta,
            "es_correcta": es_correcta,
            "pregunta_texto": pregunta.pregunta
        })
    
    total = len(payload.respuestas)
    puntaje = int((correctas / total) * 100) if total > 0 else 0
    
    print(f"✅ Quiz calificado - Puntaje: {puntaje}% ({correctas}/{total})")
    
    return {
        "puntaje": puntaje,
        "correctas": correctas,
        "total": total,
        "porcentaje": puntaje,
        "aprobado": puntaje >= 60,
        "tema": tema.nombre,
        "resultados": resultados_detallados
    }

@app.post("/resultados-quiz")
def guardar_resultado_quiz(
    payload: ResultadoQuizCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Guardar resultado de quiz en la base de datos"""
    print(f"💾 Guardando resultado - Usuario: {current_user.nombre}, Tema: {payload.tema_id}")
    
    # Verificar tema
    tema = db.query(Tema).filter(Tema.id == payload.tema_id).first()
    if not tema:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    
    # Crear resultado
    resultado = ResultadoQuiz(
        estudiante_id=current_user.id,
        tema_id=payload.tema_id,
        puntaje=payload.puntaje,
        correctas=payload.correctas,
        total=payload.total,
        tiempo_segundos=payload.tiempo_segundos
    )
    
    db.add(resultado)
    db.commit()
    db.refresh(resultado)
    
    print(f"✅ Resultado guardado - ID: {resultado.id}")
    
    return {
        "id": resultado.id,
        "estudiante_id": resultado.estudiante_id,
        "tema_id": resultado.tema_id,
        "puntaje": resultado.puntaje,
        "correctas": resultado.correctas,
        "total": resultado.total,
        "fecha": resultado.fecha,
        "mensaje": "Resultado guardado exitosamente"
    }

@app.get("/estudiante/mis-resultados")
def obtener_mis_resultados(
    tema_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todos los resultados del estudiante actual"""
    query = db.query(ResultadoQuiz).filter(ResultadoQuiz.estudiante_id == current_user.id)
    
    if tema_id:
        query = query.filter(ResultadoQuiz.tema_id == tema_id)
    
    resultados = query.order_by(ResultadoQuiz.fecha.desc()).all()
    
    return [
        {
            "id": r.id,
            "tema_id": r.tema_id,
            "puntaje": r.puntaje,
            "correctas": r.correctas,
            "total": r.total,
            "tiempo_segundos": r.tiempo_segundos,
            "fecha": r.fecha
        }
        for r in resultados
    ]

# ========================================
# ENDPOINTS DE RESULTADOS PARA DOCENTES
# ========================================

@app.get("/docente/estudiantes/{estudiante_id}/resultados")
def obtener_resultados_estudiante(
    estudiante_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_docente_or_admin)
):
    """
    Obtener todos los resultados de quiz de un estudiante específico
    Solo accesible por docentes y admin
    """
    print(f"📊 Obteniendo resultados - Estudiante ID: {estudiante_id}")
    
    # Verificar que el estudiante existe
    estudiante = db.query(User).filter(User.id == estudiante_id).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    
    # Obtener todos los resultados del estudiante
    resultados = db.query(ResultadoQuiz)\
        .filter(ResultadoQuiz.estudiante_id == estudiante_id)\
        .order_by(ResultadoQuiz.fecha.desc())\
        .all()
    
    # Obtener información de los temas
    resultados_con_tema = []
    for resultado in resultados:
        tema = db.query(Tema).filter(Tema.id == resultado.tema_id).first()
        
        resultados_con_tema.append({
            "id": resultado.id,
            "tema_id": resultado.tema_id,
            "tema": tema.nombre if tema else "Desconocido",
            "puntaje": resultado.puntaje,
            "correctas": resultado.correctas,
            "total": resultado.total,
            "tiempo_segundos": resultado.tiempo_segundos,
            "fecha": resultado.fecha.isoformat()
        })
    
    print(f"✅ {len(resultados_con_tema)} resultados encontrados")
    
    return resultados_con_tema


@app.get("/docente/estudiantes/{estudiante_id}/estadisticas")
def obtener_estadisticas_estudiante(
    estudiante_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_docente_or_admin)
):
    """
    Obtener estadísticas resumidas de un estudiante
    """
    print(f"📈 Obteniendo estadísticas - Estudiante ID: {estudiante_id}")
    
    # Verificar que el estudiante existe
    estudiante = db.query(User).filter(User.id == estudiante_id).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    
    # Obtener todos los resultados
    resultados = db.query(ResultadoQuiz)\
        .filter(ResultadoQuiz.estudiante_id == estudiante_id)\
        .all()
    
    if not resultados:
        return {
            "estudiante_id": estudiante_id,
            "estudiante_nombre": estudiante.nombre,
            "total_quizzes": 0,
            "promedio": 0,
            "mejor_puntaje": 0,
            "peor_puntaje": 0,
            "total_aprobados": 0,
            "total_reprobados": 0
        }
    
    # Calcular estadísticas
    puntajes = [r.puntaje for r in resultados]
    promedio = sum(puntajes) / len(puntajes)
    aprobados = sum(1 for p in puntajes if p >= 70)
    reprobados = len(puntajes) - aprobados
    
    return {
        "estudiante_id": estudiante_id,
        "estudiante_nombre": estudiante.nombre,
        "total_quizzes": len(resultados),
        "promedio": round(promedio, 2),
        "mejor_puntaje": max(puntajes),
        "peor_puntaje": min(puntajes),
        "total_aprobados": aprobados,
        "total_reprobados": reprobados,
        "porcentaje_aprobacion": round((aprobados / len(puntajes)) * 100, 2)
    }


@app.get("/docente/resultados/todos")
def obtener_todos_resultados(
    tema_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_docente_or_admin)
):
    """
    Obtener todos los resultados de todos los estudiantes
    Opcionalmente filtrar por tema
    """
    print(f"📊 Obteniendo todos los resultados - Tema: {tema_id}")
    
    # Query base
    query = db.query(ResultadoQuiz)
    
    # Filtrar por tema si se especifica
    if tema_id:
        query = query.filter(ResultadoQuiz.tema_id == tema_id)
    
    # Obtener resultados ordenados por fecha
    resultados = query.order_by(ResultadoQuiz.fecha.desc()).all()
    
    # Enriquecer con información de estudiante y tema
    resultados_enriquecidos = []
    for resultado in resultados:
        estudiante = db.query(User).filter(User.id == resultado.estudiante_id).first()
        tema = db.query(Tema).filter(Tema.id == resultado.tema_id).first()
        
        resultados_enriquecidos.append({
            "id": resultado.id,
            "estudiante_id": resultado.estudiante_id,
            "estudiante_nombre": estudiante.nombre if estudiante else "Desconocido",
            "estudiante_correo": estudiante.correo if estudiante else "",
            "tema_id": resultado.tema_id,
            "tema": tema.nombre if tema else "Desconocido",
            "puntaje": resultado.puntaje,
            "correctas": resultado.correctas,
            "total": resultado.total,
            "tiempo_segundos": resultado.tiempo_segundos,
            "fecha": resultado.fecha.isoformat()
        })
    
    print(f"✅ {len(resultados_enriquecidos)} resultados encontrados")
    
    return resultados_enriquecidos

# from database import get_db
# from models import Usuario, ResultadoQuiz, Tema
# from auth import get_current_user

router = APIRouter(prefix="/ranking", tags=["Ranking"])


def get_week_range(semana: str) -> tuple:
    """
    Calcular el rango de fechas para una semana específica.
    
    Formatos soportados:
    - "actual" o "presente": Semana actual
    - "pasada" o "anterior": Semana pasada
    - "2026-W05": Semana 5 del 2026 (formato ISO)
    - "hace-2": Hace 2 semanas
    """
    hoy = datetime.now()
    
    # Obtener lunes de la semana actual
    dias_desde_lunes = hoy.weekday()
    lunes_actual = hoy - timedelta(days=dias_desde_lunes)
    lunes_actual = lunes_actual.replace(hour=0, minute=0, second=0, microsecond=0)
    domingo_actual = lunes_actual + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    if semana in ["actual", "presente", "current"]:
        return lunes_actual, domingo_actual
    
    elif semana in ["pasada", "anterior", "last"]:
        lunes = lunes_actual - timedelta(days=7)
        domingo = lunes + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return lunes, domingo
    
    elif semana.startswith("hace-"):
        try:
            num_semanas = int(semana.split("-")[1])
            lunes = lunes_actual - timedelta(days=7 * num_semanas)
            domingo = lunes + timedelta(days=6, hours=23, minutes=59, seconds=59)
            return lunes, domingo
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Formato de semana inválido")
    
    elif "-W" in semana:
        # Formato ISO: 2026-W05
        try:
            year, week = semana.split("-W")
            year = int(year)
            week = int(week)
            
            # Calcular primer día del año
            primer_dia = datetime(year, 1, 1)
            dias_hasta_lunes = (7 - primer_dia.weekday()) % 7
            primer_lunes = primer_dia + timedelta(days=dias_hasta_lunes)
            
            # Calcular lunes de la semana especificada
            lunes = primer_lunes + timedelta(weeks=week - 1)
            domingo = lunes + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
            return lunes, domingo
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Formato de semana ISO inválido")
    
    else:
        raise HTTPException(status_code=400, detail="Formato de semana no reconocido")


# CORRECCIONES PARA EL ENDPOINT DE RANKING
# Agregar estas modificaciones a main.py líneas 1105-1190

@router.get("/semanal/{tema_codigo}")
def get_ranking_semanal(
    tema_codigo: str,
    semana: str = Query("actual", description="Semana del ranking"),
    limite: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Obtener ranking semanal de un tema específico
    ENDPOINT PÚBLICO - NO requiere autenticación
    """
    print(f"📊 [RANKING] Tema: {tema_codigo}, Semana: {semana}, Límite: {limite}")
    
    # ✅ VALIDAR tema_codigo
    temas_validos = ['algebra', 'geometria', 'estadistica', 'evaluacion-docente']
    if tema_codigo not in temas_validos:
        print(f"❌ [RANKING] Tema inválido: {tema_codigo}")
        raise HTTPException(
            status_code=400, 
            detail=f"Tema inválido. Opciones: {', '.join(temas_validos)}"
        )
    
    # Buscar tema
    try:
        tema = db.query(Tema).filter(Tema.codigo == tema_codigo).first()
        if not tema:
            print(f"❌ [RANKING] Tema no encontrado en BD: {tema_codigo}")
            raise HTTPException(
                status_code=404, 
                detail=f"Tema '{tema_codigo}' no encontrado en la base de datos"
            )
        
        print(f"✅ [RANKING] Tema encontrado: {tema.nombre} (ID: {tema.id})")
    except Exception as e:
        print(f"❌ [RANKING] Error buscando tema: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al buscar tema: {str(e)}")
    
    # Calcular fechas
    try:
        fecha_inicio, fecha_fin = get_week_range(semana)
        print(f"📅 [RANKING] Fechas: {fecha_inicio} a {fecha_fin}")
    except Exception as e:
        print(f"❌ [RANKING] Error en fechas: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error calculando fechas: {str(e)}")
    
    # Query del ranking
    try:
        print(f"🔍 [RANKING] Ejecutando query para tema_id={tema.id}")
        
        ranking = db.query(
            ResultadoQuiz.estudiante_id,
            User.nombre,
            User.correo,
            func.max(ResultadoQuiz.puntaje).label('mejor_puntaje'),
            func.count(ResultadoQuiz.id).label('quiz_realizados'),
            func.avg(ResultadoQuiz.puntaje).label('promedio'),
            func.coalesce(func.min(ResultadoQuiz.tiempo_segundos), 0).label('mejor_tiempo')
        ).join(
            User, ResultadoQuiz.estudiante_id == User.id
        ).filter(
            and_(
                ResultadoQuiz.tema_id == tema.id,
                ResultadoQuiz.fecha >= fecha_inicio,
                ResultadoQuiz.fecha <= fecha_fin
            )
        ).group_by(
            ResultadoQuiz.estudiante_id,
            User.nombre,
            User.correo
        ).order_by(
            desc('mejor_puntaje'),
            func.coalesce(func.min(ResultadoQuiz.tiempo_segundos), 9999).asc()
        ).limit(limite).all()
        
        print(f"✅ [RANKING] Resultados: {len(ranking)} estudiantes")
        
        # ✅ Si no hay resultados, devolver ranking vacío pero sin error
        if len(ranking) == 0:
            print(f"⚠️ [RANKING] No hay resultados para este tema/semana")
            return {
                "tema": tema_codigo,
                "tema_nombre": tema.nombre,
                "semana": semana,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin": fecha_fin.isoformat(),
                "total_estudiantes": 0,
                "ranking": []
            }
        
    except Exception as e:
        print(f"❌ [RANKING] Error en query: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error ejecutando query: {str(e)}"
        )
    
    # Formatear resultados
    try:
        resultado = []
        for idx, (usuario_id, nombre, correo, mejor_puntaje, quiz_realizados, promedio, mejor_tiempo) in enumerate(ranking, 1):
            resultado.append({
                "posicion": idx,
                "usuario_id": usuario_id,
                "nombre": nombre,
                "correo": correo,
                "mejor_puntaje": int(mejor_puntaje or 0),
                "promedio": round(float(promedio or 0), 1),
                "quiz_realizados": int(quiz_realizados),
                "mejor_tiempo_segundos": int(mejor_tiempo or 0),
                "medalla": "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else None
            })
        
        print(f"✅ [RANKING] Respuesta con {len(resultado)} entradas")
        
        return {
            "tema": tema_codigo,
            "tema_nombre": tema.nombre,
            "semana": semana,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "total_estudiantes": len(resultado),
            "ranking": resultado
        }
    except Exception as e:
        print(f"❌ [RANKING] Error formateando resultados: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error formateando resultados: {str(e)}"
        )


@router.get("/semanas-disponibles/{tema_codigo}")
def get_semanas_disponibles(
    tema_codigo: str,
    db: Session = Depends(get_db)
):
    """
    Obtener lista de semanas donde hay datos de ranking para un tema.
    """
    tema = db.query(Tema).filter(Tema.codigo == tema_codigo).first()
    if not tema:
        raise HTTPException(status_code=404, detail=f"Tema '{tema_codigo}' no encontrado")
    
    # Obtener la fecha más antigua con resultados
    primera_fecha = db.query(
        func.min(ResultadoQuiz.fecha)
    ).filter(
        ResultadoQuiz.tema_id == tema.id
    ).scalar()
    
    if not primera_fecha:
        return {"semanas": []}
    
    # Calcular semanas desde la primera fecha hasta hoy
    hoy = datetime.now()
    semanas = []
    
    dias_desde_lunes = hoy.weekday()
    lunes_actual = hoy - timedelta(days=dias_desde_lunes)
    
    semana_numero = 0
    while True:
        lunes = lunes_actual - timedelta(days=7 * semana_numero)
        domingo = lunes + timedelta(days=6)
        
        if domingo < primera_fecha:
            break
        
        # Verificar si hay datos en esta semana
        count = db.query(func.count(ResultadoQuiz.id)).filter(
            and_(
                ResultadoQuiz.tema_id == tema.id,
                ResultadoQuiz.fecha >= lunes,
                ResultadoQuiz.fecha <= domingo
            )
        ).scalar()
        
        if count > 0:
            semanas.append({
                "codigo": f"hace-{semana_numero}" if semana_numero > 0 else "actual",
                "label": "Semana Actual" if semana_numero == 0 else 
                         "Semana Pasada" if semana_numero == 1 else 
                         f"Hace {semana_numero} semanas",
                "fecha_inicio": lunes.strftime("%Y-%m-%d"),
                "fecha_fin": domingo.strftime("%Y-%m-%d"),
                "total_quizzes": count
            })
        
        semana_numero += 1
        
        if semana_numero > 52:  # Máximo 1 año atrás
            break
    
    return {"semanas": semanas}


@router.get("/posicion-usuario/{tema_codigo}")
def get_posicion_usuario(
    tema_codigo: str,
    semana: str = "actual",
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Obtener la posición del usuario actual en el ranking semanal.
    """
    tema = db.query(Tema).filter(Tema.codigo == tema_codigo).first()
    if not tema:
        raise HTTPException(status_code=404, detail=f"Tema '{tema_codigo}' no encontrado")
    
    fecha_inicio, fecha_fin = get_week_range(semana)
    
    # Obtener ranking completo
    ranking = db.query(
        ResultadoQuiz.estudiante_id,
        func.max(ResultadoQuiz.puntaje).label('mejor_puntaje'),
        func.min(ResultadoQuiz.tiempo_segundos).label('mejor_tiempo')
    ).filter(
        and_(
            ResultadoQuiz.tema_id == tema.id,
            ResultadoQuiz.fecha >= fecha_inicio,
            ResultadoQuiz.fecha <= fecha_fin
        )
    ).group_by(
        ResultadoQuiz.estudiante_id
    ).order_by(
        desc('mejor_puntaje'),
        func.min(ResultadoQuiz.tiempo_segundos).asc()
    ).all()
    
    # Buscar posición del usuario actual
    posicion = None
    mejor_puntaje = None
    
    for idx, (usuario_id, puntaje, tiempo) in enumerate(ranking, 1):
        if usuario_id == current_user.id:
            posicion = idx
            mejor_puntaje = puntaje
            break
    
    return {
        "tiene_resultados": posicion is not None,
        "posicion": posicion,
        "mejor_puntaje": mejor_puntaje,
        "total_participantes": len(ranking)
    }

app.include_router(router)