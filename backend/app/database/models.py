import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class FileModel(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String(1024), unique=True, nullable=False, index=True)
    file_name = Column(String(255), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False, index=True) # SHA-256
    category = Column(String(128), nullable=False, index=True)
    title = Column(String(512), nullable=True)
    tags = Column(JSON, default=list) # List of tag strings
    source_refs = Column(JSON, default=list)
    last_modified = Column(DateTime, nullable=False)
    indexed_at = Column(DateTime, default=datetime.datetime.utcnow)
    version = Column(Integer, default=1)

    chunks = relationship("ChunkModel", back_populates="file", cascade="all, delete-orphan")
    outgoing_relationships = relationship("FileRelationshipModel", back_populates="source_file", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<File(id={self.id}, name='{self.file_name}', category='{self.category}')>"


class ChunkModel(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    heading = Column(String(512), nullable=True)
    content = Column(Text, nullable=False)
    
    file = relationship("FileModel", back_populates="chunks")

    def __repr__(self):
        return f"<Chunk(id={self.id}, file_id={self.file_id}, index={self.chunk_index}, heading='{self.heading}')>"


class FileRelationshipModel(Base):
    __tablename__ = "file_relationships"

    id = Column(Integer, primary_key=True, index=True)
    source_file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    target_file_name = Column(String(255), nullable=False, index=True)
    relationship_type = Column(String(64), default="wikilink") # wikilink, explicit_related, category

    source_file = relationship("FileModel", back_populates="outgoing_relationships")

    def __repr__(self):
        return f"<FileRelationship(source_id={self.source_file_id}, target='{self.target_file_name}')>"


class GenerationRecordModel(Base):
    __tablename__ = "generations"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(String(64), unique=True, nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    topics = Column(JSON, default=list)
    source_files = Column(JSON, default=list)
    file_path = Column(String(1024), nullable=False)
    timezone = Column(String(64), default="Asia/Kolkata")
    created_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<GenerationRecord(record_id='{self.record_id}', created_at='{self.created_at}')>"
