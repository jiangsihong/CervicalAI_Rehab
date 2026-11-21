import unittest

from flask_jwt_extended import create_access_token
from sqlalchemy import inspect

from app import create_app
from models.assessment import Assessment
from models.user import User, db


class AssessmentDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.context = self.app.app_context()
        self.context.push()
        self.client = self.app.test_client()

        user = User(
            username='assessment-test',
            email='assessment-test@example.com',
            password='123456',
            role='patient',
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))
        self.headers = {'Authorization': 'Bearer ' + token}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_startup_creates_user_and_assessment_tables(self):
        table_names = set(inspect(db.engine).get_table_names())
        self.assertIn('users', table_names)
        self.assertIn('assessments', table_names)

    def test_empty_history_and_summary_are_available(self):
        summary = self.client.get('/api/assessment/summary', headers=self.headers)
        history = self.client.get('/api/assessment/history', headers=self.headers)

        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.get_json()['data']['total_assessments'], 0)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json()['data']['assessments'], [])

    def test_submit_creates_queryable_assessment(self):
        response = self.client.post(
            '/api/assessment/submit',
            headers=self.headers,
            json={
                'assessment_date': '2026-08-06',
                'flexion_angle': 55,
                'extension_angle': 50,
                'left_lateral_flexion_angle': 40,
                'right_lateral_flexion_angle': 41,
                'left_rotation_angle': 65,
                'right_rotation_angle': 66,
                'grade': 'severe',
            },
        )

        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(payload['code'], 201)
        self.assertEqual(Assessment.query.count(), 1)
        self.assertNotEqual(payload['data']['assessment']['grade'], 'severe')

        history = self.client.get('/api/assessment/history', headers=self.headers)
        self.assertEqual(history.get_json()['data']['total'], 1)

    def test_submit_rejects_invalid_date_and_angle(self):
        invalid_date = self.client.post(
            '/api/assessment/submit',
            headers=self.headers,
            json={'assessment_date': '06-08-2026'},
        )
        invalid_angle = self.client.post(
            '/api/assessment/submit',
            headers=self.headers,
            json={'assessment_date': '2026-08-06', 'flexion_angle': 120},
        )

        self.assertEqual(invalid_date.status_code, 400)
        self.assertEqual(invalid_angle.status_code, 400)


if __name__ == '__main__':
    unittest.main()
