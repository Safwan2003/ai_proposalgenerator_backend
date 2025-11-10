from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.post("/", response_model=schemas.UserImage, summary="Create a new user image", description="Uploads a new user image and saves it to the database.")
async def create_user_image(image: schemas.UserImageCreate, db: AsyncSession = Depends(get_db)):
    return await crud.create_user_image(db=db, image=image)

@router.get("/", response_model=List[schemas.UserImage], summary="Get all user images", description="Returns a list of all user-uploaded images.")
async def read_user_images(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    images = await crud.get_user_images(db, skip=skip, limit=limit)
    return images

@router.delete("/{image_id}", response_model=schemas.UserImage, summary="Delete a user image", description="Deletes a specific user image from the database.")
async def delete_user_image(image_id: int, db: AsyncSession = Depends(get_db)):
    db_image = await crud.delete_user_image(db, image_id=image_id)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return db_image
