"""
Script de migración para crear las tablas de Temas y Preguntas
Ejecutar DESPUÉS de actualizar models.py

IMPORTANTE: Este script NO afecta la tabla 'users' existente
"""

from app.database import engine, Base, SessionLocal
from app.models import User, Tema, Pregunta, ResultadoQuiz

def crear_tablas():
    """
    Crea las nuevas tablas en la base de datos
    """
    print("🔄 Creando tablas nuevas...")
    
    try:
        # Esto solo crea las tablas que NO existen
        # NO modifica ni elimina tablas existentes
        Base.metadata.create_all(bind=engine)
        print("✅ Tablas creadas exitosamente")
        return True
    except Exception as e:
        print(f"❌ Error creando tablas: {e}")
        return False

def seed_temas():
    """
    Inserta los 4 temas iniciales en la base de datos
    """
    print("🌱 Insertando temas iniciales...")
    
    db = SessionLocal()
    
    try:
        # Verificar si ya existen temas
        existing = db.query(Tema).count()
        if existing > 0:
            print(f"ℹ️  Ya existen {existing} temas en la base de datos")
            return True
        
        # Crear los 4 temas
        temas = [
            Tema(
                nombre="Álgebra y Funciones",
                codigo="algebra",
                descripcion="Preguntas de álgebra, funciones y ecuaciones",
                activo=True
            ),
            Tema(
                nombre="Geometría y Medida",
                codigo="geometria",
                descripcion="Preguntas de geometría, medidas y figuras",
                activo=True
            ),
            Tema(
                nombre="Estadística y Probabilidad",
                codigo="estadistica",
                descripcion="Preguntas de estadística, probabilidad y análisis de datos",
                activo=True
            ),
            Tema(
                nombre="Evaluación Docente",
                codigo="evaluacion-docente",
                descripcion="Preguntas personalizadas creadas por docentes",
                activo=True
            )
        ]
        
        # Insertar en BD
        for tema in temas:
            db.add(tema)
        
        db.commit()
        print(f"✅ Se insertaron {len(temas)} temas correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error insertando temas: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def verificar_migracion():
    """
    Verifica que las tablas se crearon correctamente
    """
    print("\n🔍 Verificando migración...")
    
    db = SessionLocal()
    
    try:
        # Verificar tabla users (debe existir)
        users_count = db.query(User).count()
        print(f"✅ Tabla 'users': {users_count} usuarios")
        
        # Verificar tabla temas
        temas_count = db.query(Tema).count()
        print(f"✅ Tabla 'temas': {temas_count} temas")
        
        # Verificar tabla preguntas
        preguntas_count = db.query(Pregunta).count()
        print(f"✅ Tabla 'preguntas': {preguntas_count} preguntas")
        
        # Verificar tabla resultados_quiz
        resultados_count = db.query(ResultadoQuiz).count()
        print(f"✅ Tabla 'resultados_quiz': {resultados_count} resultados")
        
        print("\n🎉 Migración completada exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error verificando migración: {e}")
        return False
    finally:
        db.close()

def main():
    """
    Ejecuta la migración completa
    """
    print("="*60)
    print("🚀 MIGRACIÓN: Sistema de Preguntas y Temas")
    print("="*60)
    print()
    
    # Paso 1: Crear tablas
    if not crear_tablas():
        print("❌ Migración fallida en crear_tablas()")
        return False
    
    print()
    
    # Paso 2: Insertar temas iniciales
    if not seed_temas():
        print("❌ Migración fallida en seed_temas()")
        return False
    
    print()
    
    # Paso 3: Verificar que todo está bien
    if not verificar_migracion():
        print("❌ Migración fallida en verificar_migracion()")
        return False
    
    print()
    print("="*60)
    print("✅ MIGRACIÓN COMPLETADA - Sistema listo para usar")
    print("="*60)
    return True

if __name__ == "__main__":
    main()
