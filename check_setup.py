#!/usr/bin/env python3
"""
Setup checker script - I-check kung complete ang setup
"""
import sys
import os
from pathlib import Path

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("❌ Python 3.9+ required. Current:", f"{version.major}.{version.minor}")
        return False
    print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def check_env_file():
    """Check if .env file exists"""
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found!")
        print("   Run: copy .env.example .env")
        return False
    print("✅ .env file exists")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    required = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "psycopg2",
        "redis",
        "rq",
        "httpx",
        "fpdf"
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"✅ {package} installed")
        except ImportError:
            print(f"❌ {package} NOT installed")
            missing.append(package)
    
    if missing:
        print("\n❌ Missing packages. Run:")
        print("   pip install -r requirements.txt")
        return False
    return True

def check_storage_dir():
    """Check if storage directory exists"""
    storage_path = Path("storage/pdfs")
    if not storage_path.exists():
        print("⚠️  Storage directory not found. Creating...")
        storage_path.mkdir(parents=True, exist_ok=True)
        print("✅ Storage directory created")
    else:
        print("✅ Storage directory exists")
    return True

def check_redis_connection():
    """Check Redis connection"""
    try:
        import redis
        from app.config import get_settings
        
        settings = get_settings()
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("   Make sure Redis is running:")
        print("   - Docker: docker-compose up redis")
        print("   - Manual: redis-server")
        return False

def check_database_connection():
    """Check database connection"""
    try:
        from sqlalchemy import create_engine, text
        from app.config import get_settings
        
        settings = get_settings()
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("   Make sure PostgreSQL is running and database exists:")
        print("   - Docker: docker-compose up db")
        print("   - Manual: psql -U postgres -c 'CREATE DATABASE ai_research;'")
        return False

def main():
    print("=" * 60)
    print("  AI Research Platform - Setup Checker")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        (".env File", check_env_file),
        ("Dependencies", check_dependencies),
        ("Storage Directory", check_storage_dir),
    ]
    
    # Run basic checks first
    all_passed = True
    for name, check_func in checks:
        print(f"\n[{name}]")
        if not check_func():
            all_passed = False
        print()
    
    # Only check services if basic checks passed
    if all_passed:
        print("\n[Service Connections]")
        redis_ok = check_redis_connection()
        db_ok = check_database_connection()
        print()
        
        if redis_ok and db_ok:
            print("=" * 60)
            print("✅ ALL CHECKS PASSED! Ready to run:")
            print("   uvicorn app.main:app --reload")
            print("   python worker.py  (in separate terminal)")
            print("=" * 60)
        else:
            print("=" * 60)
            print("⚠️  Some services are not available.")
            print("   You can still run the API, but some features won't work.")
            print("=" * 60)
    else:
        print("=" * 60)
        print("❌ Setup incomplete. Please fix the issues above.")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
