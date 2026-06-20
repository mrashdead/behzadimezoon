![Python](https://img.shields.io/badge/Python-3.x-blue)
![Django](https://img.shields.io/badge/Django-Framework-green)
![Status](https://img.shields.io/badge/Status-Development-orange)
![License](https://img.shields.io/badge/License-Custom-lightgrey)

# Django Management & Reservation System

A Django-based web application for custom authentication, profile management, role-based access control, and reservation workflows.

## Features

- Custom user model
- Login/logout system
- Profile management
- Admin user management
- Reservation workflow structure

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Notes
- Create a `.env` file for sensitive settings
- Do not commit `.env`, `db.sqlite3`, or `media/`

## Running Tests

For local testing, activate your virtual environment and run:

```bash
source venv/bin/activate
python manage.py test customers.tests.CustomerFormDateParsingTests
```

If you are using PostgreSQL locally, make sure the database user has permission to create test databases (CREATEDB), otherwise the tests will fail with a permission error.

To run the full account/test suite:

```bash
python manage.py test accounts
```

## License
For educational and development use.
