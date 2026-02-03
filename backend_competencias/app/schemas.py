from pydantic import BaseModel, EmailStr, Field
from pydantic.config import ConfigDict
from typing import Optional, List
from datetime import datetime

# ========================================
# SCHEMAS EXISTENTES (SIN CAMBIOS)
# ========================================

# ===== AUTH INPUTS =====
class UserCreate(BaseModel):
    nombre: str = Field(min_length=2)
    correo: EmailStr
    password: str = Field(min_length=4)

class UserLogin(BaseModel):
    correo: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: Optional[dict] = None

# ===== OUTPUTS =====
class UserOut(BaseModel):
    id: int
    nombre: str
    correo: EmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)

# ===== ADMIN INPUT =====
class PromoteRole(BaseModel):
    role: str  # "docente" o "admin"

# ===== ACTUALIZAR USUARIO =====
class UserUpdate(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[EmailStr] = None
    role: Optional[str] = None

# ===== Cambiar contraseña (usuario autenticado) =====
class ChangePassword(BaseModel):
    current_password: str = Field(min_length=4, description="Contraseña actual")
    new_password: str = Field(min_length=4, description="Nueva contraseña")

# ===== Recuperar contraseña (sin autenticación) =====
class ResetPassword(BaseModel):
    correo: Optional[EmailStr] = None
    new_password: str = Field(min_length=4, description="Nueva contraseña")

# ===== Cambiar contraseña por admin =====
class AdminChangePassword(BaseModel):
    new_password: str = Field(min_length=4, description="Nueva contraseña")


# ========================================
# ✅ NUEVOS SCHEMAS - SISTEMA DE PREGUNTAS
# ========================================

# ===== TEMA =====
class TemaBase(BaseModel):
    nombre: str = Field(min_length=3, max_length=100)
    codigo: str = Field(min_length=3, max_length=50)
    descripcion: Optional[str] = None
    activo: bool = True

class TemaCreate(TemaBase):
    pass

class TemaOut(TemaBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ===== PREGUNTA =====
class PreguntaBase(BaseModel):
    pregunta: str = Field(min_length=10, max_length=500)
    opcion_a: str = Field(min_length=1, max_length=200)
    opcion_b: str = Field(min_length=1, max_length=200)
    opcion_c: str = Field(min_length=1, max_length=200)
    opcion_d: str = Field(min_length=1, max_length=200)
    respuesta_correcta: str = Field(pattern="^[A-D]$", description="Debe ser A, B, C o D")
    nivel: str = Field(description="Debe ser: Fácil, Medio o Difícil")

class PreguntaCreate(PreguntaBase):
    tema_id: int
    es_evaluacion_docente: bool = False

class PreguntaOut(PreguntaBase):
    id: int
    tema_id: int
    activo: bool
    es_evaluacion_docente: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PreguntaParaQuiz(BaseModel):
    """
    Pregunta para mostrar en el quiz (SIN la respuesta correcta)
    """
    id: int
    pregunta: str
    opcion_a: str
    opcion_b: str
    opcion_c: str
    opcion_d: str
    nivel: str
    
    model_config = ConfigDict(from_attributes=True)


# ===== IMPORTACIÓN EXCEL =====
class ImportarExcelResponse(BaseModel):
    """
    Respuesta al importar un Excel
    """
    mensaje: str
    tema: str
    cantidad: int
    preguntas: List[PreguntaOut]


# ===== RESULTADO QUIZ =====
class ResultadoQuizCreate(BaseModel):
    """
    Para guardar el resultado de un quiz
    """
    tema_id: int
    puntaje: int = Field(ge=0, le=100)
    correctas: int = Field(ge=0)
    total: int = Field(ge=1)
    tiempo_segundos: Optional[int] = None

class ResultadoQuizOut(BaseModel):
    id: int
    estudiante_id: int
    tema_id: int
    puntaje: int
    correctas: int
    total: int
    tiempo_segundos: Optional[int]
    fecha: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ===== RESPUESTA DE ESTUDIANTE =====
class RespuestaEstudiante(BaseModel):
    """
    Para calificar respuestas de estudiantes
    """
    pregunta_id: int
    respuesta: str = Field(pattern="^[A-D]$")

class CalificarQuizRequest(BaseModel):
    """
    Request para calificar un quiz completo
    """
    tema_id: int
    respuestas: List[RespuestaEstudiante]