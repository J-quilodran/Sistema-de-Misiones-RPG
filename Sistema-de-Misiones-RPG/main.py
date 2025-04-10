from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import uvicorn
from pydantic import BaseModel
from typing import List, Optional

from models import Base, Personaje, Mision, ColaMisiones

# Configuración de la base de datos
SQLALCHEMY_DATABASE_URL = "sqlite:///./rpg_misiones.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crear las tablas en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema de Misiones RPG")

# Dependencia para obtener la sesión de base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Modelos Pydantic para validación de datos
class PersonajeCreate(BaseModel):
    nombre: str
    clase: str
    nivel: int = 1
    experiencia: int = 0

class PersonajeResponse(BaseModel):
    id: int
    nombre: str
    clase: str
    nivel: int
    experiencia: int
    
    class Config:
        from_attributes  = True

class MisionCreate(BaseModel):
    titulo: str
    descripcion: str
    recompensa_xp: int
    dificultad: int

class MisionResponse(BaseModel):
    id: int
    titulo: str
    descripcion: str
    recompensa_xp: int
    dificultad: int
    
    class Config:
        from_attributes  = True

# Endpoints
@app.post("/personajes", response_model=PersonajeResponse)
def crear_personaje(personaje: PersonajeCreate, db: Session = Depends(get_db)):
    db_personaje = Personaje(
        nombre=personaje.nombre,
        clase=personaje.clase,
        nivel=personaje.nivel,
        experiencia=personaje.experiencia
    )
    db.add(db_personaje)
    db.commit()
    db.refresh(db_personaje)
    return db_personaje

@app.post("/misiones", response_model=MisionResponse)
def crear_mision(mision: MisionCreate, db: Session = Depends(get_db)):
    db_mision = Mision(
        titulo=mision.titulo,
        descripcion=mision.descripcion,
        recompensa_xp=mision.recompensa_xp,
        dificultad=mision.dificultad
    )
    db.add(db_mision)
    db.commit()
    db.refresh(db_mision)
    return db_mision

@app.post("/personajes/{personaje_id}/misiones/{mision_id}", response_model=MisionResponse)
def aceptar_mision(personaje_id: int, mision_id: int, db: Session = Depends(get_db)):
    # Verificar que el personaje existe
    personaje = db.query(Personaje).filter(Personaje.id == personaje_id).first()
    if not personaje:
        raise HTTPException(status_code=404, detail="Personaje no encontrado")
    
    # Verificar que la misión existe
    mision = db.query(Mision).filter(Mision.id == mision_id).first()
    if not mision:
        raise HTTPException(status_code=404, detail="Misión no encontrada")
    
    # Usar la cola para añadir la misión
    cola = ColaMisiones(db, personaje_id)
    try:
        cola.enqueue(mision_id)
        return mision
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/personajes/{personaje_id}/completar", response_model=PersonajeResponse)
def completar_mision(personaje_id: int, db: Session = Depends(get_db)):
    # Verificar que el personaje existe
    personaje = db.query(Personaje).filter(Personaje.id == personaje_id).first()
    if not personaje:
        raise HTTPException(status_code=404, detail="Personaje no encontrado")
    
    # Usar la cola para completar (desencolar) la primera misión
    cola = ColaMisiones(db, personaje_id)
    
    if cola.is_empty():
        raise HTTPException(status_code=400, detail="El personaje no tiene misiones pendientes")
    
    mision = cola.dequeue()
    
    # Actualizar la experiencia del personaje
    personaje.experiencia += mision.recompensa_xp
    
    # Subir de nivel si corresponde (ejemplo simple: 100 XP por nivel)
    nuevo_nivel = (personaje.experiencia // 100) + 1
    if nuevo_nivel > personaje.nivel:
        personaje.nivel = nuevo_nivel
    
    db.commit()
    db.refresh(personaje)
    return personaje

@app.get("/personajes/{personaje_id}/misiones", response_model=List[MisionResponse])
def listar_misiones(personaje_id: int, db: Session = Depends(get_db)):
    # Verificar que el personaje existe
    personaje = db.query(Personaje).filter(Personaje.id == personaje_id).first()
    if not personaje:
        raise HTTPException(status_code=404, detail="Personaje no encontrado")
    
    # Usar la cola para obtener las misiones en orden FIFO
    cola = ColaMisiones(db, personaje_id)
    return cola.get_all()

@app.get("/personajes", response_model=List[PersonajeResponse])
def listar_personajes(db: Session = Depends(get_db)):
    return db.query(Personaje).all()

@app.get("/misiones", response_model=List[MisionResponse])
def listar_todas_misiones(db: Session = Depends(get_db)):
    return db.query(Mision).all()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
