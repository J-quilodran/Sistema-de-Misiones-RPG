from sqlalchemy import Column, Integer, String, ForeignKey, Table, DateTime, create_engine, text
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import uuid

from sqlalchemy.orm import declarative_base
Base = declarative_base()

personaje_mision = Table(
    'personaje_mision',
    Base.metadata,
    Column('personaje_id', Integer, ForeignKey('personajes.id')),
    Column('mision_id', Integer, ForeignKey('misiones.id')),
    Column('orden', Integer), 
    Column('fecha_asignacion', DateTime, default=datetime.utcnow)
)

class Personaje(Base):
    __tablename__ = 'personajes'
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    nivel = Column(Integer, default=1)
    experiencia = Column(Integer, default=0)
    clase = Column(String)
    

    misiones = relationship(
        "Mision", 
        secondary=personaje_mision,
        back_populates="personajes"
    )
    
    def __repr__(self):
        return f"<Personaje(nombre='{self.nombre}', nivel={self.nivel})>"

class Mision(Base):
    __tablename__ = 'misiones'
    
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, index=True)
    descripcion = Column(String)
    recompensa_xp = Column(Integer)
    dificultad = Column(Integer) 
    

    personajes = relationship(
        "Personaje", 
        secondary=personaje_mision,
        back_populates="misiones"
    )
    
    def __repr__(self):
        return f"<Mision(titulo='{self.titulo}', xp={self.recompensa_xp})>"


class ColaMisiones:
    def __init__(self, db_session, personaje_id):
        self.db = db_session
        self.personaje_id = personaje_id
    
    def enqueue(self, mision_id):
        mision = self.db.query(Mision).filter(Mision.id == mision_id).first()
        if not mision:
            raise ValueError("La misión no existe")
            
        personaje = self.db.query(Personaje).filter(Personaje.id == self.personaje_id).first()
        if not personaje:
            raise ValueError("El personaje no existe")
        
        exists = self.db.execute(
            personaje_mision.select().where(
                personaje_mision.c.personaje_id == self.personaje_id,
                personaje_mision.c.mision_id == mision_id
            )
        ).fetchone()
        
        if exists:
            raise ValueError("La misión ya está asignada a este personaje")
        

        max_orden = self.db.execute(
            text("SELECT MAX(orden) FROM personaje_mision WHERE personaje_id = :personaje_id"),
            {"personaje_id": self.personaje_id}
        ).scalar()
        
        siguiente_orden = 1 if max_orden is None else max_orden + 1
        

        self.db.execute(
            personaje_mision.insert().values(
                personaje_id=self.personaje_id,
                mision_id=mision_id,
                orden=siguiente_orden,
                fecha_asignacion=datetime.utcnow()
            )
        )
        self.db.commit()
        return mision
    
    def dequeue(self):
        if self.is_empty():
            return None
            

        resultado = self.db.execute(
            text("""
            SELECT m.*, pm.orden 
            FROM misiones m
            JOIN personaje_mision pm ON m.id = pm.mision_id
            WHERE pm.personaje_id = :personaje_id
            ORDER BY pm.orden ASC
            LIMIT 1
            """),
            {"personaje_id": self.personaje_id}
        ).fetchone()
        
        mision_id = resultado[0]
        
        self.db.execute(
            personaje_mision.delete().where(
                personaje_mision.c.personaje_id == self.personaje_id,
                personaje_mision.c.mision_id == mision_id
            )
        )
        

        self.db.execute(
            text("""
            UPDATE personaje_mision
            SET orden = orden - 1
            WHERE personaje_id = :personaje_id AND orden > :orden_eliminado
            """),
            {
                "personaje_id": self.personaje_id,
                "orden_eliminado": resultado[4]  # Acceder al índice correcto en la tupla
            }
        )
        
        self.db.commit()
        

        return self.db.query(Mision).filter(Mision.id == mision_id).first()
    
    def first(self):
        if self.is_empty():
            return None
            
        resultado = self.db.execute(
            text("""
            SELECT m.*
            FROM misiones m
            JOIN personaje_mision pm ON m.id = pm.mision_id
            WHERE pm.personaje_id = :personaje_id
            ORDER BY pm.orden ASC
            LIMIT 1
            """),
            {"personaje_id": self.personaje_id}
        ).fetchone()
        
        return self.db.query(Mision).filter(Mision.id == resultado[0]).first()
    
    def is_empty(self):
        count = self.db.execute(
            text("SELECT COUNT(*) FROM personaje_mision WHERE personaje_id = :personaje_id"),
            {"personaje_id": self.personaje_id}
        ).scalar()
        return count == 0
    
    def size(self):
        count = self.db.execute(
            text("SELECT COUNT(*) FROM personaje_mision WHERE personaje_id = :personaje_id"),
            {"personaje_id": self.personaje_id}
        ).scalar()
        return count
    
    def get_all(self):
        resultado = self.db.execute(
            text("""
            SELECT m.*
            FROM misiones m
            JOIN personaje_mision pm ON m.id = pm.mision_id
            WHERE pm.personaje_id = :personaje_id
            ORDER BY pm.orden ASC
            """),
            {"personaje_id": self.personaje_id}
        ).fetchall()
        
        misiones = []
        for row in resultado:
            mision = self.db.query(Mision).filter(Mision.id == row[0]).first()
            misiones.append(mision)
            
        return misiones