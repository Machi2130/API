#!/usr/bin/env python3
"""
Database Setup Script for Wheel Specifications API
This script helps set up the PostgreSQL database and tables.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://machi:Machi5500@localhost:5432/api"
)

async def create_database_and_tables():
    """Create database and tables if they don't exist"""
    try:
        # Extract database name from URL
        db_name = DATABASE_URL.split('/')[-1]
        base_url = DATABASE_URL.rsplit('/', 1)[0]
        
        print(f"Setting up database: {db_name}")
        
        # Connect to postgres database to create our target database
        postgres_url = f"{base_url}/postgres"
        
        try:
            conn = await asyncpg.connect(postgres_url)
            
            # Check if database exists
            db_exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            
            if not db_exists:
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                print(f"✓ Created database: {db_name}")
            else:
                print(f"✓ Database already exists: {db_name}")
            
            await conn.close()
            
        except Exception as e:
            print(f"Error creating database: {e}")
            print("Make sure PostgreSQL is running and credentials are correct")
            return False
        
        # Now connect to our target database and create tables
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            
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
            
            print("✓ Tables and indexes created successfully")
            
            # Show table info
            table_info = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'wheel_specifications'
                ORDER BY ordinal_position
            """)
            
            print("\nTable structure:")
            print("-" * 50)
            for row in table_info:
                nullable = "NULL" if row["is_nullable"] == "YES" else "NOT NULL"
                print(f"{row['column_name']:<20} {row['data_type']:<20} {nullable}")
            
            await conn.close()
            print("\n✓ Database setup completed successfully!")
            return True
            
        except Exception as e:
            print(f"Error creating tables: {e}")
            return False
            
    except Exception as e:
        print(f"General error: {e}")
        return False

async def check_database_connection():
    """Check if we can connect to the database"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Test query
        result = await conn.fetchval("SELECT 1")
        
        if result == 1:
            print("✓ Database connection successful!")
            
            # Check if table exists and get record count
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM wheel_specifications
            """)
            
            print(f"✓ wheel_specifications table has {count} records")
            
        await conn.close()
        return True
        
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

async def main():
    print("Wheel Specifications Database Setup")
    print("=" * 40)
    
    # First try to connect to existing database
    if await check_database_connection():
        print("Database is already set up and working!")
        return
    
    print("\nSetting up database...")
    if await create_database_and_tables():
        print("\nVerifying setup...")
        await check_database_connection()
    else:
        print("\nSetup failed. Please check your database configuration.")

if __name__ == "__main__":
    asyncio.run(main())
