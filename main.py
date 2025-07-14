# main.py
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
import uvicorn
import os
from databases import Database
import asyncpg
from sqlalchemy import create_engine, MetaData, Table, Column, String, DateTime, Text, Integer, select
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import and_
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Configuration
from dotenv import load_dotenv
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://username:password@localhost:5432/kpa_forms"
)

# App configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")

# Database setup
database = Database(DATABASE_URL)
metadata = MetaData()

# Define tables
wheel_specifications = Table(
    "wheel_specifications",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("form_number", String(100), unique=True, nullable=False),
    Column("submitted_by", String(100), nullable=False),
    Column("submitted_date", DateTime, nullable=False),
    Column("fields", JSON, nullable=False),
    Column("status", String(50), default="Saved"),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
)

# Pydantic models for validation
class WheelSpecificationFields(BaseModel):
    treadDiameterNew: Optional[str] = Field(None, max_length=100)
    lastShopIssueSize: Optional[str] = Field(None, max_length=100)
    condemningDia: Optional[str] = Field(None, max_length=100)
    wheelGauge: Optional[str] = Field(None, max_length=100)
    variationSameAxle: Optional[str] = Field(None, max_length=50)
    variationSameBogie: Optional[str] = Field(None, max_length=50)
    variationSameCoach: Optional[str] = Field(None, max_length=50)
    wheelProfile: Optional[str] = Field(None, max_length=100)
    intermediateWWP: Optional[str] = Field(None, max_length=100)
    bearingSeatDiameter: Optional[str] = Field(None, max_length=100)
    rollerBearingOuterDia: Optional[str] = Field(None, max_length=100)
    rollerBearingBoreDia: Optional[str] = Field(None, max_length=100)
    rollerBearingWidth: Optional[str] = Field(None, max_length=100)
    axleBoxHousingBoreDia: Optional[str] = Field(None, max_length=100)
    wheelDiscWidth: Optional[str] = Field(None, max_length=100)

class WheelSpecificationCreate(BaseModel):
    formNumber: str = Field(..., min_length=1, max_length=100, description="Unique form number")
    submittedBy: str = Field(..., min_length=1, max_length=100, description="User who submitted the form")
    submittedDate: str = Field(..., regex=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format")
    fields: WheelSpecificationFields
    
    @validator('formNumber')
    def validate_form_number(cls, v):
        if not v or not v.strip():
            raise ValueError('Form number cannot be empty')
        return v.strip()
    
    @validator('submittedBy')
    def validate_submitted_by(cls, v):
        if not v or not v.strip():
            raise ValueError('Submitted by cannot be empty')
        return v.strip()
    
    @validator('submittedDate')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')

class WheelSpecificationResponse(BaseModel):
    formNumber: str
    submittedBy: str
    submittedDate: str
    status: str

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Any

class WheelSpecificationGetResponse(BaseModel):
    formNumber: str
    submittedBy: str
    submittedDate: str
    fields: Dict[str, Any]

# Database connection manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    try:
        await database.connect()
        logger.info("Database connected successfully")
        
        # Create tables if they don't exist
        engine = create_engine(DATABASE_URL)
        metadata.create_all(engine)
        logger.info("Database tables created/verified")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down application...")
        await database.disconnect()
        logger.info("Database disconnected")

# Create FastAPI app
app = FastAPI(
    title="KPA Forms API",
    description="API for managing KPA wheel specification form submissions",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get database connection
async def get_database():
    return database

# API Endpoints

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "KPA Forms API is running",
        "version": "1.0.0",
        "status": "healthy"
    }

@app.post("/api/forms/wheel-specifications", response_model=ApiResponse, status_code=201, tags=["Wheel Specifications"])
async def create_wheel_specification(
    wheel_spec: WheelSpecificationCreate,
    db: Database = Depends(get_database)
):
    """
    Submit a new wheel specification form
    
    - **formNumber**: Unique identifier for the form
    - **submittedBy**: User who submitted the form
    - **submittedDate**: Submission date in YYYY-MM-DD format
    - **fields**: Wheel specification data
    """
    try:
        logger.info(f"Attempting to create wheel specification: {wheel_spec.formNumber}")
        
        # Check if form number already exists
        existing_query = "SELECT form_number FROM wheel_specifications WHERE form_number = :form_number"
        existing = await db.fetch_one(existing_query, {"form_number": wheel_spec.formNumber})
        
        if existing:
            logger.warning(f"Form number {wheel_spec.formNumber} already exists")
            raise HTTPException(
                status_code=400,
                detail=f"Form number {wheel_spec.formNumber} already exists"
            )
        
        # Convert date string to datetime object
        submitted_date = datetime.strptime(wheel_spec.submittedDate, '%Y-%m-%d')
        
        # Insert new wheel specification
        insert_query = """
            INSERT INTO wheel_specifications (form_number, submitted_by, submitted_date, fields, status, created_at)
            VALUES (:form_number, :submitted_by, :submitted_date, :fields, :status, :created_at)
        """
        
        values = {
            "form_number": wheel_spec.formNumber,
            "submitted_by": wheel_spec.submittedBy,
            "submitted_date": submitted_date,
            "fields": wheel_spec.fields.dict(),
            "status": "Saved",
            "created_at": datetime.utcnow()
        }
        
        await db.execute(insert_query, values)
        logger.info(f"Successfully created wheel specification: {wheel_spec.formNumber}")
        
        return ApiResponse(
            success=True,
            message="Wheel specification submitted successfully.",
            data=WheelSpecificationResponse(
                formNumber=wheel_spec.formNumber,
                submittedBy=wheel_spec.submittedBy,
                submittedDate=wheel_spec.submittedDate,
                status="Saved"
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating wheel specification: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/api/forms/wheel-specifications", response_model=ApiResponse, tags=["Wheel Specifications"])
async def get_wheel_specifications(
    formNumber: Optional[str] = Query(None, description="Filter by form number"),
    submittedBy: Optional[str] = Query(None, description="Filter by submitted by"),
    submittedDate: Optional[str] = Query(None, description="Filter by submitted date (YYYY-MM-DD)"),
    db: Database = Depends(get_database)
):
    """
    Retrieve wheel specifications with optional filters
    
    - **formNumber**: Filter by specific form number
    - **submittedBy**: Filter by user who submitted
    - **submittedDate**: Filter by submission date (YYYY-MM-DD)
    """
    try:
        logger.info(f"Fetching wheel specifications with filters: formNumber={formNumber}, submittedBy={submittedBy}, submittedDate={submittedDate}")
        
        # Build query with filters
        query = "SELECT * FROM wheel_specifications WHERE 1=1"
        values = {}
        
        if formNumber:
            query += " AND form_number = :form_number"
            values["form_number"] = formNumber.strip()
            
        if submittedBy:
            query += " AND submitted_by = :submitted_by"
            values["submitted_by"] = submittedBy.strip()
            
        if submittedDate:
            try:
                # Validate date format
                datetime.strptime(submittedDate, '%Y-%m-%d')
                query += " AND DATE(submitted_date) = :submitted_date"
                values["submitted_date"] = submittedDate
            except ValueError:
                logger.warning(f"Invalid date format provided: {submittedDate}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        
        query += " ORDER BY created_at DESC"
        
        # Execute query
        results = await db.fetch_all(query, values)
        logger.info(f"Found {len(results)} wheel specifications")
        
        # Format response
        formatted_results = []
        for row in results:
            formatted_results.append(WheelSpecificationGetResponse(
                formNumber=row["form_number"],
                submittedBy=row["submitted_by"],
                submittedDate=row["submitted_date"].strftime('%Y-%m-%d'),
                fields=row["fields"]
            ))
        
        return ApiResponse(
            success=True,
            message="Filtered wheel specification forms fetched successfully.",
            data=formatted_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching wheel specifications: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/api/forms/wheel-specifications/{form_number}", response_model=ApiResponse, tags=["Wheel Specifications"])
async def get_wheel_specification_by_id(
    form_number: str,
    db: Database = Depends(get_database)
):
    """
    Retrieve a specific wheel specification by form number
    
    - **form_number**: The unique form number to retrieve
    """
    try:
        logger.info(f"Fetching wheel specification: {form_number}")
        
        query = "SELECT * FROM wheel_specifications WHERE form_number = :form_number"
        result = await db.fetch_one(query, {"form_number": form_number})
        
        if not result:
            logger.warning(f"Wheel specification not found: {form_number}")
            raise HTTPException(
                status_code=404,
                detail=f"Wheel specification with form number {form_number} not found"
            )
        
        formatted_result = WheelSpecificationGetResponse(
            formNumber=result["form_number"],
            submittedBy=result["submitted_by"],
            submittedDate=result["submitted_date"].strftime('%Y-%m-%d'),
            fields=result["fields"]
        )
        
        return ApiResponse(
            success=True,
            message="Wheel specification fetched successfully.",
            data=formatted_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching wheel specification {form_number}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )

@app.delete("/api/forms/wheel-specifications/{form_number}", response_model=ApiResponse, tags=["Wheel Specifications"])
async def delete_wheel_specification(
    form_number: str,
    db: Database = Depends(get_database)
):
    """
    Delete a wheel specification by form number
    
    - **form_number**: The unique form number to delete
    """
    try:
        logger.info(f"Attempting to delete wheel specification: {form_number}")
        
        # Check if form exists
        check_query = "SELECT form_number FROM wheel_specifications WHERE form_number = :form_number"
        existing = await db.fetch_one(check_query, {"form_number": form_number})
        
        if not existing:
            logger.warning(f"Wheel specification not found for deletion: {form_number}")
            raise HTTPException(
                status_code=404,
                detail=f"Wheel specification with form number {form_number} not found"
            )
        
        # Delete the record
        delete_query = "DELETE FROM wheel_specifications WHERE form_number = :form_number"
        await db.execute(delete_query, {"form_number": form_number})
        
        logger.info(f"Successfully deleted wheel specification: {form_number}")
        
        return ApiResponse(
            success=True,
            message=f"Wheel specification {form_number} deleted successfully.",
            data=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting wheel specification {form_number}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check(db: Database = Depends(get_database)):
    """
    Health check endpoint to verify API and database connectivity
    """
    try:
        # Test database connection
        await db.fetch_one("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {
        "success": False,
        "message": "Resource not found",
        "data": None
    }

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {
        "success": False,
        "message": "Internal server error",
        "data": None
    }

if __name__ == "__main__":
    logger.info(f"Starting KPA Forms API on {API_HOST}:{API_PORT}")
    uvicorn.run(
        app, 
        host=API_HOST, 
        port=API_PORT,
        log_level="info"
    )