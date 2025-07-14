from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import asyncpg
import os
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager
import traceback
import json

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://machi:Machi5500@localhost:5432/api"
)

# Database connection pool
class DatabaseManager:
    def __init__(self):
        self.pool = None

    async def create_pool(self):
        try:
            self.pool = await asyncpg.create_pool(DATABASE_URL)
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise

    async def close_pool(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    async def get_connection(self):
        if not self.pool:
            await self.create_pool()
        return await self.pool.acquire()

db_manager = DatabaseManager()

# Database initialization
async def init_database():
    """Initialize database and create tables if they don't exist"""
    try:
        # First, try to connect to the database
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.close()
        logger.info("Connected to existing database")
    except Exception as e:
        logger.info(f"Database connection failed: {e}")
        # Try to create the database
        try:
            # Extract database name from URL
            db_name = DATABASE_URL.split('/')[-1]
            base_url = DATABASE_URL.rsplit('/', 1)[0]
            
            # Connect to postgres database to create our target database
            postgres_url = f"{base_url}/postgres"
            conn = await asyncpg.connect(postgres_url)
            
            # Check if database exists
            db_exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            
            if not db_exists:
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                logger.info(f"Created database: {db_name}")
            
            await conn.close()
        except Exception as create_error:
            logger.error(f"Failed to create database: {create_error}")
            raise

    # Now create the connection pool and tables
    await db_manager.create_pool()
    
    conn = await db_manager.get_connection()
    try:
        # Create the wheel_specifications table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS wheel_specifications (
                id SERIAL PRIMARY KEY,
                form_number VARCHAR(100) UNIQUE NOT NULL,
                submitted_by VARCHAR(100) NOT NULL,
                submitted_date DATE NOT NULL,
                fields JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wheel_specs_form_number 
            ON wheel_specifications(form_number)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wheel_specs_submitted_by 
            ON wheel_specifications(submitted_by)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wheel_specs_submitted_date 
            ON wheel_specifications(submitted_date)
        """)
        
        logger.info("Database tables created successfully")
    finally:
        await db_manager.pool.release(conn)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_database()
    yield
    # Shutdown
    await db_manager.close_pool()

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="KPA Forms - Wheel Specifications API",
    description="API for managing wheel specification forms",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class WheelSpecificationFields(BaseModel):
    treadDiameterNew: Optional[str] = Field(None, description="Tread diameter new specification")
    lastShopIssueSize: Optional[str] = Field(None, description="Last shop issue size")
    condemningDia: Optional[str] = Field(None, description="Condemning diameter")
    wheelGauge: Optional[str] = Field(None, description="Wheel gauge specification")
    variationSameAxle: Optional[str] = Field(None, description="Variation same axle")
    variationSameBogie: Optional[str] = Field(None, description="Variation same bogie")
    variationSameCoach: Optional[str] = Field(None, description="Variation same coach")
    wheelProfile: Optional[str] = Field(None, description="Wheel profile specification")
    intermediateWWP: Optional[str] = Field(None, description="Intermediate WWP")
    bearingSeatDiameter: Optional[str] = Field(None, description="Bearing seat diameter")
    rollerBearingOuterDia: Optional[str] = Field(None, description="Roller bearing outer diameter")
    rollerBearingBoreDia: Optional[str] = Field(None, description="Roller bearing bore diameter")
    rollerBearingWidth: Optional[str] = Field(None, description="Roller bearing width")
    axleBoxHousingBoreDia: Optional[str] = Field(None, description="Axle box housing bore diameter")
    wheelDiscWidth: Optional[str] = Field(None, description="Wheel disc width")

class WheelSpecificationCreate(BaseModel):
    formNumber: str = Field(..., min_length=1, max_length=100, description="Unique form number")
    submittedBy: str = Field(..., min_length=1, max_length=100, description="User who submitted the form")
    submittedDate: date = Field(..., description="Date when form was submitted")
    fields: WheelSpecificationFields

    @field_validator('formNumber')
    @classmethod
    def validate_form_number(cls, v):
        if not v.strip():
            raise ValueError('Form number cannot be empty')
        return v.strip()

    @field_validator('submittedBy')
    @classmethod
    def validate_submitted_by(cls, v):
        if not v.strip():
            raise ValueError('Submitted by cannot be empty')
        return v.strip()

class WheelSpecificationResponse(BaseModel):
    id: int
    formNumber: str
    submittedBy: str
    submittedDate: date
    fields: Dict[str, Any]
    createdAt: datetime
    updatedAt: datetime

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

# Database dependency
async def get_db():
    conn = await db_manager.get_connection()
    try:
        yield conn
    finally:
        await db_manager.pool.release(conn)

# Helper function to properly handle JSONB data
def parse_jsonb_field(field_value):
    """Parse JSONB field ensuring it returns a proper dict"""
    if field_value is None:
        return {}
    if isinstance(field_value, str):
        try:
            return json.loads(field_value)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON string: {field_value}")
            return {}
    elif isinstance(field_value, dict):
        return field_value
    else:
        logger.warning(f"Unexpected field type: {type(field_value)}")
        return {}

# API Routes
@app.get("/", response_model=Dict[str, str])
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "KPA Forms - Wheel Specifications API",
        "version": "1.0.0"
    }

@app.post("/api/forms/wheel-specifications", response_model=APIResponse)
async def create_wheel_specification(
    wheel_spec: WheelSpecificationCreate,
    conn=Depends(get_db)
):
    """Create a new wheel specification form"""
    try:
        # Check if form number already exists
        existing = await conn.fetchrow(
            "SELECT id FROM wheel_specifications WHERE form_number = $1",
            wheel_spec.formNumber
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Form number '{wheel_spec.formNumber}' already exists"
            )

        # Convert fields to dict for JSONB insertion
        fields_data = (
            wheel_spec.fields.model_dump()
            if hasattr(wheel_spec.fields, "model_dump")
            else wheel_spec.fields.dict()
        )

        # Insert new record - let PostgreSQL handle the JSONB conversion
        record = await conn.fetchrow("""
            INSERT INTO wheel_specifications 
            (form_number, submitted_by, submitted_date, fields)
            VALUES ($1, $2, $3, $4)
            RETURNING id, form_number, submitted_by, submitted_date, fields, created_at, updated_at
        """,
            wheel_spec.formNumber,
            wheel_spec.submittedBy,
            wheel_spec.submittedDate,
            json.dumps(fields_data)  # Convert to JSON string
        )

        logger.info(f"Created wheel specification: {wheel_spec.formNumber}")

        return APIResponse(
            success=True,
            message="Wheel specification form submitted successfully",
            data={
                "id": record["id"],
                "formNumber": record["form_number"],
                "submittedBy": record["submitted_by"],
                "submittedDate": record["submitted_date"].isoformat(),
                "fields": parse_jsonb_field(record["fields"]),  # ✅ Properly parse JSONB
                "createdAt": record["created_at"].isoformat(),
                "updatedAt": record["updated_at"].isoformat()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error creating wheel specification: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while creating wheel specification"
        )

@app.get("/api/forms/wheel-specifications", response_model=APIResponse)
async def get_wheel_specifications(
    form_number: Optional[str] = Query(None, description="Filter by form number"),
    submitted_by: Optional[str] = Query(None, description="Filter by submitted by"),
    submitted_date: Optional[date] = Query(None, description="Filter by submitted date"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    conn=Depends(get_db)
):
    """Get wheel specifications with optional filtering"""
    try:
        # Build query conditions
        conditions = []
        params = []
        param_count = 0
        
        if form_number:
            param_count += 1
            conditions.append(f"form_number ILIKE ${param_count}")
            params.append(f"%{form_number}%")
        
        if submitted_by:
            param_count += 1
            conditions.append(f"submitted_by ILIKE ${param_count}")
            params.append(f"%{submitted_by}%")
        
        if submitted_date:
            param_count += 1
            conditions.append(f"submitted_date = ${param_count}")
            params.append(submitted_date)
        
        # Build WHERE clause
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        # Add limit and offset
        param_count += 1
        limit_clause = f"LIMIT ${param_count}"
        params.append(limit)
        
        param_count += 1
        offset_clause = f"OFFSET ${param_count}"
        params.append(offset)
        
        # Execute query
        query = f"""
            SELECT id, form_number, submitted_by, submitted_date, fields, created_at, updated_at
            FROM wheel_specifications
            {where_clause}
            ORDER BY created_at DESC
            {limit_clause} {offset_clause}
        """
        
        records = await conn.fetch(query, *params)
        
        # Get total count for pagination info
        count_query = f"""
            SELECT COUNT(*) as total
            FROM wheel_specifications
            {where_clause}
        """
        
        total_count = await conn.fetchval(count_query, *params[:-2])  # Exclude limit and offset params
        
        # Format response
        data = []
        for record in records:
            data.append({
                "id": record["id"],
                "formNumber": record["form_number"],
                "submittedBy": record["submitted_by"],
                "submittedDate": record["submitted_date"].isoformat(),
                "fields": parse_jsonb_field(record["fields"]),  # ✅ Properly parse JSONB
                "createdAt": record["created_at"].isoformat(),
                "updatedAt": record["updated_at"].isoformat()
            })
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(data)} wheel specifications",
            data=data
        )
        
    except Exception as e:
        logger.error(f"Error retrieving wheel specifications: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while retrieving wheel specifications"
        )

@app.get("/api/forms/wheel-specifications/{form_number}", response_model=APIResponse)
async def get_wheel_specification_by_form_number(
    form_number: str,
    conn=Depends(get_db)
):
    """Get a specific wheel specification by form number"""
    try:
        record = await conn.fetchrow("""
            SELECT id, form_number, submitted_by, submitted_date, fields, created_at, updated_at
            FROM wheel_specifications
            WHERE form_number = $1
        """, form_number)
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Wheel specification with form number '{form_number}' not found"
            )
        
        data = {
            "id": record["id"],
            "formNumber": record["form_number"],
            "submittedBy": record["submitted_by"],
            "submittedDate": record["submitted_date"].isoformat(),
            "fields": parse_jsonb_field(record["fields"]),  # ✅ Properly parse JSONB
            "createdAt": record["created_at"].isoformat(),
            "updatedAt": record["updated_at"].isoformat()
        }
        
        return APIResponse(
            success=True,
            message="Wheel specification retrieved successfully",
            data=data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving wheel specification: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while retrieving wheel specification"
        )

@app.put("/api/forms/wheel-specifications/{form_number}", response_model=APIResponse)
async def update_wheel_specification(
    form_number: str,
    wheel_spec: WheelSpecificationCreate,
    conn=Depends(get_db)
):
    """Update an existing wheel specification form"""
    try:
        # Check if record exists
        existing = await conn.fetchrow(
            "SELECT id FROM wheel_specifications WHERE form_number = $1",
            form_number
        )
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Wheel specification with form number '{form_number}' not found"
            )
        
        # Convert fields to dict for JSONB insertion
        fields_data = (
            wheel_spec.fields.model_dump()
            if hasattr(wheel_spec.fields, "model_dump")
            else wheel_spec.fields.dict()
        )
        
        # Update record
        record = await conn.fetchrow("""
            UPDATE wheel_specifications 
            SET form_number = $1, submitted_by = $2, submitted_date = $3, 
                fields = $4, updated_at = CURRENT_TIMESTAMP
            WHERE form_number = $5
            RETURNING id, form_number, submitted_by, submitted_date, fields, created_at, updated_at
        """, 
            wheel_spec.formNumber,
            wheel_spec.submittedBy,
            wheel_spec.submittedDate,
            json.dumps(fields_data),  # Convert to JSON string
            form_number
        )
        
        logger.info(f"Updated wheel specification: {form_number}")
        
        return APIResponse(
            success=True,
            message="Wheel specification form updated successfully",
            data={
                "id": record["id"],
                "formNumber": record["form_number"],
                "submittedBy": record["submitted_by"],
                "submittedDate": record["submitted_date"].isoformat(),
                "fields": parse_jsonb_field(record["fields"]),  # ✅ Properly parse JSONB
                "createdAt": record["created_at"].isoformat(),
                "updatedAt": record["updated_at"].isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating wheel specification: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "true").lower() == "true"
    )