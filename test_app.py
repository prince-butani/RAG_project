import os
import unittest
import tempfile
import json
from app import app, db, User
from werkzeug.security import generate_password_hash

class TestApp(unittest.TestCase):
    def setUp(self):
        self.db_fd, app.config['DATABASE'] = tempfile.mkstemp()
        app.config['TESTING'] = True
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(app.config['DATABASE'])

    def test_register(self):
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            if user:
                db.session.delete(user)
                db.session.commit()
        # Test successful registration
        data = {'username': 'testuser', 'password': 'testpassword'}
        response = self.app.post('/register', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)

        # Test username already exists
        response = self.app.post('/register', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 409)

        # Test missing data
        data = {'username': 'testuser'}
        response = self.app.post('/register', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 400)

        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            db.session.delete(user)
            db.session.commit()

    def test_login(self):
        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            if user:
                db.session.delete(user)
                db.session.commit()
            # Create a test user with encrypted password
            password = 'testpassword'
            encrypted_password = generate_password_hash(password)
            user = User(username='testuser', password=encrypted_password)
            db.session.add(user)
            db.session.commit()

        # Test successful login
        data = {'username': 'testuser', 'password': 'testpassword'}
        response = self.app.post('/login', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access_token', response.json)

        # Test invalid credentials
        data = {'username': 'testuser', 'password': 'wrongpassword'}
        response = self.app.post('/login', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 401)

        # Test missing data
        data = {'username': 'testuser'}
        response = self.app.post('/login', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 400)

        with app.app_context():
            user = User.query.filter_by(username='testuser').first()
            db.session.delete(user)
            db.session.commit()

if __name__ == '__main__':
    unittest.main()