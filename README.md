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

````bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

## Notes
- Create a `.env` file for sensitive settings
- Do not commit `.env`, `db.sqlite3`, or `media/`

## License
For educational and development use.
