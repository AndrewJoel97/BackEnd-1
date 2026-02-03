from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from .database import Base

# ========================================
# MODELO EXISTENTE (SIN CAMBIOS)
# ========================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    correo = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="estudiante")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ========================================
# ✅ NUEVOS MODELOS - SISTEMA DE PREGUNTAS
# ========================================

class Tema(Base):
    """
    Temas del sistema (Álgebra, Geometría, etc.)
    """
    __tablename__ = "temas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False, index=True)
    # Ej: "Álgebra y Funciones", "Geometría y Medida", etc.
    
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    # Ej: "algebra", "geometria", "estadistica", "evaluacion-docente"
    
    descripcion = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relación: un tema tiene muchas preguntas
    preguntas = relationship("Pregunta", back_populates="tema")


class Pregunta(Base):
    """
    Preguntas del quiz - importadas desde Excel
    """
    __tablename__ = "preguntas"

    id = Column(Integer, primary_key=True, index=True)
    
    # Contenido de la pregunta
    pregunta = Column(String(500), nullable=False)
    opcion_a = Column(String(200), nullable=False)
    opcion_b = Column(String(200), nullable=False)
    opcion_c = Column(String(200), nullable=False)
    opcion_d = Column(String(200), nullable=False)
    
    # Respuesta correcta: 'A', 'B', 'C', o 'D'
    respuesta_correcta = Column(String(1), nullable=False)
    
    # Nivel de dificultad: 'Fácil', 'Medio', o 'Difícil'
    nivel = Column(String(20), nullable=False, index=True)
    
    # Relación con tema
    tema_id = Column(Integer, ForeignKey("temas.id"), nullable=False, index=True)
    tema = relationship("Tema", back_populates="preguntas")
    
    # Metadatos
    activo = Column(Boolean, default=True, nullable=False)
    es_evaluacion_docente = Column(Boolean, default=False, nullable=False)
    # Si es True, esta pregunta es parte de "Evaluación Docente"
    
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Usuario (docente/admin) que importó la pregunta
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ========================================
# MODELO OPCIONAL - RESULTADOS DE QUIZ
# (Para implementar después)
# ========================================
class ResultadoQuiz(Base):
    """
    Resultados de quiz realizados por estudiantes
    """
    __tablename__ = "resultados_quiz"

    id = Column(Integer, primary_key=True, index=True)
    
    # Estudiante que realizó el quiz
    estudiante_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Tema del quiz
    tema_id = Column(Integer, ForeignKey("temas.id"), nullable=False, index=True)
    
    # Resultados
    puntaje = Column(Integer, nullable=False)  # 0-100
    correctas = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    
    # Metadatos
    tiempo_segundos = Column(Integer, nullable=True)  # Tiempo que tomó
    fecha = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relaciones
    # estudiante = relationship("User", foreign_keys=[estudiante_id])
    # tema = relationship("Tema")