from sqlalchemy.orm import Session
from . import models, schemas

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate, hashed_password: str):
    try:
        db_user = models.User(email=user.email, hashed_password=hashed_password)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        db.rollback()
        print(f"Error creating user: {e}")
        raise

def add_pdf(db: Session, file_name: str, file_path: str, user_id: int):
    try:
        db_file = models.PDFFile(
            file_name=file_name,
            file_path=file_path,
            user_id=user_id
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        return db_file
    except Exception as e:
        db.rollback()
        print(f"Error adding PDF: {e}")
        raise


def get_pdfs_by_user(db: Session, user_id: int):
    try:
        return db.query(models.PDFFile).filter(models.PDFFile.user_id == user_id).all()
    except Exception as e:
        print(f"Error getting PDFs: {e}")
        return []

def delete_pdf(db: Session, pdf_id: int, user_id: int):
    try:
        file = db.query(models.PDFFile).filter(
            models.PDFFile.id == pdf_id,
            models.PDFFile.user_id == user_id
        ).first()
        if file:
            db.delete(file)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        print(f"Error deleting PDF: {e}")
        return False

def add_action(db: Session, action: str, filename: str, user_id: int):
    try:
        record = models.ActionHistory(action=action, filename=filename, user_id=user_id)
        db.add(record)
        db.commit()
        return record
    except Exception as e:
        db.rollback()
        print(f"Error adding action: {e}")
        raise

def get_history(db: Session, user_id: int):
    try:
        return db.query(models.ActionHistory).filter(
            models.ActionHistory.user_id == user_id
        ).all()
    except Exception as e:
        print(f"Error getting history: {e}")
        return []
