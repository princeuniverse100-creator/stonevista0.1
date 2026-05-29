"""
Run once: python migrate3.py
Adds all new columns and creates new tables.
"""
from main import app, db

with app.app_context():
    stmts = [
        'ALTER TABLE seller ADD COLUMN IF NOT EXISTS email VARCHAR(200)',
        'ALTER TABLE seller ADD COLUMN IF NOT EXISTS years_experience INTEGER DEFAULT 0',
        'ALTER TABLE seller ADD COLUMN IF NOT EXISTS business_type VARCHAR(100)',
        'ALTER TABLE seller ADD COLUMN IF NOT EXISTS bulk_available BOOLEAN DEFAULT FALSE',
        'ALTER TABLE seller ADD COLUMN IF NOT EXISTS delivery_areas TEXT',
        'ALTER TABLE marble ADD COLUMN IF NOT EXISTS marble_name VARCHAR(200)',
        'ALTER TABLE marble ADD COLUMN IF NOT EXISTS marble_type VARCHAR(100)',
        'ALTER TABLE marble ADD COLUMN IF NOT EXISTS origin VARCHAR(200)',
        'ALTER TABLE marble ADD COLUMN IF NOT EXISTS finish VARCHAR(100)',
        'ALTER TABLE marble ADD COLUMN IF NOT EXISTS thickness VARCHAR(100)',
        'ALTER TABLE marble ADD COLUMN IF NOT EXISTS available_sizes VARCHAR(300)',
        'ALTER TABLE marble ADD COLUMN IF NOT EXISTS marble_desc TEXT',
    ]
    for stmt in stmts:
        try:
            db.session.execute(db.text(stmt))
            print(f"OK: {stmt[:55]}...")
        except Exception as e:
            print(f"Skip: {e}")
    db.session.commit()
    db.create_all()
    print("\nDone! Run python main.py to start.")
