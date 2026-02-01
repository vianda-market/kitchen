# Project Folder Structure
This is a simple project folder structure for a Python application. It includes directories for the main application code, database-related code, and utility functions. The structure is designed to be clean and organized, making it easy to navigate and maintain.

project_root/
├── app/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.sql
│   ├── db/
│   │   ├── __init__.py
│   │   ├── index.sql
│   │   ├── shema.sql
│   │   ├── seed.sql
│   │   ├── test_db_dev.sh
│   │   ├── test.sql
│   │   └── trigger.sql
│   ├── models/
│   │   ├── __init__.py
│   │   ├── address.py
│   │   ├── institution.py
│   │   ├── institution_entity.py
│   │   ├── plate.py
│   │   ├── product.py
│   │   ├── restaurant.py
│   │   ├── role.py
│   │   └── user.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   └── other.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── address.py
│   │   ├── institution.py
│   │   ├── institution_entity.py
│   │   ├── plate.py
│   │   ├── product.py
│   │   ├── restaurant.py
│   │   ├── role.py
│   │   └── user.py
│   ├── tests/
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   └── setup.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── test_address.py
│   │   │   ├── test_institution_entity.py
│   │   │   ├── test_institution.py
│   │   │   ├── test_plate.py
│   │   │   ├── test_product.py
│   │   │   ├── test_restaurant.py
│   │   │   ├── test_role.py
│   │   │   └── test_user.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── test_user.py
│   │   │   └── xxx.py
│   │   ├── __init__.py    
│   └── utils/
│       ├── __init__.py
│       ├── auth.py
│       ├── db.py
│       └── log.py
├── venv/
├── .env
├── .gitignore
├── application.py
├── readme.txt
└── requirements.txt
