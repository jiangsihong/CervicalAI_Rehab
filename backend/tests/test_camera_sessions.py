import copy
import unittest
from uuid import uuid4

from flask_jwt_extended import create_access_token
from sqlalchemy import inspect

from app import create_app
from models.camera_session import CameraSession
from models.user import User, db


class CameraSessionTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.context = self.app.app_context()
        self.context.push()
        self.client = self.app.test_client()
        self.headers = []
        for index in range(2):
            user = User(username='camera' + str(index), email='camera{}@example.com'.format(index), password='test123')
            db.session.add(user)
            db.session.commit()
            self.headers.append({'Authorization': 'Bearer ' + create_access_token(identity=str(user.id))})
        self.id = str(uuid4())
        self.path = '/api/assessment/pose/sessions/' + self.id
        self.payload = {
            'started_at': '2026-10-13T02:00:00Z', 'ended_at': '2026-10-13T02:00:10Z',
            'status': 'completed', 'revision': 2, 'duration_seconds': 10,
            'frame_count': 20, 'detected_frames': 18,
            'angle_stats': {'tilt': {'count': 18, 'min': -10, 'max': 20, 'mean': 5},
                            'pan': {'count': 18, 'min': -5, 'max': 5, 'mean': 0}, 'roll': None},
            'samples': [{'elapsed': 1, 'tilt': -10, 'pan': 0, 'roll': None},
                        {'elapsed': 9, 'tilt': 20, 'pan': 5, 'roll': None}],
        }

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def save(self, payload=None, owner=0):
        return self.client.put(self.path, json=payload or self.payload, headers=self.headers[owner])

    def test_persistent_record_detail_and_paginated_history(self):
        self.assertIn('camera_sessions', inspect(db.engine).get_table_names())
        self.assertEqual(self.save().status_code, 200)
        db.session.remove()
        detail = self.client.get(self.path, headers=self.headers[0]).get_json()['data']['session']
        self.assertEqual(detail['id'], self.id)
        self.assertEqual(detail['frame_count'], 20)
        self.assertIsNone(detail['angle_stats']['roll'])
        self.assertIsNone(detail['samples'][0]['roll'])
        history = self.client.get('/api/assessment/pose/sessions?limit=1', headers=self.headers[0]).get_json()['data']
        self.assertEqual(history['total'], 1)
        self.assertNotIn('samples', history['sessions'][0])
        page = self.client.get('/api/assessment/pose/sessions?offset=1', headers=self.headers[0]).get_json()['data']
        self.assertEqual(page['sessions'], [])

    def test_duplicate_and_delayed_checkpoint_do_not_overwrite_final_save(self):
        self.save()
        self.save()
        stale = copy.deepcopy(self.payload)
        stale.update(revision=1, status='recording', ended_at=None, frame_count=19)
        self.assertEqual(self.save(stale).status_code, 200)
        self.assertEqual(CameraSession.query.count(), 1)
        saved = self.client.get(self.path, headers=self.headers[0]).get_json()['data']['session']
        self.assertEqual(saved['status'], 'completed')
        self.assertEqual(saved['frame_count'], 20)

    def test_checkpoints_and_final_result_update_one_record(self):
        checkpoint = copy.deepcopy(self.payload)
        checkpoint.update(revision=1, status='recording', ended_at=None)
        self.assertEqual(self.save(checkpoint).status_code, 200)
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(CameraSession.query.count(), 1)
        self.assertEqual(CameraSession.query.first().revision, 2)

    def test_account_isolation_and_authentication(self):
        self.assertEqual(self.client.put(self.path, json=self.payload).status_code, 401)
        self.save()
        self.assertEqual(self.client.get(self.path, headers=self.headers[1]).status_code, 404)
        self.assertEqual(self.save(owner=1).status_code, 404)
        result = self.client.get('/api/assessment/pose/sessions', headers=self.headers[1]).get_json()['data']
        self.assertEqual(result['total'], 0)

    def test_no_face_session_does_not_fabricate_zero_angles(self):
        empty = copy.deepcopy(self.payload)
        empty.update(detected_frames=0, angle_stats={'tilt': None, 'pan': None, 'roll': None},
                     samples=[{'elapsed': 1, 'tilt': None, 'pan': None, 'roll': None}])
        self.assertEqual(self.save(empty).status_code, 200)
        saved = CameraSession.query.first().to_dict()
        self.assertIsNone(saved['angle_stats']['tilt'])

    def test_validates_stats_times_samples_and_revision(self):
        invalid = [None, [], {'revision': 0}, {'detected_frames': 21}, {'duration_seconds': float('nan')},
                   {'ended_at': '2026-10-12T00:00:00Z'}, {'started_at': '2026-10-13T02:00:00'},
                   {'samples': [{'elapsed': 11, 'tilt': 0, 'pan': 0, 'roll': 0}]},
                   {'samples': [{'elapsed': 2}, {'elapsed': 1}]}, {'samples': [{}] * 301},
                   {'angle_stats': {'tilt': {'count': 18, 'min': -5, 'max': 5, 'mean': 10}}}]
        for change in invalid:
            payload = copy.deepcopy(self.payload)
            if isinstance(change, dict):
                payload.update(change)
            else:
                payload = change
            response = self.client.put(self.path, json=payload, headers=self.headers[0])
            self.assertEqual(response.status_code, 400, change)
        self.assertEqual(CameraSession.query.count(), 0)

    def test_local_date_filter_uses_browser_timezone(self):
        self.payload.update(started_at='2026-10-12T17:00:00Z', ended_at='2026-10-12T17:00:10Z')
        self.save()
        url = '/api/assessment/pose/sessions?start_date=2026-10-13&end_date=2026-10-13&timezone_offset=-480'
        result = self.client.get(url, headers=self.headers[0]).get_json()['data']
        self.assertEqual(result['total'], 1)
        bad = self.client.get('/api/assessment/pose/sessions?start_date=bad', headers=self.headers[0])
        self.assertEqual(bad.status_code, 400)


if __name__ == '__main__':
    unittest.main()
