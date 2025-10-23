from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app import crud, models, schemas
from app.database import get_db

router = APIRouter()

@router.post("/", response_model=schemas.CustomLogo)
def create_custom_logo(logo: schemas.CustomLogoCreate, db: Session = Depends(get_db)):
    db_logo = crud.create_custom_logo(db=db, logo=logo)
    return db_logo

@router.get("/", response_model=List[schemas.CustomLogo])
def read_custom_logos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logos = crud.get_custom_logos(db, skip=skip, limit=limit)
    return logos

@router.delete("/{logo_id}", response_model=schemas.CustomLogo)
def delete_custom_logo(logo_id: int, db: Session = Depends(get_db)):
    db_logo = crud.delete_custom_logo(db, logo_id=logo_id)
    if db_logo is None:
        raise HTTPException(status_code=404, detail="Logo not found")
    return db_logo
