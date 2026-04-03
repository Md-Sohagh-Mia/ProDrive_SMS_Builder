# ProDrive_SMS_Builder

This project aims to design and develop an automated digital management system for a transport company. The system will help the company manage operational data digitally, convert company manuals into an accessible digital format, and implement digital forms to streamline internal processes. The goal is to improve efficiency, reduce paperwork.

---

## Customer Authentication System (Django + MySQL)

A full customer login/logout system has been implemented using **Django 4.x** and **MySQL**.

### Features

- **Custom Customer model** extending Django's `AbstractBaseUser`
  - Fields: `email`, `username`, `full_name`, `phone_number`, `company_name`, `abn`, `address`, `role`, `is_active`, `created_at`, `updated_at`, `failed_login_attempts`
- **Login** – accepts email *or* username + password, session-based authentication, "remember me" option, account lock-out after 5 failed attempts
- **Logout** – POST-based with confirmation page, destroys session
- **Signup** – full company registration form with password strength meter and Terms acceptance
- **Dashboard** – login-required view showing account details and quick actions
- **CSRF protection** on all forms
- **Password hashing** via Django's PBKDF2 by default
- **Admin interface** fully configured for customer management

### Project Layout

```
ProDrive_SMS_Builder/
├── manage.py
├── requirements.txt
├── prodrive/                    # Django project package
│   ├── settings.py              # MySQL database config, auth settings
│   ├── urls.py                  # Root URL routing
│   ├── wsgi.py
│   └── asgi.py
├── auth_system/                 # Authentication Django app
│   ├── models.py                # Customer model
│   ├── forms.py                 # LoginForm, SignupForm
│   ├── views.py                 # login, logout, signup, dashboard views
│   ├── urls.py                  # /auth/ URL patterns
│   ├── backends.py              # Email-or-username auth backend
│   ├── admin.py                 # Admin interface
│   ├── tests.py                 # 35 unit/integration tests
│   └── migrations/
│       └── 0001_initial.py
└── templates/
    └── auth_system/
        ├── base.html
        ├── login.html
        ├── signup.html
        ├── logout_confirm.html
        └── dashboard.html
```

### URL Routes

| URL | View | Description |
|-----|------|-------------|
| `/` | Redirect | → `/auth/login/` |
| `/auth/login/` | `login_view` | Sign-in page |
| `/auth/logout/` | `logout_view` | Confirmation + logout |
| `/auth/signup/` | `signup_view` | Company registration |
| `/auth/dashboard/` | `dashboard_view` | Authenticated dashboard |
| `/admin/` | Django admin | Customer management |

### Setup Instructions

#### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `mysqlclient` requires the MySQL client libraries. On Ubuntu/Debian: `sudo apt-get install libmysqlclient-dev`. On macOS: `brew install mysql-client`.

#### 2. Configure MySQL

Create the database and user:

```sql
CREATE DATABASE prodrive_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'prodrive_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON prodrive_db.* TO 'prodrive_user'@'localhost';
FLUSH PRIVILEGES;
```

#### 3. Set environment variables

```bash
export DJANGO_SECRET_KEY='your-long-random-secret-key'
export DB_NAME='prodrive_db'
export DB_USER='prodrive_user'
export DB_PASSWORD='your_secure_password'
export DB_HOST='localhost'
export DB_PORT='3306'
export DJANGO_DEBUG='False'           # set to True for development
export DJANGO_ALLOWED_HOSTS='yourdomain.com'
```

#### 4. Apply migrations

```bash
python manage.py migrate
```

#### 5. Create an admin superuser

```bash
python manage.py createsuperuser
```

#### 6. Run the development server

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/` – you will be redirected to the login page.

### Running Tests

```bash
python manage.py test auth_system
```

All 35 tests cover models, forms, the authentication backend, and all views.
