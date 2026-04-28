## Notamil Backend - README

This document outlines the steps to set up and run the Notamil backend application locally using a conda environment.

**Prerequisites**

* **Conda:** If you don't have conda installed, download and install Miniconda or Anaconda from [https://docs.conda.io/en/latest/miniconda.html](https://docs.conda.io/en/latest/miniconda.html).


**Application Setup**

1. **Clone the Repository:**

   ```bash
   git clone git@github.com:projeto-nota-mil/redato-backend.git
   cd redato-backend
   ```

2. **Create and Activate Conda Environment:**

   ```bash
   conda create --name redato-env python=3.11  # Or your desired Python version
   conda activate redato-env
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set Environment Variables:**

   * Create a copy of the `.env.example` file and rename it to `.env`.
   * **Important:** Update the `.env` file with your chosen database credentials:
     ```
     DATABASE_URL=postgresql://admin:7562@localhost:5432/auth_db
     SECRET_KEY=your_secret_key_here 
     ALGORITHM=HS256
     ACCESS_TOKEN_EXPIRE_MINUTES=30
     ```

5. **Run Database Migrations (Optional but Recommended):**

   * While not explicitly mentioned in the provided files, using database migrations is highly recommended. If you have a migrations tool set up (e.g., Alembic), run the appropriate command to apply migrations.

**Running the Application**

1. **Start the Development Server:**

   ```bash
   uvicorn main:app --reload
   ```

The application should now be running locally. You can access the API documentation (if available) at `http://127.0.0.1:8000/docs` or interact with the API endpoints as needed.


## API Endpoints and Parameters from routes.py

### Endpoint: `/login`
**Method:** POST

#### Description:
Authenticate a user using a Firebase ID token.

#### Parameters:
- `token` (str): The Firebase ID token.
  - **Source:** Dependency injection using `Depends(oauth2_scheme)`

#### Response:
- **Success:**
  ```json
  {
      "access_token": "<token>",
      "token_type": "bearer"
  }
  ```
- **Error:**
  - Status Code: 401
    ```json
    {
        "detail": "Token inválido"
    }
    ```
  - Status Code: 500
    ```json
    {
        "detail": "An error occurred during login."
    }

### Endpoint: `/users/me`
**Method:** GET

### Description:
Retrieves information about the authenticated user.

### Parameters:
| Name   | Type   | In       | Required | Description                         |
|--------|--------|----------|----------|-------------------------------------|
| token  | string | Header   | Yes      | Bearer token in the Authorization header.|

### Responses:

#### Success:
| Status Code | Description                      | Example Response                |
|-------------|----------------------------------|----------------------------------|
| 200         | Authenticated user information. | `{ "email": "user@example.com" }`|

#### Error:
| Status Code | Description                                    |
|-------------|------------------------------------------------|
| 401         | `"Invalid token: email not found"`            |
| 401         | `"Token validation failed"`                   |

## Endpoint: `/register`

**Method:** POST

### Description:
Registers a new user in the system.

### Parameters:
| Name | Type       | In   | Required | Description                 |
|------|------------|------|----------|-----------------------------|
| user | UserCreate | Body | Yes      | JSON object with user data. |

#### `UserCreate` Object:
| Field      | Type          | Required | Description                     |
|------------|---------------|----------|---------------------------------|
| email      | EmailStr      | Yes      | User's email address.           |
| password   | string        | Yes      | User's password.                |
| name       | string        | Yes      | User's full name.               |
| login_id   | string        | Yes      | Unique login identifier.        |

### Responses:

#### Success:
| Status Code | Description                            | Example Response                                  |
|-------------|----------------------------------------|--------------------------------------------------|
| 200         | User successfully registered.          | `{ "email": "user@example.com", "uid": "abc123" }`|

#### Error:
| Status Code | Description                             |
|-------------|-----------------------------------------|
| 400         | `"Error during user registration: <error_message>"`|

### Endpoint: `/submit-essay`
**Method:** POST

### Description:
Submits an essay for processing and stores it in the database.

### Parameters:
| Name     | Type   | In   | Required | Description               |
|----------|--------|------|----------|---------------------------|
| content  | string | Body | Yes      | The content of the essay. |
| username | string | Body | Yes      | The username of the submitter. |

### Responses:

#### Success:
| Status Code | Description                                   | Example Response                                                 |
|-------------|-----------------------------------------------|-------------------------------------------------------------------|
| 200         | Essay successfully submitted.                | `{ "message": "Essay submitted successfully", "username": "JohnDoe", "content_length": 500 }`|

#### Error:
| Status Code | Description                                   |
|-------------|-----------------------------------------------|
| 400         | `"Content and username are required."`       |
| 500         | `"An error occurred while submitting the essay."`|


### Endpoint: Edit User
**URL**: `/users/{user_id}`

**Method**: PUT  


### Description:
Allows updating user details such as username and/or password.

### Parameters:

| Name      | Type  | In    | Required | Description                                         |
|-----------|-------|-------|----------|-----------------------------------------------------|
| user_id   | str   | Path  | Yes      | The unique identifier of the user to update.        |
| username  | str   | Body  | No       | The new username for the user.                      |
| password  | str   | Body  | No       | The new password for the user.                      |

### Responses:

- **200 OK**: Returns a JSON object containing the updated user information.

```json
{
    "message": "User information updated successfully.",
    "user_id": "unique-user-id"
}
```

## Endpoint: `/users/recover-password`

**Method**: POST

### Description:
Allows users to request a password reset by providing their email address. The API will send a password reset email to the provided address.

### Parameters:

| Name    | Type  | In    | Required | Description                                 |
|---------|-------|-------|----------|---------------------------------------------|
| email   | str   | Body  | Yes      | The email address of the user requesting a password reset. |

### Responses:

- **200 OK**: Returns a JSON object confirming that the password reset email was sent.

```json
{
    "message": "Password reset email sent successfully.",
    "email": "user@example.com"
}
